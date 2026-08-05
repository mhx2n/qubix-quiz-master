# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 117 — VERBATIM QUESTION HARVEST · PDF PAGE RANGE .gen · BANGLA LOCK
#              (2026-08-05)
#
#   1. Source-language lock for generation: a Bangla page (even a math page
#      full of symbols) can no longer produce English quizzes.
#   2. NEW  .gen (no count) on a question image / PDF / OCR result →
#      every question printed on that source is converted to a quiz verbatim.
#      A printed answer + explanation is preserved; a missing one is solved
#      and supplied by AI.
#   3. NEW  .gen 1-5 / .gen 6-10 / .gen 2,4,7 on a PDF →
#      all questions of exactly those pages go to the buffer. Repeating with
#      the next range appends the next pages.
#   4. /pdfpages is available in Student access as well as Master access.
#
# Loaded last by bot/__main__.py — do not import directly.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cxV
import os as _osV
import re as _reV
import tempfile as _tfV


def _qxv_log(message, level="info"):
    with _cxV.suppress(Exception):
        getattr(logger, level)("[QX117] %s", message)  # type: ignore[name-defined]


def _qxv_box(title, body, emoji="✅"):
    with _cxV.suppress(Exception):
        return ui_box_html(title, body, emoji=emoji)  # type: ignore[name-defined]
    return f"{emoji} <b>{title}</b>\n{body}"


_QXV_BN = _reV.compile(r"[\u0980-\u09FF]")
_QXV_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


# ═════════════════════════════════════════════════════════════════════════════
# 1) Language: follow the source script, never silently switch to English
# ═════════════════════════════════════════════════════════════════════════════
_qxv_prev_lang = globals().get("_generation_lang_88")


def _generation_lang_88(source=""):  # noqa: F811
    raw = str(source or "")
    # An explicit choice always wins.
    active = str(globals().get("_active_lang_81") or "").lower()
    if active in ("bn", "en"):
        return active
    chooser = globals().get("_quiz_lang_78")
    if callable(chooser):
        with _cxV.suppress(Exception):
            chosen = str(chooser() or "").lower()
            if chosen in ("bn", "en"):
                return chosen
    lang = "bn"
    if callable(_qxv_prev_lang):
        with _cxV.suppress(Exception):
            lang = str(_qxv_prev_lang(raw) or "bn").lower()
    # Math/science OCR is symbol heavy: a handful of Bangla characters is
    # already proof that the printed source is Bangla.
    if lang != "bn" and len(_QXV_BN.findall(raw)) >= 4:
        return "bn"
    return lang


globals()["_generation_lang_88"] = _generation_lang_88

with _cxV.suppress(Exception):
    globals()["_QXZ_MATH_HINT"] = (
        str(globals().get("_QXZ_MATH_HINT") or "")
        + " LANGUAGE: write the stem, the wording of every option and the whole "
          "explanation in the SAME language/script as the source page — a Bangla "
          "source must produce Bangla quizzes (only symbols, variables and units "
          "stay in Latin)."
    )

_qxv_log("source-language lock installed")


# ═════════════════════════════════════════════════════════════════════════════
# 2) Verbatim question harvest
# ═════════════════════════════════════════════════════════════════════════════
QXV_CHUNK = 4200
QXV_MAX_CHUNKS = 12

_QXV_LETTERS = {
    "a": 1, "b": 2, "c": 3, "d": 4,
    "ক": 1, "খ": 2, "গ": 3, "ঘ": 4,
    "i": 1, "ii": 2, "iii": 3, "iv": 4,
}


