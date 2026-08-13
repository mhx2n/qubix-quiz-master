# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 146 (2026-08-13) — CSV split files + cancel button on live cards
#
# 1) CSV upload/forward now shows a two-button card first:
#      🎯 কুইজ কনভার্ট → rows go to the buffer exactly like section 142 did
#      ✂️ স্প্লিট ফাইল → pick 25/30/35/40/45/50/55/60/70 or a custom size;
#        rows are divided equally and every part is sent back to the inbox as
#        its own serial-numbered CSV (part01, part02, …).  Whatever remains at
#        the tail — even fewer than the chosen size — becomes the last file.
# 2) Every live generation card (PDF/image harvest + .gen AI generation) now
#    carries a ⏹ button.  Tapping it stops the job; questions already in the
#    buffer stay and are reported.  Nothing else in any earlier flow changes:
#    all overrides delegate to the previous globals and only add the button,
#    the cancel flag and the split branch.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a146
import contextlib as _cx146
import csv as _csv146
import os as _os146
import re as _re146
import tempfile as _tmp146
import time as _t146
import uuid as _uuid146


def _qx146_log(message, *args, **kwargs):
    """Section-safe logger: accepts (msg), (msg, level) and printf-style
    (msg, *fmt_args[, level]) — never raises, never crashes a handler."""
    with _cx146.suppress(Exception):
        level = kwargs.pop("level", "info")
        parts = list(args)
        msg = None
        # trailing known level keyword passed positionally, e.g. (msg, "warning")
        if parts and isinstance(parts[-1], str) and parts[-1] in (
                "debug", "info", "warning", "error", "critical"):
            try:
                msg = str(message) % tuple(parts[:-1]) if parts[:-1] else str(message)
                level = parts[-1]
                parts = []
            except Exception:
                msg = None
        if msg is None:
            try:
                msg = str(message) % tuple(parts) if parts else str(message)
            except Exception:
                msg = str(message) + (" " + " ".join(str(p) for p in parts) if parts else "")
        getattr(logger, str(level), logger.info)("[S146] %s", msg)  # type: ignore[name-defined]


_QX146_BN = {ord(c): str(i) for i, c in enumerate("০১২৩৪৫৬৭৮৯")}
_QX146_PENDING = {}    # token -> {uid, chat_id, rows, name, ts}
_QX146_AWAIT = {}      # uid   -> (token, ts)  waiting for a custom split size
_QX146_JOBS = {}       # uid   -> {"cancel": bool, "status": msg, "kind": str}
_QX146_CANCELLED = {}  # uid   -> ts of the latest cancelled harvest
_QX146_SIZES = (25, 30, 35, 40, 45, 50, 55, 60, 70)


def _qx146_prune():
    now = _t146.time()
    for token, entry in list(_QX146_PENDING.items()):
        if now - float((entry or {}).get("ts") or 0) > 3600:
            _QX146_PENDING.pop(token, None)
    for uid, pair in list(_QX146_AWAIT.items()):
        with _cx146.suppress(Exception):
            if now - float((pair or (None, 0))[1] or 0) > 600:
                _QX146_AWAIT.pop(uid, None)
    for uid, ts in list(_QX146_CANCELLED.items()):
        if now - float(ts or 0) > 600:
            _QX146_CANCELLED.pop(uid, None)


def _qx146_box(title, body, emoji="📥"):
    boxer = globals().get("ui_box_html")
    if callable(boxer):
        with _cx146.suppress(Exception):
            return boxer(title, body, emoji=emoji)
    return "%s %s\n%s" % (emoji, title, body)


# ═════════════════════════════════════════════════════════════════════════════
# 1) Cancel button + job registry
# ═════════════════════════════════════════════════════════════════════════════
def _qx146_cancel_kb(uid):
    try:
        return InlineKeyboardMarkup([[InlineKeyboardButton(  # type: ignore[name-defined]
            "⏹ বন্ধ করুন", callback_data="qx146:cancel:%d" % int(uid))]])  # type: ignore[name-defined]
    except Exception:
        return None


