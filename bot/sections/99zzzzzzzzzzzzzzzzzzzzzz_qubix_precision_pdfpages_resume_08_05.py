# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 113 — QUIZ PRECISION · TRUE RESUME · PDF PAGE GENERATION (2026-08-05)
#
#   1. Decimal-safe option text.  "5.04" / "1.0 × 10⁻⁴" were losing their
#      integer part because the option cleaner treated "5." as an A/B/1/2 list
#      label.  Labels are still stripped; decimals never are.
#   2. Every generated quiz now carries exactly 4 options, and the marked
#      answer is reconciled against the explanation (the value the explanation
#      actually proves wins).  Unrepairable items are dropped so the provider
#      cascade keeps trying instead of publishing a wrong quiz.
#   3. /resumequiz truly continues an interrupted publish run — the remaining
#      rows, same chat / topic / prefix / explanation link.
#   4. Math + image + text sources that produced "Added: 0" get a math-aware
#      rescue pass (lenient repair + dedicated prompt) before giving up.
#   5. NEW: /pdfpages — generate quizzes from chosen pages of a PDF.
#   6. scoreon / scoreoff / scon / scoff retired; /score (with its buttons) stays.
#
# Loaded last by bot/__main__.py — do not import directly.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cxZ
import os as _osZ
import re as _reZ
import tempfile as _tfZ
import time as _tZ

from telegram.ext import ApplicationHandlerStop as _AHSZ
from telegram.constants import ParseMode as _PMZ


def _qxz_log(message, level="info"):
    with _cxZ.suppress(Exception):
        getattr(logger, level)("[QX113] %s", message)  # type: ignore[name-defined]


def _qxz_box(title, body, emoji="✅"):
    with _cxZ.suppress(Exception):
        return ui_box_html(title, body, emoji=emoji)  # type: ignore[name-defined]
    return f"{emoji} <b>{title}</b>\n{body}"


# ═════════════════════════════════════════════════════════════════════════════
# 1) Decimal-safe option cleaning
# ═════════════════════════════════════════════════════════════════════════════
_QXZ_DECIMAL = _reZ.compile(r"^\s*[\(\[]?\s*[-−+]?\s*[0-9০-৯]+\s*[.．]\s*[0-9০-৯]")

_qxz_prev_clean = globals().get("_qx107_clean_math_text")

if callable(_qxz_prev_clean):
    def _qx107_clean_math_text(value, *, option=False):  # noqa: F811
        raw = str(value or "")
        if option and _QXZ_DECIMAL.match(raw.strip()):
            # A leading "5." here is a decimal point, not an option label.
            text = _qxz_prev_clean(raw, option=False)
            return _reZ.sub(r"\s+", " ", str(text or "")).strip()
        return _qxz_prev_clean(raw, option=option)

    globals()["_qx107_clean_math_text"] = _qx107_clean_math_text
    _qxz_log("decimal-safe option cleaner installed")


# ═════════════════════════════════════════════════════════════════════════════
# 2) Four options + answer/explanation reconciliation
# ═════════════════════════════════════════════════════════════════════════════
_QXZ_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_QXZ_NUM = _reZ.compile(r"[-−+]?\d+(?:[.,]\d+)?(?:\s*[×xX*]\s*10\s*[\^]?\s*[-−]?\s*\d+)?")


def _qxz_plain(text):
    """Bengali digits + superscripts flattened to plain ASCII math."""
    raw = str(text or "").translate(_QXZ_BN_DIGITS)
    return (raw.replace("⁻", "-").replace("−", "-")
              .replace("⁰", "0").replace("¹", "1").replace("²", "2").replace("³", "3")
              .replace("⁴", "4").replace("⁵", "5").replace("⁶", "6").replace("⁷", "7")
              .replace("⁸", "8").replace("⁹", "9"))


def _qxz_num_value(text):
    """Best-effort numeric value of an option/answer string (handles ×10^n)."""
    raw = _qxz_plain(text)
    match = _reZ.search(r"[-+]?\d+(?:\.\d+)?", raw)
    if not match:
        return None
    try:
        value = float(match.group(0))
    except Exception:
        return None
    power = _reZ.search(r"10\s*\^?\s*([-+]?\d+)", raw[match.end():])
    if power:
        with _cxZ.suppress(Exception):
            value *= 10.0 ** int(power.group(1))
    return value


