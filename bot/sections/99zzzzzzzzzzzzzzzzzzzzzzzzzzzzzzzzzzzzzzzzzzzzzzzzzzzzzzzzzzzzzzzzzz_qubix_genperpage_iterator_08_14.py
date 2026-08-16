# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 148 (2026-08-14) — .genperpage: PDF page-by-page quiz iterator
#
# Reply to a PDF with:
#     .genperpage 3      → page 3 → last page, ONE page at a time
#     .genperpage 4-8    → pages 4,5,6,7,8 — each page is fully processed
#                          (OCR → every printed question → buffer) before the
#                          next page starts, exactly like a normal .gen run.
#
# Every page gets its own live card (10s refresh + ⏹ cancel button, reusing
# the untouched section-145/146 harvest engine).  Cancelling stops the whole
# run; whatever already landed in the buffer stays.  When the run ends a
# final summary card + the usual action card arrive.
#
# Additive only: no earlier global is removed or re-routed.  The command is
# registered next to .gen and listed in the OWNER command menu.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a148
import contextlib as _cx148
import os as _os148
import re as _re148
import tempfile as _tf148
import time as _t148


def _qx148_log(message, *args, **kwargs):
    """Never-raising logger: (msg), (msg, level) or printf-style."""
    with _cx148.suppress(Exception):
        level = kwargs.pop("level", "info")
        parts = list(args)
        msg = None
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
        getattr(logger, str(level), logger.info)("[S148] %s", msg)  # type: ignore[name-defined]


_QX148_BN = {ord(c): str(i) for i, c in enumerate("০১২৩৪৫৬৭৮৯")}
_QX148_STOP = {}   # uid -> ts of the latest stop request (OCR-phase cancel)
_QX148_RUNS = {}   # uid -> True while a page-by-page run is active
_QX148_MAX_PAGES = 20

_QX148_HELP = (
    "<b>ব্যবহার</b>\n"
    "PDF ফাইলটিতে <b>reply</b> করে লিখুন:\n"
    "<code>.genperpage 3</code> — ৩ নম্বর পৃষ্ঠা থেকে শেষ পৃষ্ঠা পর্যন্ত\n"
    "<code>.genperpage 4-8</code> — ৪ থেকে ৮ নম্বর পৃষ্ঠা পর্যন্ত\n\n"
    "প্রতিটি পৃষ্ঠা <b>একটা করে</b> প্রসেস হবে — ঐ পৃষ্ঠার সব প্রশ্ন quiz-এ\n"
    "রূপান্তরিত হয়ে Buffer-এ যোগ হবে, তারপর পরের পৃষ্ঠা শুরু হবে।\n"
    "এক রানে সর্বোচ্চ <b>%d</b> পৃষ্ঠা।\n"
    "সদ্য পাঠানো PDF থাকলে reply ছাড়াও কাজ করবে।" % _QX148_MAX_PAGES
)


def _qx148_box(title, body, emoji="📄"):
    boxer = globals().get("ui_box_html")
    if callable(boxer):
        with _cx148.suppress(Exception):
            return boxer(title, body, emoji=emoji)
    return "%s %s\n%s" % (emoji, title, body)


def _qx148_elapsed(started):
    seconds = max(0, int(_t148.time() - float(started or 0)))
    minutes, rest = divmod(seconds, 60)
    return "%dm %02ds" % (minutes, rest) if minutes else "%ds" % rest


def _qx148_cancel_kb(uid):
    try:
        return InlineKeyboardMarkup([[InlineKeyboardButton(  # type: ignore[name-defined]
            "⏹ বন্ধ করুন", callback_data="qx148:cancel:%d" % int(uid))]])  # type: ignore[name-defined]
    except Exception:
        return None


def _qx148_may_run(uid):
    checker = globals().get("_qxz_may_run")
    if callable(checker):
        with _cx148.suppress(Exception):
            return bool(checker(int(uid)))
    checker = globals().get("_qx99_may_run")
    if callable(checker):
        with _cx148.suppress(Exception):
            return bool(checker(int(uid)))
    return True