def _qx146_uid_for_status(status):
    """Find which running job owns this status card (harvest cards carry no uid)."""
    if status is None:
        return 0
    mid = int(getattr(status, "message_id", 0) or 0)
    if not mid:
        return 0
    cid = int(getattr(status, "chat_id", 0) or 0)
    for uid, job in list(_QX146_JOBS.items()):
        st = (job or {}).get("status")
        if st is None:
            continue
        with _cx146.suppress(Exception):
            if int(getattr(st, "message_id", 0) or 0) != mid:
                continue
            st_cid = int(getattr(st, "chat_id", 0) or 0)
            if cid and st_cid and cid != st_cid:
                continue
            return int(uid)
    return 0


def _qx146_elapsed(started):
    seconds = max(0, int(_t146.time() - float(started or 0)))
    minutes, rest = divmod(seconds, 60)
    return "%dm %02ds" % (minutes, rest) if minutes else "%ds" % rest


# ── 1a) Verbatim harvest card — same body as section 138, plus the ⏹ button ──
async def _qx138_card(status, found, expected, added, started,
                      title="Converting Questions"):  # noqa: F811
    if status is None:
        return
    target = max(1, int(expected or 0) or int(found or 0) or 1)
    percent = max(0, min(100, round((int(found or 0) / target) * 100)))
    body = (
        "শনাক্ত হয়েছে: <b>%d</b>\n"
        "তৈরি হয়েছে: <b>%d</b> / <b>%d</b>\n"
        "Progress: <b>%d%%</b>\n"
        "Buffer-এ যোগ: <b>%d</b>\n"
        "সময়: <code>%s</code>\n\n"
        "Source-এর প্রশ্ন ও সমাধান হুবহু যাচাই হচ্ছে…"
        % (int(expected or 0), int(found or 0), int(expected or 0) or int(found or 0),
           percent, int(added or 0), _qx146_elapsed(started))
    )
    text = _qx146_box(title, body, "🧠")
    uid = _qx146_uid_for_status(status)
    markup = _qx146_cancel_kb(uid) if uid else None
    with _cx146.suppress(Exception):
        await status.edit_text(text, parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                               reply_markup=markup)


globals()["_qx138_card"] = _qx138_card


# ── 1b) .gen live card — same body as section 129, plus the ⏹ button ─────────
async def _qx129_progress(context, update, uid, done, wanted, mode, started):  # noqa: F811
    cards = globals().get("_QX95_LAST_GEN_CARD") or {}
    message = getattr(update, "effective_message", None)
    chat_id = int(getattr(message, "chat_id", 0) or 0)
    message_id = cards.get((chat_id, int(uid or 0)))
    if not chat_id or not message_id:
        return
    elapsed = max(0, int(_t146.time() - float(started or 0)))
    minutes, seconds = divmod(elapsed, 60)
    elapsed_text = "%dm %02ds" % (minutes, seconds) if minutes else "%ds" % seconds
    try:
        percent = max(0, min(100, round((int(done) / max(1, int(wanted))) * 100)))
    except Exception:
        percent = 0
    body = (
        "Standard: <b>%s</b>\n"
        "তৈরি হয়েছে: <b>%d</b> / <b>%d</b>\n"
        "Progress: <b>%d%%</b>\n"
        "সময়: <code>%s</code>\n\n"
        "🧠 Source মিলিয়ে quiz তৈরি ও যাচাই হচ্ছে…"
        % (str(mode or "std").upper(), int(done), int(wanted), percent, elapsed_text)
    )
    text = _qx146_box("Generating Quiz", body, "⏳")
    with _cx146.suppress(Exception):
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=int(message_id), text=text,
            parse_mode=ParseMode.HTML, disable_web_page_preview=True,  # type: ignore[name-defined]
            reply_markup=_qx146_cancel_kb(uid),
        )


globals()["_qx129_progress"] = _qx129_progress