def _qxz_close(a, b):
    if a is None or b is None:
        return False
    if a == b:
        return True
    scale = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / scale < 0.005


def _qxz_reconcile_answer(row):
    """Trust the explanation: if it proves another option, move the answer."""
    options = list(row.get("options") or [])
    explanation = str(row.get("explanation") or "")
    if len(options) < 2 or not explanation.strip():
        return row
    answer = int(row.get("answer") or 1)

    # Exact textual mention of a whole option (strongest signal).
    flat = _reZ.sub(r"\s+", " ", explanation).casefold()
    text_hits = [
        index for index, option in enumerate(options, start=1)
        if len(_reZ.sub(r"\s+", "", str(option))) >= 3
        and _reZ.sub(r"\s+", " ", str(option)).casefold() in flat
    ]
    if len(text_hits) == 1 and text_hits[0] != answer:
        row["answer"] = text_hits[0]
        return row

    # Numeric result: the LAST number of the explanation is the computed value.
    numbers = _QXZ_NUM.findall(_qxz_plain(explanation))
    final_value = _qxz_num_value(numbers[-1]) if numbers else None
    if final_value is None:
        return row
    matches = [
        index for index, option in enumerate(options, start=1)
        if _qxz_close(_qxz_num_value(option), final_value)
    ]
    if len(matches) == 1 and matches[0] != answer:
        row["answer"] = matches[0]
    return row


def _qxz_pad_options(row):
    """Repair a 3-option numeric MCQ instead of losing the whole item."""
    options = [str(o or "").strip() for o in (row.get("options") or []) if str(o or "").strip()]
    if len(options) >= 4 or len(options) < 3:
        return None
    values = [_qxz_num_value(o) for o in options]
    if any(value is None for value in values):
        return None
    base = max(values, key=abs)
    for factor in (2.0, 0.5, 3.0, 1.5, 10.0):
        candidate = base * factor
        if all(not _qxz_close(candidate, value) for value in values):
            text = ("%g" % candidate)
            if text not in options:
                options.append(text)
                row["options"] = options
                return row
    return None


def _qxz_finalise(row, *, allow_repair=False):
    if not isinstance(row, dict):
        return None
    options = [str(o or "").strip() for o in (row.get("options") or []) if str(o or "").strip()]
    unique, seen = [], set()
    for option in options:
        key = _reZ.sub(r"\s+", "", option).casefold()
        if key and key not in seen:
            seen.add(key)
            unique.append(option)
    row["options"] = unique
    if len(unique) < 4:
        if not allow_repair:
            return None
        row = _qxz_pad_options(row)
        if row is None:
            return None
        unique = row["options"]
    answer = int(row.get("answer") or 1)
    if len(unique) > 4:
        # Keep the correct option inside the first four.
        correct = unique[answer - 1] if 1 <= answer <= len(unique) else unique[0]
        trimmed = [o for o in unique[:4]]
        if correct not in trimmed:
            trimmed[3] = correct
        row["options"] = trimmed
        row["answer"] = trimmed.index(correct) + 1
    elif not (1 <= answer <= len(unique)):
        row["answer"] = 1
    return _qxz_reconcile_answer(row)


def _qxz_wrap_normaliser(name, *, allow_repair=False):
    previous = globals().get(name)
    if not callable(previous) or getattr(previous, "_qxz_wrapped", False):
        return
    # In lenient (rescue) mode we bypass earlier strict normalisers so a
    # 3-option numeric item can be repaired instead of silently dropped.
    base = globals().get("_old_normalise_88") or previous

    def wrapper(item, *args, **kwargs):
        lenient = bool(globals().get("_QXZ_LENIENT"))
        try:
            row = (base if lenient else previous)(item, *args, **kwargs)
        except Exception:
            row = None
        if row is None and lenient and base is not previous:
            with _cxZ.suppress(Exception):
                row = previous(item, *args, **kwargs)
        if not isinstance(row, dict):
            return None
        return _qxz_finalise(row, allow_repair=lenient)

    wrapper._qxz_wrapped = True  # type: ignore[attr-defined]
    with _cxZ.suppress(Exception):
        wrapper.__name__ = name
    globals()[name] = wrapper
    _qxz_log(f"quiz validator installed on {name}")