# ── argument parsing: "3" | "4-8" (Bengali digits ok) ────────────────────────
def _qx148_parse_args(tokens):
    """→ (start, end_or_None).  end None means 'till the last page'."""
    start = end = None
    for raw in tokens:
        text = str(raw or "").strip().translate(_QX148_BN)
        if not text:
            continue
        match = _re148.fullmatch(r"(\d{1,4})(?:\s*[-–—:]\s*(\d{1,4}))?", text)
        if match:
            start = int(match.group(1))
            if match.group(2):
                end = int(match.group(2))
            break
    if start is not None and end is not None and end < start:
        start, end = end, start
    return start, end


# ── PDF resolution: replied PDF, otherwise the last PDF the user sent ────────
def _qx148_pdf_file_id(message, context):
    reply = getattr(message, "reply_to_message", None)
    if reply is not None:
        document = getattr(reply, "document", None)
        name = str(getattr(document, "file_name", "") or "").lower() if document else ""
        mime = str(getattr(document, "mime_type", "") or "").lower() if document else ""
        if document is not None and (name.endswith(".pdf") or "pdf" in mime):
            remember = globals().get("_qxz_remember_pdf")
            if callable(remember):
                with _cx148.suppress(Exception):
                    remember(context, document)
            return str(getattr(document, "file_id", "") or ""), None
        # Replied to something that is NOT a PDF (photo/text) → hard error.
        return "", "not_pdf"
    cached = (getattr(context, "user_data", None) or {}).get("_qxz_last_pdf") or {}
    return str(cached.get("file_id") or ""), None


def _qx148_page_count(path):
    import fitz  # PyMuPDF

    document = fitz.open(path)
    try:
        return int(document.page_count or 0)
    finally:
        document.close()


# ── live-card bodies ──────────────────────────────────────────────────────────
def _qx148_ocr_body(state, pages, total_pages):
    return (
        "📖 পৃষ্ঠা <b>%d</b> পড়া হচ্ছে… (%d/%d)\n"
        "PDF-এ মোট পৃষ্ঠা: <b>%d</b>\n"
        "✅ সম্পন্ন পৃষ্ঠা: <b>%d</b>\n"
        "🔎 পাওয়া প্রশ্ন: <b>%d</b> • ➕ যোগ: <b>%d</b>\n"
        "সময়: <code>%s</code>"
        % (int(state.get("page") or 0), int(state.get("idx") or 0), len(pages),
           int(total_pages or 0), int(state.get("done_pages") or 0),
           int(state.get("found") or 0), int(state.get("added") or 0),
           _qx148_elapsed(state.get("started")))
    )


def _qx148_page_done_body(page, idx, total, found, added, dup, page_started):
    return (
        "✅ পৃষ্ঠা <b>%d</b> সম্পন্ন (%d/%d)\n"
        "🔎 পাওয়া: <b>%d</b> • ➕ যোগ: <b>%d</b> • ♻️ ডুপ্লিকেট: <b>%d</b>\n"
        "⏱ এই পৃষ্ঠায়: <code>%s</code>"
        % (int(page), int(idx), int(total), int(found), int(added), int(dup),
           _qx148_elapsed(page_started))
    )


# ── ⏹ cancel during the OCR phase (harvest phase uses the qx146 button) ─────
async def qx148_cb(update, context):
    query = getattr(update, "callback_query", None)
    data = str(getattr(query, "data", "") or "") if query is not None else ""
    if not data.startswith("qx148:"):
        return None
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    caller = int(getattr(getattr(query, "from_user", None), "id", 0) or 0)
    if action == "cancel" and len(parts) >= 3:
        owner = -1
        with _cx148.suppress(Exception):
            owner = int(parts[2])
        if caller != owner:
            with _cx148.suppress(Exception):
                await query.answer("এই বাটনটি আপনার জন্য নয়।", show_alert=True)
            raise ApplicationHandlerStop  # type: ignore[name-defined]
        _QX148_STOP[caller] = _t148.time()
        # If a page harvest is running right now, cancel it too.
        jobs = globals().get("_QX146_JOBS")
        if isinstance(jobs, dict):
            job = jobs.get(caller)
            if isinstance(job, dict):
                job["cancel"] = True
        with _cx148.suppress(Exception):
            await query.answer("⏹ বন্ধ হচ্ছে — এ পর্যন্ত যা তৈরি হয়েছে Buffer-এ থাকবে।")
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    with _cx148.suppress(Exception):
        await query.answer()
    raise ApplicationHandlerStop  # type: ignore[name-defined]