def _qxv_prompt(chunk, lang):
    language = (
        "প্রতিটি প্রশ্ন, অপশন ও ব্যাখ্যা বাংলাতেই লিখবে (মূল পাতায় যেভাবে আছে)।"
        if lang == "bn" else
        "Keep every stem, option and explanation in English exactly as printed."
    )
    return (
        "You are an exam digitiser. Return STRICT JSON only, no markdown.\n"
        "TASK: extract EVERY multiple-choice question that appears in the SOURCE "
        "below — do not invent new questions, do not skip any, keep the printed "
        "order.\n"
        "RULES:\n"
        "1. Copy the question stem and the options exactly as printed (fix only "
        "OCR noise). Remove A/B/C/D or ক/খ/গ/ঘ labels from the option text.\n"
        "2. Every item must have exactly 4 options. If the page prints fewer, add "
        "plausible distractors of the same type.\n"
        "3. If the page already marks the correct answer, use that answer. If not, "
        "solve the question yourself and give the correct answer with 100% accuracy.\n"
        "4. If the page prints an explanation/solution, reuse it (condensed). If "
        "not, write a short step-by-step justification that ends with the same "
        "value as the correct option.\n"
        "5. Write numbers completely — 5.04 must stay 5.04, never 04. Use readable "
        "Unicode math (√, ², ₁, π, θ, ×10⁻⁴).\n"
        f"6. {language}\n"
        "7. answer is an integer 1-4 pointing at the correct option.\n"
        'FORMAT: {"items":[{"question":"...","options":["..","..","..",".."],'
        '"answer":2,"explanation":"..."}]}\n\n'
        "SOURCE:\n" + str(chunk or "")
    )


def _qxv_ai_raw(prompt, timeout=45):
    caller = globals().get("_adv_call_text")
    if callable(caller):
        with _cxV.suppress(Exception):
            result = caller(prompt, force_json=True, timeout=timeout)
            raw = result[0] if isinstance(result, (list, tuple)) else result
            if raw and str(raw).strip():
                return str(raw)
    builtin = globals().get("call_gemini_text_rest")
    if callable(builtin):
        with _cxV.suppress(Exception):
            raw = builtin(prompt, timeout_seconds=timeout, force_json=True)
            if raw and str(raw).strip():
                return str(raw)
    asker = globals().get("query_ai")
    if callable(asker):
        with _cxV.suppress(Exception):
            raw = asker(prompt)
            if raw and str(raw).strip():
                return str(raw)
    return ""


def _qxv_items(raw):
    for name in ("_json_items_74", "_partial_json_items_74"):
        parser = globals().get(name)
        if callable(parser):
            with _cxV.suppress(Exception):
                items = list(parser(raw) or [])
                if items:
                    return items
    return []


def _qxv_answer_index(item, options):
    value = item.get("answer", item.get("correct", item.get("correct_option")))
    text = str(value if value is not None else "").strip()
    plain = text.translate(_QXV_BN_DIGITS)
    if _reV.fullmatch(r"[1-9]", plain):
        return int(plain)
    key = plain.strip("().:- ").lower()
    if key in _QXV_LETTERS:
        return _QXV_LETTERS[key]
    flat = _reV.sub(r"\s+", " ", text).casefold()
    for index, option in enumerate(options, start=1):
        if flat and flat == _reV.sub(r"\s+", " ", str(option)).casefold():
            return index
    return 0


def _qxv_row(item):
    if not isinstance(item, dict):
        return None
    question = str(item.get("question") or item.get("questions") or "").strip()
    raw_options = item.get("options")
    if isinstance(raw_options, dict):
        raw_options = list(raw_options.values())
    if not raw_options:
        raw_options = [item.get(f"option{i}") for i in range(1, 6)]
    cleaner = globals().get("_qx107_clean_math_text")
    options = []
    for option in (raw_options or []):
        text = str(option or "").strip()
        if not text:
            continue
        if callable(cleaner):
            with _cxV.suppress(Exception):
                text = str(cleaner(text, option=True) or text).strip()
        if text:
            options.append(text)
    options = options[:4]
    if not question or len(options) < 4:
        return None
    answer = _qxv_answer_index(item, options) or 1
    row = {
        "question": question,
        "options": options,
        "answer": max(1, min(4, int(answer))),
        "explanation": str(item.get("explanation") or item.get("solution") or "").strip(),
    }
    finaliser = globals().get("_qxz_finalise")
    if callable(finaliser):
        with _cxV.suppress(Exception):
            return finaliser(dict(row), allow_repair=True)
    return row


def _qxv_chunks(text):
    raw = str(text or "").strip()
    if not raw:
        return []
    out, buffer_text = [], ""
    for block in _reV.split(r"\n\s*\n", raw):
        if len(buffer_text) + len(block) + 2 > QXV_CHUNK and buffer_text:
            out.append(buffer_text)
            buffer_text = block
        else:
            buffer_text = (buffer_text + "\n\n" + block) if buffer_text else block
        if len(out) >= QXV_MAX_CHUNKS:
            break
    if buffer_text and len(out) < QXV_MAX_CHUNKS:
        out.append(buffer_text)
    return out