_QXZ_LENIENT = False
globals()["_QXZ_LENIENT"] = False

for _qxz_name in ("_normalise_mcq_74", "_qx107_normalise_mcq"):
    _qxz_wrap_normaliser(_qxz_name)


# ═════════════════════════════════════════════════════════════════════════════
# 3) Math / image / text rescue so a source never returns "Added: 0"
# ═════════════════════════════════════════════════════════════════════════════
_QXZ_MATH_HINT = (
    "The source is mathematical/scientific. Build fully solvable NEW MCQs on the same "
    "topics (limits, derivatives, integration, trigonometry, algebra, chemistry numericals). "
    "Rules: exactly 4 options; write complete numbers (2.349, 5.04 — never drop the integer "
    "part); no A/B/ক/খ labels inside options; readable Unicode math (√, ², ₁, π, θ, ×10⁻⁴); "
    "the explanation must end with the same value as the correct option. "
    "Return valid JSON even if part of the source is unclear."
)


def _qxz_source_text(ocr_ctx):
    if isinstance(ocr_ctx, dict):
        for key in ("clean_text", "raw_markdown", "text", "source_text"):
            value = str(ocr_ctx.get(key) or "").strip()
            if value:
                return value
        chunks = []
        for item in list(ocr_ctx.get("items") or [])[:40]:
            with _cxZ.suppress(Exception):
                chunks.append(str(item.get("questions") or item.get("question") or ""))
        return "\n".join(c for c in chunks if c).strip()
    return str(ocr_ctx or "").strip()


def _qxz_rescue_sync(ocr_ctx, desired):
    source = _qxz_source_text(ocr_ctx)
    if not source:
        return []
    batcher = globals().get("_generate_batch_fast_74")
    if not callable(batcher):
        return []
    desired = max(1, min(int(desired or 5), 200))
    out, seen = [], set()
    globals()["_QXZ_LENIENT"] = True
    try:
        for _ in range(5):
            if len(out) >= desired:
                break
            need = min(6, desired - len(out))
            avoid = _QXZ_MATH_HINT + "\nAvoid repeating:\n" + "\n".join(
                "- " + row["question"][:120] for row in out[-15:]
            )
            rows = []
            with _cxZ.suppress(Exception):
                rows = list(batcher(source, need, avoid_text=avoid) or [])
            if not rows:
                continue
            for row in rows:
                clean = _qxz_finalise(dict(row), allow_repair=True)
                if not clean:
                    continue
                signature = _reZ.sub(r"\W+", "", clean["question"].casefold())[:110]
                if not signature or signature in seen:
                    continue
                seen.add(signature)
                out.append(clean)
                if len(out) >= desired:
                    break
    finally:
        globals()["_QXZ_LENIENT"] = False
    return out


def _qxz_store_rows(uid, rows, mode="std"):
    added = dup = 0
    seen = set()
    with _cxZ.suppress(Exception):
        for _row_id, payload in (buffer_list(uid, limit=99999) or []):  # type: ignore[name-defined]
            seen.add(_fp_question(payload))  # type: ignore[name-defined]
    for row in rows or []:
        try:
            options = [str(o or "").strip() for o in (row.get("options") or []) if str(o or "").strip()][:5]
            answer = int(row.get("answer") or 1)
            question = str(row.get("question") or "").strip()
            if not question or len(options) < 4 or not (1 <= answer <= len(options)):
                continue
            payload = {
                "questions": question, "answer": answer,
                "explanation": str(row.get("explanation") or "")[:200],
                "type": 1, "section": 1, "source": f"gen_{mode}",
            }
            for index in range(5):
                payload[f"option{index + 1}"] = options[index] if index < len(options) else ""
            with _cxZ.suppress(Exception):
                payload = _enforce_option_parity(payload)  # type: ignore[name-defined]
            fingerprint = _fp_question(payload)  # type: ignore[name-defined]
            if fingerprint in seen:
                dup += 1
                continue
            if buffer_count(uid) >= MAX_BUFFERED_QUESTIONS:  # type: ignore[name-defined]
                break
            with _cxZ.suppress(Exception):
                if not explain_mode_on(uid):  # type: ignore[name-defined]
                    payload["explanation"] = ""
            buffer_add(uid, payload)  # type: ignore[name-defined]
            seen.add(fingerprint)
            added += 1
        except Exception:
            continue
    return added, dup