# ── 1c) Harvest wrapper — runs the proven bounded harvest, cancellable ───────
_qx146_prev_harvest = globals().get("_qxv_harvest")


async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):  # noqa: F811
    fast = globals().get("_qx145_fast_harvest")
    prev = _qx146_prev_harvest
    uid = int(uid or 0)
    buffer_ids = globals().get("_qx129_buffer_ids")
    before = set()
    if callable(buffer_ids):
        with _cx146.suppress(Exception):
            before = set(buffer_ids(uid) or set())

    state = {"expected": 0, "found": 0, "added": 0,
             "started": _t146.time(), "done": False}
    job = _QX146_JOBS[uid] = {"cancel": False, "status": status, "kind": "harvest"}
    card = globals().get("_qx138_card")

    async def ticker():
        while not state["done"]:
            await _a146.sleep(10.0)
            if state["done"] or not callable(card):
                continue
            with _cx146.suppress(Exception):
                await card(status, int(state["found"]),
                           int(state["expected"]) or int(state["found"]),
                           int(state["added"]), state["started"])

    async def runner():
        if callable(fast):
            outcome = await fast(update, context, uid, source_text, status, label, state)
            if outcome is not None:
                return outcome
        if callable(prev):
            return await prev(update, context, uid, source_text, status, label)
        return 0, 0, 0

    tick_task = _a146.ensure_future(ticker())
    run_task = _a146.ensure_future(runner())
    cancelled = False
    try:
        while not run_task.done():
            if job.get("cancel"):
                run_task.cancel()
                cancelled = True
                break
            await _a146.sleep(0.6)
        if not cancelled:
            try:
                return await run_task
            except _a146.CancelledError:
                cancelled = True
        with _cx146.suppress(_a146.CancelledError, Exception):
            await run_task

        # ── cancelled: keep whatever already landed in the buffer ──
        after = set()
        if callable(buffer_ids):
            with _cx146.suppress(Exception):
                after = set(buffer_ids(uid) or set())
        added = max(int(state["added"] or 0), len(after - before))
        found = int(state["found"] or 0)
        _QX146_CANCELLED[uid] = _t146.time()
        if status is not None:
            body = "⏹ জেনারেশন বন্ধ করা হচ্ছে…\nএ পর্যন্ত তৈরি প্রশ্ন Buffer-এ রাখা হয়েছে।"
            with _cx146.suppress(Exception):
                await status.edit_text(_qx146_box("Cancelled", body, "⏹"),
                                       parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        _qx146_log("harvest cancelled by uid=%s added=%s found=%s", uid, added, found)
        # found must stay truthy so callers never fall into the AI fallback.
        found_out = found if found > 0 else (added if added > 0 else -1)
        return int(added), 0, int(found_out)
    finally:
        state["done"] = True
        _QX146_JOBS.pop(uid, None)
        for task in (tick_task, run_task):
            if task is not None and not task.done():
                task.cancel()
        with _cx146.suppress(_a146.CancelledError, Exception):
            await _a146.gather(
                *[t for t in (tick_task, run_task) if t is not None],
                return_exceptions=True,
            )


globals()["_qxv_harvest"] = _qxv_harvest


# ── 1d) .gen wrapper — same generator, cancellable ───────────────────────────
_qx146_prev_gen = globals().get("_generate_to_buffer_59")

if callable(_qx146_prev_gen):

    async def _generate_to_buffer_59(update, context, ocr_ctx, uid, count,
                                     mode="std"):  # noqa: F811
        uid = int(uid or 0)
        buffer_ids = globals().get("_qx129_buffer_ids")
        before = set()
        if callable(buffer_ids):
            with _cx146.suppress(Exception):
                before = set(buffer_ids(uid) or set())
        job = _QX146_JOBS[uid] = {"cancel": False, "kind": "gen"}
        task = _a146.ensure_future(
            _qx146_prev_gen(update, context, ocr_ctx, uid, count, mode))
        cancelled = False
        try:
            while not task.done():
                if job.get("cancel"):
                    task.cancel()
                    cancelled = True
                    break
                await _a146.sleep(0.6)
            if not cancelled:
                try:
                    return await task
                except _a146.CancelledError:
                    cancelled = True
            with _cx146.suppress(_a146.CancelledError, Exception):
                await task
            after = set()
            if callable(buffer_ids):
                with _cx146.suppress(Exception):
                    after = set(buffer_ids(uid) or set())
            added = len(after - before)
            _qx146_log("gen cancelled by uid=%s partial added=%s", uid, added)
            return int(added), 0
        finally:
            _QX146_JOBS.pop(uid, None)
            if not task.done():
                task.cancel()
                with _cx146.suppress(_a146.CancelledError, Exception):
                    await task

    globals()["_generate_to_buffer_59"] = _generate_to_buffer_59


# ── 1e) Cancelled harvest report — replaces the usual report just once ───────
_qx146_prev_report = globals().get("_qxv_report")

if callable(_qx146_prev_report):

    async def _qxv_report(update, context, uid, added, dup, found, label):  # noqa: F811
        uid_i = int(uid or 0)
        ts = _QX146_CANCELLED.pop(uid_i, 0) or 0
        if not ts or _t146.time() - float(ts) >= 300:
            return await _qx146_prev_report(update, context, uid, added, dup, found, label)
        total = 0
        with _cx146.suppress(Exception):
            total = int(buffer_count(uid_i) or 0)  # type: ignore[name-defined]
        real_found = int(found or 0)
        if real_found < 0:
            real_found = int(added or 0)
        body = (
            "📄 Source: <b>%s</b>\n"
            "🔎 পাওয়া প্রশ্ন: <b>%d</b>\n"
            "➕ Buffer-এ যোগ: <b>%d</b>\n"
            "📦 Buffer total: <b>%d</b>\n\n"
            "⏹ আপনি জেনারেশন বন্ধ করেছেন — এ পর্যন্ত তৈরি প্রশ্নগুলোই রাখা হয়েছে।"
            % (str(label or "source"), real_found, int(added or 0), total)
        )
        message = getattr(update, "effective_message", None)
        with _cx146.suppress(Exception):
            if message is not None:
                await message.reply_text(
                    _qx146_box("Generation Stopped", body, "⏹"),
                    parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        if int(added or 0) > 0:
            card = globals().get("_send_pb_action_card")
            if callable(card) and message is not None:
                with _cx146.suppress(Exception):
                    await card(context, message.chat_id, uid_i, int(added))
        return None

    globals()["_qxv_report"] = _qxv_report


# ═════════════════════════════════════════════════════════════════════════════
# 2) CSV upload → two-button card → convert OR split
# ═════════════════════════════════════════════════════════════════════════════
def _qx146_choice_body(count):
    return (
        "মোট প্রশ্ন: <b>%d</b> টি\n\n"
        "🎯 <b>কুইজ কনভার্ট</b> — সব প্রশ্ন Buffer-এ যোগ হবে\n"
        "✂️ <b>স্প্লিট ফাইল</b> — সমান ভাগে আলাদা আলাদা CSV"
        % int(count)
    )


def _qx146_choice_kb(token):
    return InlineKeyboardMarkup([  # type: ignore[name-defined]
        [InlineKeyboardButton("🎯 কুইজ কনভার্ট", callback_data="qx146:conv:%s" % token),  # type: ignore[name-defined]
         InlineKeyboardButton("✂️ স্প্লিট ফাইল", callback_data="qx146:split:%s" % token)],  # type: ignore[name-defined]
        [InlineKeyboardButton("✖ বাতিল", callback_data="qx146:close:%s" % token)],  # type: ignore[name-defined]
    ])


def _qx146_size_kb(token):
    rows, line = [], []
    for size in _QX146_SIZES:
        line.append(InlineKeyboardButton(str(size),  # type: ignore[name-defined]
                                         callback_data="qx146:sz:%s:%d" % (token, size)))
        if len(line) == 4:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton("✏️ কাস্টম সংখ্যা",  # type: ignore[name-defined]
                                      callback_data="qx146:custom:%s" % token)])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="qx146:back:%s" % token),  # type: ignore[name-defined]
                 InlineKeyboardButton("✖ বাতিল", callback_data="qx146:close:%s" % token)])  # type: ignore[name-defined]
    return InlineKeyboardMarkup(rows)  # type: ignore[name-defined]