def _qxv_extract_sync(source_text, lang="bn"):
    """Harvest every printed MCQ from an OCR text."""
    rows, seen = [], set()
    globals()["_QXZ_LENIENT"] = True
    try:
        for chunk in _qxv_chunks(source_text):
            raw = _qxv_ai_raw(_qxv_prompt(chunk, lang))
            if not raw:
                continue
            for item in _qxv_items(raw):
                row = _qxv_row(item)
                if not row:
                    continue
                signature = _reV.sub(r"\W+", "", str(row.get("question") or "").casefold())[:110]
                if not signature or signature in seen:
                    continue
                seen.add(signature)
                rows.append(row)
    finally:
        globals()["_QXZ_LENIENT"] = False
    return rows


async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):
    lang = "bn"
    with _cxV.suppress(Exception):
        lang = str(_generation_lang_88(source_text) or "bn")
    rows = []
    with _cxV.suppress(Exception):
        rows = await _run_blocking(  # type: ignore[name-defined]
            _role_of(uid), _qxv_extract_sync, source_text, lang,  # type: ignore[name-defined]
            timeout=600,
        )
    if not rows:
        return 0, 0, 0
    added, dup = 0, 0
    storer = globals().get("_qxz_store_rows")
    if callable(storer):
        with _cxV.suppress(Exception):
            added, dup = storer(uid, rows, "src")
    return int(added or 0), int(dup or 0), len(rows)


async def _qxv_report(update, context, uid, added, dup, found, label):
    total = 0
    with _cxV.suppress(Exception):
        total = int(buffer_count(uid))  # type: ignore[name-defined]
    body = (
        f"📄 Source: <b>{label}</b>\n"
        f"🔎 পাওয়া প্রশ্ন: <b>{found}</b>\n"
        f"➕ Buffer-এ যোগ: <b>{added}</b>\n"
        f"♻️ ডুপ্লিকেট বাদ: <b>{dup}</b>\n"
        f"📦 Buffer total: <b>{total}</b>"
    )
    with _cxV.suppress(Exception):
        await update.effective_message.reply_text(
            _qxv_box("Questions → Quiz" if added else "No New Quiz", body,
                     "✅" if added else "ℹ️"),
            parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
        )
    if added > 0:
        with _cxV.suppress(Exception):
            await _send_pb_action_card(  # type: ignore[name-defined]
                context, update.effective_message.chat_id, uid, added
            )


# ═════════════════════════════════════════════════════════════════════════════
# 3) .gen — page ranges for PDFs and full-page harvest for question sheets
# ═════════════════════════════════════════════════════════════════════════════
_QXV_PAGESPEC = _reV.compile(r"^\d{1,4}(?:\s*[-–—:]\s*\d{1,4})?(?:,\d{1,4}(?:\s*[-–—:]\s*\d{1,4})?)+$|^\d{1,4}\s*[-–—:]\s*\d{1,4}$")
_QXV_PLAIN_TOKENS = {"all", "full", "verbatim", "same", "asis", "src", "source", "sob", "sobgulo"}


def _qxv_pdf_document(message):
    reply = getattr(message, "reply_to_message", None)
    for candidate in (reply, message):
        document = getattr(candidate, "document", None) if candidate is not None else None
        if document is None:
            continue
        name = str(getattr(document, "file_name", "") or "").lower()
        mime = str(getattr(document, "mime_type", "") or "").lower()
        if name.endswith(".pdf") or "pdf" in mime:
            return document
    return None


def _qxv_reply_is_media(message):
    reply = getattr(message, "reply_to_message", None)
    if reply is None:
        return False
    if getattr(reply, "photo", None):
        return True
    document = getattr(reply, "document", None)
    if document is not None:
        name = str(getattr(document, "file_name", "") or "").lower()
        return not name.endswith(".txt")
    return False