_qxz_prev_gen_buffer = globals().get("_generate_to_buffer_59")

if callable(_qxz_prev_gen_buffer):
    async def _generate_to_buffer_59(update, context, ocr_ctx, uid, count, mode="std"):  # noqa: F811
        added, dup = 0, 0
        with _cxZ.suppress(Exception):
            added, dup = await _qxz_prev_gen_buffer(update, context, ocr_ctx, uid, count, mode)
        if int(added or 0) > 0:
            return added, dup
        rows = []
        with _cxZ.suppress(Exception):
            rows = await _run_blocking(  # type: ignore[name-defined]
                _role_of(uid), _qxz_rescue_sync, ocr_ctx, count,  # type: ignore[name-defined]
                timeout=max(60, min(240, int(count or 10) * 6)),
            )
        if not rows:
            return added, dup
        extra_added, extra_dup = _qxz_store_rows(uid, rows, mode)
        _qxz_log(f"rescue generation uid={uid} added={extra_added} dup={extra_dup}")
        return int(added or 0) + extra_added, int(dup or 0) + extra_dup

    globals()["_generate_to_buffer_59"] = _generate_to_buffer_59


# ═════════════════════════════════════════════════════════════════════════════
# 4) True /resumequiz — continue the interrupted publish run
# ═════════════════════════════════════════════════════════════════════════════
_QXZ_RESUME: dict = {}      # uid -> remaining publish job
globals()["_QXZ_RESUME"] = _QXZ_RESUME

_qxz_prev_post_buffer = globals().get("_post_buffer_to_chat")

if callable(_qxz_prev_post_buffer):
    async def _post_buffer_to_chat(context, admin_id, chat_id, items, thread_id=None,  # noqa: F811
                                   group_prefix="", group_expl_link=""):
        rows = list(items or [])
        uid = int(admin_id or 0)
        _QXZ_RESUME.pop(uid, None)
        ok, fail, first_id = await _qxz_prev_post_buffer(
            context, admin_id, chat_id, rows, thread_id, group_prefix, group_expl_link,
        )
        done = int(ok or 0) + int(fail or 0)
        if uid and rows and done < len(rows):
            _QXZ_RESUME[uid] = {
                "chat_id": chat_id, "thread_id": thread_id,
                "prefix": group_prefix, "link": group_expl_link,
                "rows": rows[done:], "posted": int(ok or 0), "ts": _tZ.time(),
            }
            _qxz_log(f"resume job stored uid={uid} remaining={len(rows) - done}")
        return ok, fail, first_id

    globals()["_post_buffer_to_chat"] = _post_buffer_to_chat


def _qxz_may_run(uid):
    checker = globals().get("_qx99_may_run")
    if callable(checker):
        with _cxZ.suppress(Exception):
            return bool(checker(int(uid)))
    return True


_qxz_prev_resume_cmd = globals().get("qx99_cmd_resumequiz")