async def qx146_csv_inbox(update, context):
    """CSV document → parse → choice card (convert / split).  Non-CSV passes through."""
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    document = getattr(message, "document", None) if message is not None else None
    is_csv = globals().get("_qx142_is_csv")
    if message is None or user is None or document is None or not callable(is_csv):
        return None
    if not is_csv(document):
        return None

    gate = globals().get("_qxz_may_run") or globals().get("_qx99_may_run")
    uid = int(user.id)
    if callable(gate):
        allowed = True
        with _cx146.suppress(Exception):
            allowed = bool(gate(uid))
        if not allowed:
            return None

    status = None
    with _cx146.suppress(Exception):
        status = await message.reply_text(
            _qx146_box("CSV ফাইল", "ফাইল পড়া হচ্ছে…", "📥"),
            parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
        )

    text = ""
    path = ""
    try:
        handle = await context.bot.get_file(document.file_id)
        path = _os146.path.join(_tmp146.gettempdir(),
                                "qx146_%s.csv" % _uuid146.uuid4().hex[:10])
        await handle.download_to_drive(custom_path=path)
        with open(path, "rb") as stream:
            blob = stream.read()
        decoder = globals().get("_qx142_decode")
        if callable(decoder):
            with _cx146.suppress(Exception):
                text = decoder(blob)
        if not text:
            with _cx146.suppress(Exception):
                text = blob.decode("utf-8-sig", "ignore")
    except Exception as error:
        _qx146_log("csv download failed: %s" % str(error)[:160], "warning")
    finally:
        with _cx146.suppress(Exception):
            if path:
                _os146.remove(path)

    rows = []
    parser = globals().get("_qx142_rows_from_csv")
    if callable(parser):
        with _cx146.suppress(Exception):
            rows = list(parser(text) or [])

    if not rows:
        body = (
            "কোনো বৈধ প্রশ্ন পাওয়া যায়নি।\n\n"
            "কলাম দরকার: <code>questions, option1..option4, answer</code>"
            " (ঐচ্ছিক <code>explanation</code>)।\n"
            "বটের export করা CSV সরাসরি কাজ করবে।"
        )
        with _cx146.suppress(Exception):
            if status is not None:
                await status.edit_text(_qx146_box("CSV ফাইল", body, "⚠️"),
                                       parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
            else:
                await message.reply_text(_qx146_box("CSV ফাইল", body, "⚠️"),
                                         parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    _qx146_prune()
    token = _uuid146.uuid4().hex[:10]
    name = str(getattr(document, "file_name", "") or "quiz.csv")
    _QX146_PENDING[token] = {
        "uid": uid,
        "chat_id": int(getattr(message, "chat_id", 0) or uid),
        "rows": rows,
        "name": name,
        "ts": _t146.time(),
    }
    card_text = _qx146_box("CSV ফাইল প্রস্তুত", _qx146_choice_body(len(rows)), "📥")
    with _cx146.suppress(Exception):
        if status is not None:
            await status.edit_text(card_text, parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                                   reply_markup=_qx146_choice_kb(token))
        else:
            await message.reply_text(card_text, parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                                     reply_markup=_qx146_choice_kb(token))
    _qx146_log("csv ready: rows=%s uid=%s token=%s", len(rows), uid, token)
    raise ApplicationHandlerStop  # type: ignore[name-defined]


# ── split execution ───────────────────────────────────────────────────────────
def _qx146_write_part(rows, path):
    header = ["questions", "option1", "option2", "option3", "option4",
              "option5", "answer", "explanation", "type", "section"]
    with open(path, "w", encoding="utf-8-sig", newline="") as stream:
        writer = _csv146.writer(stream)
        writer.writerow(header)
        for row in rows or []:
            options = list((row or {}).get("options") or [])[:5]
            while len(options) < 5:
                options.append("")
            writer.writerow([
                str((row or {}).get("question") or (row or {}).get("questions") or ""),
                *[str(o or "") for o in options],
                int((row or {}).get("answer") or 0),
                str((row or {}).get("explanation") or ""),
                1, 1,
            ])


async def _qx146_do_split(context, entry, size):
    """Send the rows as serial-numbered CSV parts; the tail remainder is the last file."""
    rows = list((entry or {}).get("rows") or [])
    uid = int((entry or {}).get("uid") or 0)
    chat_id = int((entry or {}).get("chat_id") or uid)
    if not rows or int(size or 0) <= 0:
        return 0, 0
    size = int(size)
    base = _re146.sub(r"\.(csv|tsv)$", "", str((entry or {}).get("name") or "quiz"),
                      flags=_re146.I)
    base = _re146.sub(r"[^\w\-.]+", "_", base).strip("_") or "quiz"
    chunks = [rows[i:i + size] for i in range(0, len(rows), size)]
    total = len(chunks)
    sent = 0
    start = 1
    for index, chunk in enumerate(chunks, start=1):
        path = _os146.path.join(_tmp146.gettempdir(),
                                "qx146_part_%s.csv" % _uuid146.uuid4().hex[:8])
        try:
            _qx146_write_part(chunk, path)
            end = start + len(chunk) - 1
            caption = (
                "📄 <b>Part %d/%d</b> — প্রশ্ন <b>%d–%d</b> (%dটি)"
                % (index, total, start, end, len(chunk))
            )
            with open(path, "rb") as stream:
                await context.bot.send_document(
                    chat_id=chat_id, document=stream,
                    filename="%s_part%02d.csv" % (base, index),
                    caption=caption, parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                )
            sent += 1
            start = end + 1
            await _a146.sleep(0.4)
        except Exception as error:
            _qx146_log("split part %s failed: %s" % (index, str(error)[:160]), "warning")
        finally:
            with _cx146.suppress(Exception):
                _os146.remove(path)
    return sent, total


def _qx146_split_done_body(entry, size, sent, total):
    return (
        "মোট প্রশ্ন: <b>%d</b> টি\n"
        "প্রতি ফাইলে: <b>%d</b> টি\n"
        "ফাইল পাঠানো হয়েছে: <b>%d/%d</b> টি"
        % (len(list((entry or {}).get("rows") or [])), int(size), int(sent), int(total))
    )


# ── callback handler ──────────────────────────────────────────────────────────
async def qx146_cb(update, context):
    query = getattr(update, "callback_query", None)
    data = str(getattr(query, "data", "") or "") if query is not None else ""
    if not data.startswith("qx146:"):
        return None
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    caller = int(getattr(getattr(query, "from_user", None), "id", 0) or 0)

    # ── ⏹ cancel a running generation ──
    if action == "cancel" and len(parts) >= 3:
        owner = -1
        with _cx146.suppress(Exception):
            owner = int(parts[2])
        if caller != owner:
            with _cx146.suppress(Exception):
                await query.answer("এই বাটনটি আপনার জন্য নয়।", show_alert=True)
            raise ApplicationHandlerStop  # type: ignore[name-defined]
        job = _QX146_JOBS.get(caller)
        if not job:
            with _cx146.suppress(Exception):
                await query.answer("এই জেনারেশন শেষ হয়ে গেছে ✅", show_alert=False)
            raise ApplicationHandlerStop  # type: ignore[name-defined]
        job["cancel"] = True
        with _cx146.suppress(Exception):
            await query.answer("⏹ বন্ধ হচ্ছে — এ পর্যন্ত যা তৈরি হয়েছে তাই রাখা হবে।",
                               show_alert=False)
        with _cx146.suppress(Exception):
            await query.edit_message_reply_markup(reply_markup=None)
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    # ── CSV card actions ──
    token = parts[2] if len(parts) > 2 else ""
    _qx146_prune()
    entry = _QX146_PENDING.get(token)
    if not entry:
        with _cx146.suppress(Exception):
            await query.answer("মেয়াদ শেষ — ফাইলটি আবার পাঠান।", show_alert=True)
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    if caller != int(entry.get("uid") or 0):
        with _cx146.suppress(Exception):
            await query.answer("এই বাটনটি আপনার জন্য নয়।", show_alert=True)
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action == "close":
        _QX146_PENDING.pop(token, None)
        _QX146_AWAIT.pop(caller, None)
        with _cx146.suppress(Exception):
            await query.message.delete()
        with _cx146.suppress(Exception):
            await query.answer()
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action == "conv":
        rows = list(entry.get("rows") or [])
        _QX146_PENDING.pop(token, None)
        _QX146_AWAIT.pop(caller, None)
        added = dup = 0
        storer = globals().get("_qxz_store_rows")
        if callable(storer):
            with _cx146.suppress(Exception):
                stored_added, stored_dup = storer(caller, rows, "csv")
                added, dup = int(stored_added or 0), int(stored_dup or 0)
        with _cx146.suppress(Exception):
            await query.answer("✅ Buffer-এ যোগ হচ্ছে…")
        with _cx146.suppress(Exception):
            await query.message.delete()
        chat_id = int(entry.get("chat_id") or caller)
        card = globals().get("_send_pb_action_card")
        if callable(card):
            with _cx146.suppress(Exception):
                await card(context, chat_id, caller, added)
        else:
            total = 0
            with _cx146.suppress(Exception):
                total = int(buffer_count(caller) or 0)  # type: ignore[name-defined]
            with _cx146.suppress(Exception):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=_qx146_box(
                        "CSV → Quiz",
                        "যোগ হয়েছে: <b>%d</b>\nDuplicate: <b>%d</b>\nBuffer: <b>%d</b>"
                        % (added, dup, total),
                        "✅",
                    ),
                    parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        _qx146_log("csv convert: rows=%s added=%s dup=%s uid=%s",
                   len(rows), added, dup, caller)
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action == "split":
        body = (
            "মোট প্রশ্ন: <b>%d</b> টি\n\n"
            "প্রতি ফাইলে কতটি প্রশ্ন থাকবে?\n"
            "শেষে যা বেঁচে যাবে (কম হলেও) সেটাই শেষ ফাইলে যাবে।"
            % len(list(entry.get("rows") or []))
        )
        with _cx146.suppress(Exception):
            await query.message.edit_text(
                _qx146_box("স্প্লিট ফাইল", body, "✂️"),
                parse_mode=ParseMode.HTML, reply_markup=_qx146_size_kb(token))  # type: ignore[name-defined]
        with _cx146.suppress(Exception):
            await query.answer()
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action == "back":
        with _cx146.suppress(Exception):
            await query.message.edit_text(
                _qx146_box("CSV ফাইল প্রস্তুত",
                           _qx146_choice_body(len(list(entry.get("rows") or []))), "📥"),
                parse_mode=ParseMode.HTML, reply_markup=_qx146_choice_kb(token))  # type: ignore[name-defined]
        with _cx146.suppress(Exception):
            await query.answer()
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action == "custom":
        _QX146_AWAIT[caller] = (token, _t146.time())
        body = (
            "প্রতি ফাইলে কতটি প্রশ্ন থাকবে?\n\n"
            "শুধু সংখ্যাটি লিখে পাঠান — যেমন: <code>45</code>\n"
            "(১–৫০০ এর মধ্যে)"
        )
        with _cx146.suppress(Exception):
            await query.message.edit_text(
                _qx146_box("কাস্টম সাইজ", body, "✏️"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        with _cx146.suppress(Exception):
            await query.answer()
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action == "sz" and len(parts) >= 4:
        size = 0
        with _cx146.suppress(Exception):
            size = int(str(parts[3]).translate(_QX146_BN))
        size = max(1, min(500, size))
        _QX146_PENDING.pop(token, None)
        _QX146_AWAIT.pop(caller, None)
        with _cx146.suppress(Exception):
            await query.answer("✂️ স্প্লিট হচ্ছে…")
        with _cx146.suppress(Exception):
            await query.message.edit_text(
                _qx146_box("স্প্লিট ফাইল",
                           "প্রতি ফাইলে <b>%d</b> টি করে ভাগ করা হচ্ছে…" % size, "✂️"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        sent, total = await _qx146_do_split(context, entry, size)
        with _cx146.suppress(Exception):
            await query.message.edit_text(
                _qx146_box("স্প্লিট সম্পন্ন",
                           _qx146_split_done_body(entry, size, sent, total), "✅"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        _qx146_log("csv split: size=%s files=%s/%s uid=%s", size, sent, total, caller)
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    with _cx146.suppress(Exception):
        await query.answer()
    raise ApplicationHandlerStop  # type: ignore[name-defined]


# ── custom split size typed as plain text ─────────────────────────────────────
async def qx146_size_text(update, context):
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        return None
    uid = int(user.id)
    pair = _QX146_AWAIT.get(uid)
    if not pair:
        return None
    token, ts = pair
    if _t146.time() - float(ts or 0) > 600:
        _QX146_AWAIT.pop(uid, None)
        return None
    digits = str(getattr(message, "text", "") or "").strip().translate(_QX146_BN)
    if not _re146.fullmatch(r"[0-9]{1,3}", digits or ""):
        with _cx146.suppress(Exception):
            await message.reply_text(
                _qx146_box("কাস্টম সাইজ",
                           "শুধু সংখ্যা লিখুন — যেমন: <code>45</code> (১–৫০০)", "✏️"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    size = max(1, min(500, int(digits)))
    _QX146_AWAIT.pop(uid, None)
    entry = _QX146_PENDING.pop(token, None)
    if not entry:
        with _cx146.suppress(Exception):
            await message.reply_text(
                _qx146_box("স্প্লিট ফাইল", "মেয়াদ শেষ — CSV ফাইলটি আবার পাঠান।", "⚠️"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    status = None
    with _cx146.suppress(Exception):
        status = await message.reply_text(
            _qx146_box("স্প্লিট ফাইল",
                       "প্রতি ফাইলে <b>%d</b> টি করে ভাগ করা হচ্ছে…" % size, "✂️"),
            parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
    sent, total = await _qx146_do_split(context, entry, size)
    with _cx146.suppress(Exception):
        if status is not None:
            await status.edit_text(
                _qx146_box("স্প্লিট সম্পন্ন",
                           _qx146_split_done_body(entry, size, sent, total), "✅"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
    _qx146_log("csv split (custom): size=%s files=%s/%s uid=%s", size, sent, total, uid)
    raise ApplicationHandlerStop  # type: ignore[name-defined]


# ── wiring ────────────────────────────────────────────────────────────────────
_qx146_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx146_prev_build_app() if callable(_qx146_prev_build_app) else None
    if app is None:
        return app
    with _cx146.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx146_cb, pattern=r"^qx146:"),  # type: ignore[name-defined]
            group=-3800,
        )
    with _cx146.suppress(Exception):
        app.add_handler(
            MessageHandler(filters.Document.ALL, qx146_csv_inbox),  # type: ignore[name-defined]
            group=-3400,
        )
    with _cx146.suppress(Exception):
        app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, qx146_size_text),  # type: ignore[name-defined]
            group=-3400,
        )
    _qx146_log("csv split + cancel handlers wired")
    return app


_qx146_log("csv split + cancel button active")