async def _qxv_pdf_pages_flow(update, context, uid, pages):
    message = update.effective_message
    document = _qxv_pdf_document(message)
    file_id = str(getattr(document, "file_id", "") or "")
    if document is not None:
        remember = globals().get("_qxz_remember_pdf")
        if callable(remember):
            with _cxV.suppress(Exception):
                remember(context, document)
    if not file_id:
        cached = (getattr(context, "user_data", None) or {}).get("_qxz_last_pdf") or {}
        file_id = str(cached.get("file_id") or "")
    if not file_id:
        return False

    label = ", ".join(str(p) for p in pages)
    status = None
    with _cxV.suppress(Exception):
        status = await message.reply_text(
            _qxv_box("PDF Pages → Quiz",
                     f"পৃষ্ঠা: <b>{label}</b>\nপাতাগুলোর সব প্রশ্ন পড়া হচ্ছে…", "📄"),
            parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
        )

    workdir = _tfV.mkdtemp(prefix="qxv_pdf_")
    local_path = _osV.path.join(workdir, "source.pdf")
    try:
        telegram_file = await context.bot.get_file(file_id)
        await telegram_file.download_to_drive(custom_path=local_path)
        sliced, used, total = await _run_blocking(  # type: ignore[name-defined]
            _role_of(uid), globals()["_qxz_slice_pdf"], local_path, pages, timeout=120  # type: ignore[name-defined]
        )
        ocr = await _run_blocking(  # type: ignore[name-defined]
            _role_of(uid), _mistral_ocr_process_path, sliced, timeout=300  # type: ignore[name-defined]
        )
        ocr_pages = list((ocr or {}).get("pages") or [])
        raw_markdown = str((ocr or {}).get("raw_markdown") or "").strip()
        clean_text = raw_markdown
        source_items = []
        with _cxV.suppress(Exception):
            clean_text, source_items = await _run_blocking(  # type: ignore[name-defined]
                _role_of(uid), _ocr_pages_to_clean_text_and_items, ocr_pages, uid, timeout=300  # type: ignore[name-defined]
            )
        clean_text = str(clean_text or raw_markdown or "").strip()
        if not clean_text:
            raise RuntimeError("এই পৃষ্ঠাগুলো থেকে পড়ার মতো লেখা পাওয়া যায়নি।")

        page_label = f"PDF page {', '.join(str(p) for p in used)} / মোট {total}"
        with _cxV.suppress(Exception):
            if status is not None:
                await status.edit_text(
                    _qxv_box("Converting", f"{page_label}\nপ্রশ্নগুলো quiz-এ রূপান্তর হচ্ছে…", "🧠"),
                    parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                )
        added, dup, found = await _qxv_harvest(update, context, uid, clean_text, status, page_label)
        if not found:
            # No printed MCQ on those pages → fall back to normal generation.
            ocr_ctx = {
                "raw_markdown": raw_markdown, "clean_text": clean_text,
                "items": list(source_items or []), "page_count": len(used),
                "source_label": page_label,
            }
            with _cxV.suppress(Exception):
                added, dup = await globals()["_generate_to_buffer_59"](
                    update, context, ocr_ctx, uid, 10, "std"
                )
        with _cxV.suppress(Exception):
            if status is not None:
                await status.delete()
        await _qxv_report(update, context, uid, added, dup, found or added, page_label)
    except Exception as error:
        _qxv_log(f"pdf range gen failed uid={uid}: {error}", "warning")
        with _cxV.suppress(Exception):
            text = _qxv_box("PDF Pages → Quiz ব্যর্থ", str(error)[:300], "⚠️")
            if status is not None:
                await status.edit_text(text, parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
            else:
                await message.reply_text(text, parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
    finally:
        with _cxV.suppress(Exception):
            if _osV.path.exists(local_path):
                _osV.remove(local_path)
    return True


_qxv_prev_cmd_gen = globals().get("cmd_gen")


async def cmd_gen(update, context):  # noqa: F811
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        if callable(_qxv_prev_cmd_gen):
            return await _qxv_prev_cmd_gen(update, context)
        return None
    uid = int(getattr(user, "id", 0) or 0)

    text = str(getattr(message, "text", "") or "").strip()
    tokens = [t for t in text.split()[1:] if not t.startswith("@")]
    normalised = [t.translate(_QXV_BN_DIGITS) for t in tokens]

    # (a) .gen 1-5 / .gen 2,4,7 → those PDF pages
    page_tokens = [t for t in normalised if _QXV_PAGESPEC.match(t)]
    has_pdf = _qxv_pdf_document(message) is not None or bool(
        (getattr(context, "user_data", None) or {}).get("_qxz_last_pdf")
    )
    if page_tokens and has_pdf:
        parser = globals().get("_qxz_parse_pages")
        pages = []
        if callable(parser):
            with _cxV.suppress(Exception):
                pages, _count = parser(page_tokens)
        if pages:
            handled = await _qxv_pdf_pages_flow(update, context, uid, pages)
            if handled:
                raise ApplicationHandlerStop  # type: ignore[name-defined]

    # (b) plain .gen on a question sheet → harvest every printed question
    only_plain = all(t.lower() in _QXV_PLAIN_TOKENS for t in tokens)
    if only_plain and _qxv_reply_is_media(message):
        resolver = globals().get("_resolve_ocr_ctx_59")
        ocr_ctx = None
        if callable(resolver):
            with _cxV.suppress(Exception):
                ocr_ctx = await resolver(update, context, message.reply_to_message, uid)
        source_text = ""
        if isinstance(ocr_ctx, dict):
            source_text = str(ocr_ctx.get("clean_text") or ocr_ctx.get("raw_markdown") or "").strip()
        if source_text:
            status = None
            with _cxV.suppress(Exception):
                status = await message.reply_text(
                    _qxv_box("Reading Questions",
                             "পাতায় থাকা সব প্রশ্ন quiz-এ রূপান্তর হচ্ছে…", "🔎"),
                    parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                )
            added, dup, found = await _qxv_harvest(
                update, context, uid, source_text, status, "উক্ত পাতা"
            )
            with _cxV.suppress(Exception):
                if status is not None:
                    await status.delete()
            if found:
                await _qxv_report(update, context, uid, added, dup, found, "উক্ত পাতা")
                raise ApplicationHandlerStop  # type: ignore[name-defined]
            # nothing printed on the page → keep the classic picker flow

    if callable(_qxv_prev_cmd_gen):
        return await _qxv_prev_cmd_gen(update, context)
    return None


globals()["cmd_gen"] = cmd_gen


# ═════════════════════════════════════════════════════════════════════════════
# 4) /pdfpages for Student access too
# ═════════════════════════════════════════════════════════════════════════════
_QXV_NEW_COMMANDS = {"pdfpages", "pdfpage"}

for _qxv_set_name in ("QX113_STUDENT_COMMANDS", "QX112_STUDENT_COMMANDS", "QX_WORKSPACE_COMMANDS"):
    with _cxV.suppress(Exception):
        bucket = globals().get(_qxv_set_name)
        if isinstance(bucket, set):
            bucket |= _QXV_NEW_COMMANDS

with _cxV.suppress(Exception):
    menu = globals().get("QX112_STUDENT_MENU_COMMANDS")
    if isinstance(menu, list) and not any(str(row[0]) == "pdfpages" for row in menu if row):
        menu.insert(3, ("pdfpages", "PDF-এর নির্দিষ্ট পৃষ্ঠা থেকে quiz"))

_QXV_STUDENT_BLOCK = (
    "\n\n<b>PDF থেকে quiz</b>\n"
    "<code>/pdfpages 3-7 20</code> — PDF-এ reply করে নির্দিষ্ট পৃষ্ঠা থেকে quiz\n"
    "<code>.gen 1-5</code> — ঐ পৃষ্ঠাগুলোর সব প্রশ্ন সরাসরি buffer-এ\n"
    "<code>.gen</code> (প্রশ্নের ছবিতে reply) — ছবির সব প্রশ্ন quiz-এ"
)

for _qxv_card in (
    "QX112_STUDENT_COMMANDS_CARD", "QX115_STUDENT_HELP_CARD",
    "QX95_USER_COMMANDS_CARD", "QX94_USER_COMMANDS_CARD",
    "QX93_COMMANDS_CARD", "QX94_OWNER_CARD",
):
    with _cxV.suppress(Exception):
        card = globals().get(_qxv_card)
        if isinstance(card, str) and card and "/pdfpages" not in card:
            globals()[_qxv_card] = card + _QXV_STUDENT_BLOCK


# ═════════════════════════════════════════════════════════════════════════════
# 5) Wiring
# ═════════════════════════════════════════════════════════════════════════════
_qxv_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qxv_prev_build_app() if callable(_qxv_prev_build_app) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    with _cxV.suppress(Exception):
        if callable(register):
            register(app, "gen", cmd_gen, group=-3400)
        else:
            app.add_handler(CommandHandler("gen", cmd_gen), group=-3400)  # type: ignore[name-defined]
            app.add_handler(_build_dot_command_handler("gen", cmd_gen), group=-3400)  # type: ignore[name-defined]
    _qxv_log("verbatim .gen harvest + pdf page ranges wired")
    return app


_qxv_log("section 117 loaded")