async def qx99_cmd_resumequiz(update, context):  # noqa: F811
    message = getattr(update, "effective_message", None)
    uid = 0
    with _cxZ.suppress(Exception):
        uid = int(globals()["_qx99_uid"](update))
    if not uid:
        with _cxZ.suppress(Exception):
            uid = int(update.effective_user.id)
    if message is None or not _qxz_may_run(uid):
        raise _AHSZ

    # Always clear every stop flag first.
    with _cxZ.suppress(Exception):
        globals()["_QX99_STOP"].discard(uid)
    with _cxZ.suppress(Exception):
        globals()["_stop_clear_81"](uid)
    with _cxZ.suppress(Exception):
        globals()["_stop_clear_81"](None)

    job = _QXZ_RESUME.pop(uid, None)
    if not job or not job.get("rows"):
        if callable(_qxz_prev_resume_cmd):
            return await _qxz_prev_resume_cmd(update, context)
        with _cxZ.suppress(Exception):
            await message.reply_text(
                _qxz_box("Run Cleared", "Stop flag সরানো হয়েছে — এখন আবার পোস্ট করা যাবে।", "▶️"),
                parse_mode=_PMZ.HTML,
            )
        raise _AHSZ

    rows = list(job.get("rows") or [])
    with _cxZ.suppress(Exception):
        await message.reply_text(
            _qxz_box(
                "Resuming Run",
                f"যেখানে থেমেছিল ঠিক সেখান থেকেই বাকি <b>{len(rows)}</b>টি quiz যাচ্ছে…",
                "▶️",
            ),
            parse_mode=_PMZ.HTML,
        )
    poster = globals().get("_post_buffer_to_chat")
    ok = fail = 0
    with _cxZ.suppress(Exception):
        ok, fail, _first = await poster(
            context, uid, job.get("chat_id"), rows, job.get("thread_id"),
            job.get("prefix") or "", job.get("link") or "",
        )
    with _cxZ.suppress(Exception):
        await message.reply_text(
            _qxz_box(
                "Resume Complete",
                (f"✅ এই ধাপে পাঠানো: <b>{int(ok or 0)}</b>\n"
                 f"⚠️ ব্যর্থ: <b>{int(fail or 0)}</b>\n"
                 f"📦 আগে পাঠানো হয়েছিল: <b>{int(job.get('posted') or 0)}</b>"),
                "✅",
            ),
            parse_mode=_PMZ.HTML,
        )
    raise _AHSZ


globals()["qx99_cmd_resumequiz"] = qx99_cmd_resumequiz
globals()["cmd_resumequiz_81"] = qx99_cmd_resumequiz


# ═════════════════════════════════════════════════════════════════════════════
# 5) /pdfpages — quizzes from chosen pages of a PDF
# ═════════════════════════════════════════════════════════════════════════════
QXZ_PDF_MAX_PAGES = 20

QXZ_PDF_HELP = (
    "<b>ব্যবহার</b>\n"
    "PDF ফাইলটিতে <b>reply</b> করে লিখুন:\n"
    "<code>/pdfpages 3-7 20</code> — ৩ থেকে ৭ নম্বর পৃষ্ঠা থেকে ২০টি quiz\n"
    "<code>/pdfpages 2,5,9</code> — শুধু ঐ পৃষ্ঠাগুলো (default 10টি quiz)\n"
    "<code>/pdfpages 4</code> — শুধু ৪ নম্বর পৃষ্ঠা\n\n"
    f"একবারে সর্বোচ্চ <b>{QXZ_PDF_MAX_PAGES}</b> পৃষ্ঠা।\n"
    "সদ্য পাঠানো PDF থাকলে reply ছাড়াও কাজ করবে।"
)


def _qxz_parse_pages(tokens):
    pages, count = [], 0
    for token in tokens:
        text = str(token or "").strip().translate(_QXZ_BN_DIGITS)
        if not text:
            continue
        if _reZ.fullmatch(r"\d{1,3}", text) and pages:
            count = int(text)
            continue
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            span = _reZ.fullmatch(r"(\d{1,4})\s*[-–—:]\s*(\d{1,4})", part)
            if span:
                start, end = int(span.group(1)), int(span.group(2))
                if start > end:
                    start, end = end, start
                pages.extend(range(start, min(end, start + QXZ_PDF_MAX_PAGES - 1) + 1))
            elif _reZ.fullmatch(r"\d{1,4}", part):
                pages.append(int(part))
    ordered = []
    for page in pages:
        if page >= 1 and page not in ordered:
            ordered.append(page)
    return ordered[:QXZ_PDF_MAX_PAGES], (count if count > 0 else 10)