# ── main command ──────────────────────────────────────────────────────────────
async def qx148_cmd_genperpage(update, context):
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    uid = int(getattr(user, "id", 0) or 0)
    if not _qx148_may_run(uid):
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    raw = str(getattr(message, "text", "") or "").strip()
    tokens = list(getattr(context, "args", None) or []) or raw.split()[1:]
    start, end = _qx148_parse_args(tokens)
    if start is None:
        with _cx148.suppress(Exception):
            await message.reply_text(
                _qx148_box("PDF Page-by-Page Quiz", _QX148_HELP, "📄"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    file_id, pdf_error = _qx148_pdf_file_id(message, context)
    if pdf_error == "not_pdf":
        with _cx148.suppress(Exception):
            await message.reply_text(
                _qx148_box("শুধু PDF",
                           "এই কমান্ডটি শুধু <b>PDF</b> ফাইলের জন্য।\n"
                           "ছবির প্রশ্ন রূপান্তরের জন্য <code>.gen</code> ব্যবহার করুন।",
                           "⚠️"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    if not file_id:
        with _cx148.suppress(Exception):
            await message.reply_text(
                _qx148_box("PDF পাওয়া যায়নি", _QX148_HELP, "⚠️"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    # One generation at a time per user (the harvest engine shares a per-uid job slot).
    jobs = globals().get("_QX146_JOBS")
    if _QX148_RUNS.get(uid) or (isinstance(jobs, dict) and jobs.get(uid)):
        with _cx148.suppress(Exception):
            await message.reply_text(
                _qx148_box("অপেক্ষা করুন",
                           "আরেকটি জেনারেশন এখন চলছে — শেষ না হওয়া পর্যন্ত "
                           "নতুন রান শুরু করা যাবে না।", "⏳"),
                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    prep = None
    with _cx148.suppress(Exception):
        prep = await message.reply_text(
            _qx148_box("PDF Page-by-Page", "PDF ডাউনলোড হচ্ছে…", "📄"),
            parse_mode=ParseMode.HTML)  # type: ignore[name-defined]

    workdir = _tf148.mkdtemp(prefix="qx148_gpp_")
    local_path = _os148.path.join(workdir, "source.pdf")
    role = _role_of(uid)  # type: ignore[name-defined]
    _QX148_RUNS[uid] = True
    _QX148_STOP.pop(uid, None)
    ticker_task = None
    try:
        telegram_file = await context.bot.get_file(file_id)
        await telegram_file.download_to_drive(custom_path=local_path)
        total_pages = await _run_blocking(role, _qx148_page_count, local_path, timeout=60)  # type: ignore[name-defined]
        total_pages = int(total_pages or 0)
        if total_pages < 1:
            raise RuntimeError("PDF পড়া যায়নি — ফাইলটি নষ্ট হতে পারে।")
        if start > total_pages:
            raise RuntimeError(
                "এই PDF-এ মোট <b>%d</b>টি পৃষ্ঠা — <b>%d</b> নম্বর পৃষ্ঠা নেই।"
                % (total_pages, start))
        stop_page = int(end) if end else total_pages
        stop_page = min(stop_page, total_pages)
        clamped = False
        if stop_page - start + 1 > _QX148_MAX_PAGES:
            stop_page = start + _QX148_MAX_PAGES - 1
            clamped = True
        pages = list(range(start, stop_page + 1))
        if clamped:
            with _cx148.suppress(Exception):
                await message.reply_text(
                    _qx148_box("পৃষ্ঠা সীমা",
                               "এক রানে সর্বোচ্চ <b>%d</b> পৃষ্ঠা — এবার <b>%d–%d</b> "
                               "প্রসেস হবে।" % (_QX148_MAX_PAGES, start, stop_page),
                               "ℹ️"),
                    parse_mode=ParseMode.HTML)  # type: ignore[name-defined]

        with _cx148.suppress(Exception):
            if prep is not None:
                await prep.delete()
        prep = None

        run_state = {
            "phase": "ocr", "card": None, "page": start, "idx": 0,
            "started": _t148.time(), "found": 0, "added": 0, "dup": 0,
            "done_pages": 0,
        }
        totals = {"found": 0, "added": 0, "dup": 0, "cancelled": False}
        skipped = []

        async def _ocr_ticker():
            while True:
                await _a148.sleep(10.0)
                if run_state.get("phase") != "ocr":
                    continue
                card = run_state.get("card")
                if card is None:
                    continue
                with _cx148.suppress(Exception):
                    await card.edit_text(
                        _qx148_box("PDF Page-by-Page",
                                   _qx148_ocr_body(run_state, pages, total_pages),
                                   "📖"),
                        parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                        reply_markup=_qx148_cancel_kb(uid),
                    )

        ticker_task = _a148.ensure_future(_ocr_ticker())

        for idx, page in enumerate(pages, start=1):
            if _QX148_STOP.get(uid):
                totals["cancelled"] = True
                break
            run_state["page"] = page
            run_state["idx"] = idx
            run_state["phase"] = "ocr"
            page_card = None
            with _cx148.suppress(Exception):
                page_card = await message.reply_text(
                    _qx148_box("PDF Page-by-Page",
                               _qx148_ocr_body(run_state, pages, total_pages),
                               "📖"),
                    parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                    reply_markup=_qx148_cancel_kb(uid),
                )
            run_state["card"] = page_card
            page_started = _t148.time()
            sliced = None
            try:
                slicer = globals().get("_qxz_slice_pdf")
                if not callable(slicer):
                    raise RuntimeError("PDF slicer unavailable")
                sliced, _used, _tot = await _run_blocking(  # type: ignore[name-defined]
                    role, slicer, local_path, [page], timeout=90)
                ocr = await _run_blocking(  # type: ignore[name-defined]
                    role, _mistral_ocr_process_path, sliced, timeout=240)  # type: ignore[name-defined]
                ocr_pages = list((ocr or {}).get("pages") or [])
                raw_markdown = str((ocr or {}).get("raw_markdown") or "").strip()
                clean_text = raw_markdown
                with _cx148.suppress(Exception):
                    clean_text, _items = await _run_blocking(  # type: ignore[name-defined]
                        role, _ocr_pages_to_clean_text_and_items, ocr_pages, uid,  # type: ignore[name-defined]
                        timeout=240)
                clean_text = str(clean_text or raw_markdown or "").strip()
                if not clean_text:
                    skipped.append(page)
                    with _cx148.suppress(Exception):
                        if page_card is not None:
                            await page_card.edit_text(
                                _qx148_box("পৃষ্ঠা %d" % page,
                                           "⚠️ এই পৃষ্ঠায় পড়ার মতো লেখা পাওয়া যায়নি — "
                                           "এড়িয়ে যাওয়া হলো।", "⚠️"),
                                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
                    continue
                if _QX148_STOP.get(uid):
                    totals["cancelled"] = True
                    with _cx148.suppress(Exception):
                        if page_card is not None:
                            await page_card.edit_text(
                                _qx148_box("Cancelled",
                                           "⏹ পৃষ্ঠা %d রূপান্তরের আগেই বন্ধ করা হয়েছে।" % page,
                                           "⏹"),
                                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
                    break

                run_state["phase"] = "harvest"
                harvest = globals().get("_qxv_harvest")
                if not callable(harvest):
                    raise RuntimeError("harvest engine unavailable")
                added, dup, found = await harvest(
                    update, context, uid, clean_text, page_card,
                    "PDF page %d" % page)
                run_state["phase"] = "ocr"

                found_i = int(found or 0)
                cancelled = False
                if found_i < 0:
                    cancelled = True
                    found_i = 0
                cancelled_map = globals().get("_QX146_CANCELLED")
                if isinstance(cancelled_map, dict):
                    with _cx148.suppress(Exception):
                        if float(cancelled_map.get(uid, 0) or 0) >= page_started - 1:
                            cancelled = True
                if _QX148_STOP.get(uid):
                    cancelled = True
                added_i = int(added or 0)
                dup_i = int(dup or 0)
                totals["found"] += found_i
                totals["added"] += added_i
                totals["dup"] += dup_i
                run_state["found"] = totals["found"]
                run_state["added"] = totals["added"]
                run_state["dup"] = totals["dup"]
                run_state["done_pages"] = idx
                if cancelled:
                    totals["cancelled"] = True
                    break  # the harvest engine already turned the card into "Cancelled"
                if found_i == 0:
                    skipped.append(page)
                    with _cx148.suppress(Exception):
                        if page_card is not None:
                            await page_card.edit_text(
                                _qx148_box("পৃষ্ঠা %d" % page,
                                           "ℹ️ এই পৃষ্ঠায় প্রিন্টেড প্রশ্ন পাওয়া যায়নি — "
                                           "এড়িয়ে যাওয়া হলো।", "ℹ️"),
                                parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
                    continue
                with _cx148.suppress(Exception):
                    if page_card is not None:
                        await page_card.edit_text(
                            _qx148_box("পৃষ্ঠা %d সম্পন্ন" % page,
                                       _qx148_page_done_body(page, idx, len(pages),
                                                             found_i, added_i, dup_i,
                                                             page_started),
                                       "✅"),
                            parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                            reply_markup=None,
                        )
            except Exception as error:
                run_state["phase"] = "ocr"
                _qx148_log("genperpage page %s failed uid=%s: %s", page, uid, error, "warning")
                skipped.append(page)
                with _cx148.suppress(Exception):
                    if page_card is not None:
                        await page_card.edit_text(
                            _qx148_box("পৃষ্ঠা %d" % page,
                                       "⚠️ এই পৃষ্ঠায় সমস্যা হয়েছে — এড়িয়ে যাওয়া হলো।\n"
                                       "<code>%s</code>" % str(error)[:200], "⚠️"),
                            parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
                continue
            finally:
                run_state["card"] = None
                with _cx148.suppress(Exception):
                    if sliced and _os148.path.exists(sliced):
                        _os148.remove(sliced)

        run_state["phase"] = "done"

        # ── final summary ──
        total_buffer = 0
        with _cx148.suppress(Exception):
            total_buffer = int(buffer_count(uid) or 0)  # type: ignore[name-defined]
        done_count = int(run_state.get("done_pages") or 0)
        title = "PDF Page-by-Page বন্ধ" if totals["cancelled"] else "PDF Page-by-Page সম্পন্ন"
        emoji = "⏹" if totals["cancelled"] else "✅"
        body = (
            "📄 পৃষ্ঠা: <b>%d–%d</b> • সম্পন্ন: <b>%d/%d</b>\n"
            "🔎 মোট পাওয়া প্রশ্ন: <b>%d</b>\n"
            "➕ Buffer-এ যোগ: <b>%d</b>\n"
            "♻️ ডুপ্লিকেট বাদ: <b>%d</b>\n"
            % (pages[0], pages[-1], done_count, len(pages),
               totals["found"], totals["added"], totals["dup"])
        )
        if skipped:
            body += "⚠️ এড়িয়ে যাওয়া পৃষ্ঠা: <b>%s</b>\n" % ", ".join(str(p) for p in skipped)
        if totals["cancelled"]:
            body += "⏹ আপনি রান বন্ধ করেছেন — তৈরি প্রশ্নগুলো Buffer-এ আছে।\n"
        body += (
            "⏱ মোট সময়: <code>%s</code>\n"
            "📦 Buffer total: <b>%d</b>" % (_qx148_elapsed(run_state["started"]), total_buffer)
        )
        with _cx148.suppress(Exception):
            await message.reply_text(_qx148_box(title, body, emoji),
                                     parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        if int(totals["added"] or 0) > 0:
            card = globals().get("_send_pb_action_card")
            if callable(card):
                with _cx148.suppress(Exception):
                    await card(context, message.chat_id, uid, int(totals["added"]))
        _qx148_log("genperpage run done uid=%s pages=%s-%s added=%s found=%s cancelled=%s",
                   uid, pages[0], pages[-1], totals["added"], totals["found"],
                   totals["cancelled"])
    except Exception as error:
        _qx148_log("genperpage failed uid=%s: %s", uid, error, "warning")
        with _cx148.suppress(Exception):
            text = _qx148_box("PDF Page-by-Page ব্যর্থ", str(error)[:300], "⚠️")
            if prep is not None:
                await prep.edit_text(text, parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
            else:
                await message.reply_text(text, parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
    finally:
        _QX148_RUNS.pop(uid, None)
        if ticker_task is not None and not ticker_task.done():
            ticker_task.cancel()
            with _cx148.suppress(_a148.CancelledError, Exception):
                await ticker_task
        with _cx148.suppress(Exception):
            if _os148.path.exists(local_path):
                _os148.remove(local_path)
        with _cx148.suppress(Exception):
            _os148.rmdir(workdir)
    raise ApplicationHandlerStop  # type: ignore[name-defined]


# ── owner command menu ────────────────────────────────────────────────────────
def _qx148_install_owner_menu():
    sections = globals().get("PRIVATE_COMMAND_SECTIONS")
    if not isinstance(sections, dict) or not isinstance(sections.get("owner"), list):
        return
    with _cx148.suppress(Exception):
        if not any(str(row[0]) == "genperpage" for row in sections["owner"] if row):
            sections["owner"].append(
                ("genperpage", "PDF পৃষ্ঠা বাই পৃষ্ঠা সব প্রশ্ন quiz-এ"))
        sections["owner"].sort(key=lambda item: str(item[0]).lower())


_qx148_install_owner_menu()


# ── wiring ────────────────────────────────────────────────────────────────────
_qx148_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx148_prev_build_app() if callable(_qx148_prev_build_app) else None
    if app is None:
        return app
    with _cx148.suppress(Exception):
        register = globals().get("_register_dual_command")
        if callable(register):
            register(app, "genperpage", qx148_cmd_genperpage, group=-3400)
        else:
            app.add_handler(CommandHandler("genperpage", qx148_cmd_genperpage), group=-3400)  # type: ignore[name-defined]
            app.add_handler(_build_dot_command_handler("genperpage", qx148_cmd_genperpage), group=-3400)  # type: ignore[name-defined]
    with _cx148.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx148_cb, pattern=r"^qx148:"),  # type: ignore[name-defined]
            group=-3800,
        )
    # Re-push the owner menu (now including genperpage) on startup.
    with _cx148.suppress(Exception):
        _qx148_prev_pi = getattr(app, "post_init", None)

        async def _qx148_post_init(application):
            if callable(_qx148_prev_pi):
                with _cx148.suppress(Exception):
                    await _qx148_prev_pi(application)
            install_defaults = globals().get("install_default_command_scopes")
            refresh = globals().get("refresh_private_command_menu")
            owner_ids = globals().get("OWNER_IDS") or ()
            if callable(install_defaults):
                with _cx148.suppress(Exception):
                    await install_defaults(application)
            if not callable(refresh):
                return

            class _Shim:
                def __init__(self, bot):
                    self.bot = bot

            shim = _Shim(application.bot)
            for oid in owner_ids:
                with _cx148.suppress(Exception):
                    await refresh(shim, int(oid))

        app.post_init = _qx148_post_init
    _qx148_log(".genperpage wired (dot+slash), cancel callback + owner menu active")
    return app


_qx148_log("section 148 loaded — .genperpage page-by-page iterator ready")