def _qxz_slice_pdf(source_path, pages):
    """Build a small PDF containing only the requested pages."""
    import fitz  # PyMuPDF

    document = fitz.open(source_path)
    try:
        total = document.page_count
        wanted = [p for p in pages if 1 <= p <= total]
        if not wanted:
            raise RuntimeError(f"এই PDF-এ {total}টি পৃষ্ঠা আছে — চাওয়া পৃষ্ঠা পাওয়া যায়নি।")
        out = fitz.open()
        try:
            for page in wanted:
                out.insert_pdf(document, from_page=page - 1, to_page=page - 1)
            target = _osZ.path.join(_tfZ.mkdtemp(prefix="qxz_pdfpages_"), "selected.pdf")
            out.save(target)
        finally:
            out.close()
    finally:
        document.close()
    return target, wanted, total


def _qxz_remember_pdf(context, document):
    with _cxZ.suppress(Exception):
        context.user_data["_qxz_last_pdf"] = {
            "file_id": document.file_id,
            "name": getattr(document, "file_name", "") or "document.pdf",
            "ts": _tZ.time(),
        }


async def qxz_track_pdf(update, context):
    document = getattr(getattr(update, "effective_message", None), "document", None)
    name = str(getattr(document, "file_name", "") or "").lower()
    mime = str(getattr(document, "mime_type", "") or "").lower()
    if document is not None and (name.endswith(".pdf") or "pdf" in mime):
        _qxz_remember_pdf(context, document)
    return None


async def qxz_cmd_pdfpages(update, context):
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        raise _AHSZ
    uid = int(user.id)
    if not _qxz_may_run(uid):
        raise _AHSZ

    raw = (getattr(message, "text", "") or "").strip()
    tokens = raw.split()[1:]
    pages, count = _qxz_parse_pages(tokens)
    if not pages:
        with _cxZ.suppress(Exception):
            await message.reply_text(
                _qxz_box("PDF Page Quiz", QXZ_PDF_HELP, "📄"), parse_mode=_PMZ.HTML
            )
        raise _AHSZ

    reply = getattr(message, "reply_to_message", None)
    document = getattr(reply, "document", None) if reply is not None else None
    file_id = getattr(document, "file_id", "") if document is not None else ""
    if document is not None:
        _qxz_remember_pdf(context, document)
    if not file_id:
        cached = (context.user_data or {}).get("_qxz_last_pdf") or {}
        file_id = str(cached.get("file_id") or "")
    if not file_id:
        with _cxZ.suppress(Exception):
            await message.reply_text(
                _qxz_box("PDF পাওয়া যায়নি", QXZ_PDF_HELP, "⚠️"), parse_mode=_PMZ.HTML
            )
        raise _AHSZ

    label = ", ".join(str(p) for p in pages)
    status = None
    with _cxZ.suppress(Exception):
        status = await message.reply_text(
            _qxz_box("PDF Reading", f"পৃষ্ঠা: <b>{label}</b>\nটার্গেট: <b>{count}</b>টি quiz\nপড়া হচ্ছে…", "📄"),
            parse_mode=_PMZ.HTML,
        )

    workdir = _tfZ.mkdtemp(prefix="qxz_pdfsrc_")
    local_path = _osZ.path.join(workdir, "source.pdf")
    try:
        telegram_file = await context.bot.get_file(file_id)
        await telegram_file.download_to_drive(custom_path=local_path)
        sliced, used, total = await _run_blocking(  # type: ignore[name-defined]
            _role_of(uid), _qxz_slice_pdf, local_path, pages, timeout=90  # type: ignore[name-defined]
        )
        with _cxZ.suppress(Exception):
            if status is not None:
                await status.edit_text(
                    _qxz_box("PDF Scanning", f"পৃষ্ঠা: <b>{', '.join(str(p) for p in used)}</b> / মোট {total}\nলেখা পড়া হচ্ছে…", "🔎"),
                    parse_mode=_PMZ.HTML,
                )
        ocr = await _run_blocking(  # type: ignore[name-defined]
            _role_of(uid), _mistral_ocr_process_path, sliced, timeout=240  # type: ignore[name-defined]
        )
        ocr_pages = list((ocr or {}).get("pages") or [])
        raw_markdown = str((ocr or {}).get("raw_markdown") or "").strip()
        clean_text, source_items = raw_markdown, []
        with _cxZ.suppress(Exception):
            clean_text, source_items = await _run_blocking(  # type: ignore[name-defined]
                _role_of(uid), _ocr_pages_to_clean_text_and_items, ocr_pages, uid, timeout=240  # type: ignore[name-defined]
            )
        clean_text = str(clean_text or raw_markdown or "").strip()
        if not clean_text:
            raise RuntimeError("এই পৃষ্ঠাগুলো থেকে পড়ার মতো লেখা পাওয়া যায়নি।")

        ocr_ctx = {
            "raw_markdown": raw_markdown,
            "clean_text": clean_text,
            "items": list(source_items or []),
            "page_count": len(used),
            "source_label": f"PDF page {', '.join(str(p) for p in used)}",
        }
        with _cxZ.suppress(Exception):
            if status is not None:
                await status.edit_text(
                    _qxz_box("Generating", f"<b>{count}</b>টি নতুন quiz তৈরি হচ্ছে…", "🧠"),
                    parse_mode=_PMZ.HTML,
                )
        added, dup = await globals()["_generate_to_buffer_59"](
            update, context, ocr_ctx, uid, count, "std"
        )
        total_buffer = 0
        with _cxZ.suppress(Exception):
            total_buffer = int(buffer_count(uid))  # type: ignore[name-defined]
        body = (
            f"📄 Source: <b>PDF page {', '.join(str(p) for p in used)}</b>\n"
            f"➕ Added: <b>{int(added or 0)}</b>\n"
            f"♻️ Duplicates skipped: <b>{int(dup or 0)}</b>\n"
            f"📦 Buffer total: <b>{total_buffer}</b>"
        )
        if not int(added or 0):
            body += "\n\nএই পৃষ্ঠাগুলো থেকে নতুন unique quiz পাওয়া যায়নি — অন্য পৃষ্ঠা দিন।"
        with _cxZ.suppress(Exception):
            if status is not None:
                await status.edit_text(
                    _qxz_box("Quiz Ready" if added else "No New Quiz", body, "✅" if added else "ℹ️"),
                    parse_mode=_PMZ.HTML,
                )
            else:
                await message.reply_text(
                    _qxz_box("Quiz Ready" if added else "No New Quiz", body, "✅" if added else "ℹ️"),
                    parse_mode=_PMZ.HTML,
                )
    except Exception as error:
        _qxz_log(f"pdfpages failed uid={uid}: {error}", "warning")
        text = _qxz_box("PDF Page Quiz ব্যর্থ", str(error)[:300], "⚠️")
        with _cxZ.suppress(Exception):
            if status is not None:
                await status.edit_text(text, parse_mode=_PMZ.HTML)
            else:
                await message.reply_text(text, parse_mode=_PMZ.HTML)
    finally:
        with _cxZ.suppress(Exception):
            if _osZ.path.exists(local_path):
                _osZ.remove(local_path)
    raise _AHSZ


# ═════════════════════════════════════════════════════════════════════════════
# 6) Retire scoreon / scoreoff / scon / scoff — keep /score with its buttons
# ═════════════════════════════════════════════════════════════════════════════
_QXZ_RETIRED = {"scoreon", "scoreoff", "scon", "scoff"}


async def qxz_cmd_retired_score(update, context):
    message = getattr(update, "effective_message", None)
    with _cxZ.suppress(Exception):
        await message.reply_text(
            _qxz_box(
                "Score Control",
                "এই কমান্ডটি সরানো হয়েছে। এখন শুধু <code>/score</code> দিন — "
                "ওখানেই বাটন দিয়ে চালু/বন্ধ করা যাবে।",
                "🏆",
            ),
            parse_mode=_PMZ.HTML,
        )
    raise _AHSZ


with _cxZ.suppress(Exception):
    _qxz_ws = globals().get("QX_WORKSPACE_COMMANDS")
    if isinstance(_qxz_ws, set):
        _qxz_ws -= _QXZ_RETIRED
        _qxz_ws |= {"pdfpages", "score", "stopquiz", "resumequiz"}

with _cxZ.suppress(Exception):
    _qxz_retired_set = globals().get("QX_RETIRED_USER_COMMANDS")
    if isinstance(_qxz_retired_set, set):
        _qxz_retired_set |= _QXZ_RETIRED
        _qxz_retired_set.discard("pdfpages")


def _qxz_fix_menu(list_name):
    menu = globals().get(list_name)
    if not isinstance(menu, list):
        return
    menu[:] = [item for item in menu if not (item and str(item[0]) in _QXZ_RETIRED)]
    if not any(str(item[0]) == "pdfpages" for item in menu if item):
        menu.append(("pdfpages", "PDF-এর নির্দিষ্ট পৃষ্ঠা থেকে quiz"))


for _qxz_menu in ("QX97_USER_MENU_COMMANDS", "QX94_USER_MENU_COMMANDS", "QX94_OWNER_MENU_COMMANDS"):
    with _cxZ.suppress(Exception):
        _qxz_fix_menu(_qxz_menu)

with _cxZ.suppress(Exception):
    registry = globals().get("COMMAND_ALIAS_REGISTRY")
    if isinstance(registry, dict):
        for _qxz_key in list(registry.keys()):
            if str(_qxz_key) in _QXZ_RETIRED:
                registry.pop(_qxz_key, None)

with _cxZ.suppress(Exception):
    sections = globals().get("PRIVATE_COMMAND_SECTIONS")
    if isinstance(sections, dict):
        for _qxz_sec, _qxz_items in list(sections.items()):
            with _cxZ.suppress(Exception):
                sections[_qxz_sec] = [
                    item for item in _qxz_items if str(item[0]) not in _QXZ_RETIRED
                ]

# Command sheets: drop the retired lines, advertise the new PDF command.
_QXZ_CARD_BLOCK = (
    "\n\n📄 <b>PDF page quiz</b>\n"
    "<code>/pdfpages 3-7 20</code> — PDF-এ reply করে নির্দিষ্ট পৃষ্ঠা থেকে quiz\n"
    "🏆 <code>/score</code> — score reply চালু/বন্ধ (বাটন দিয়ে)"
)

for _qxz_card in (
    "QX95_USER_COMMANDS_CARD", "QX94_USER_COMMANDS_CARD",
    "QX93_COMMANDS_CARD", "QX94_OWNER_CARD",
):
    with _cxZ.suppress(Exception):
        card = globals().get(_qxz_card)
        if isinstance(card, str) and card:
            card = card.replace("<code>.scon</code> / <code>.scoff</code> — score reply", "")
            if "/pdfpages" not in card:
                card = card + _QXZ_CARD_BLOCK
            globals()[_qxz_card] = card


# ═════════════════════════════════════════════════════════════════════════════
# 7) Wiring — highest priority so the new behaviour always wins
# ═════════════════════════════════════════════════════════════════════════════
_qxz_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qxz_prev_build_app() if callable(_qxz_prev_build_app) else None
    if app is None:
        return app

    register = globals().get("_register_dual_command")
    for name, callback in (
        ("pdfpages", qxz_cmd_pdfpages),
        ("pdfpage", qxz_cmd_pdfpages),
        ("resumequiz", qx99_cmd_resumequiz),
    ):
        with _cxZ.suppress(Exception):
            if callable(register):
                register(app, name, callback, group=-3000)
            else:
                app.add_handler(CommandHandler(name, callback), group=-3000)  # type: ignore[name-defined]

    for name in sorted(_QXZ_RETIRED):
        with _cxZ.suppress(Exception):
            if callable(register):
                register(app, name, qxz_cmd_retired_score, group=-3000)
            else:
                app.add_handler(CommandHandler(name, qxz_cmd_retired_score), group=-3000)  # type: ignore[name-defined]

    with _cxZ.suppress(Exception):
        app.add_handler(
            MessageHandler(filters.Document.ALL, qxz_track_pdf),  # type: ignore[name-defined]
            group=-3200,
        )

    _qxz_log("precision pass wired (pdfpages, true resume, score cleanup)")
    return app


_qxz_log("section 113 loaded")
