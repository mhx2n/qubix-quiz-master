# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 121 — STUDENT CARD SCRUB · INSTANT .gen STATUS · PDF .gen N PAGE
#               · BUFFER COUNT INBOX BUTTON            (2026-08-05)
#
#   1. Student inbox never shows the channel directory ("1 · dddd") nor the
#      "একই source-এ আবার command দিলে…" / topic-publish hints.
#   2. `.gen` on a photo/PDF now shows the "Reading Questions" card INSTANTLY
#      (before OCR), so students no longer wait 15–20s for feedback.
#   3. `.gen 2` on a PDF means PAGE 2 (harvest every printed question there),
#      not "make 2 quizzes". Quiz *generation* by count stays with /pdfpages.
#   4. `.bc` / `/buffercount` card now also carries a working
#      "📥 Send to Inbox" button (all roles) beside the existing menu buttons.
#
#   Layer-only: no earlier section is rewritten.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx121
import re as _re121
import telegram as _tg121


def _qx121_log(message, level="info"):
    with _cx121.suppress(Exception):
        getattr(_qx_log, level)("[QUBIX-121] " + str(message))  # type: ignore[name-defined]


def _qx121_is_student(chat_id) -> bool:
    with _cx121.suppress(Exception):
        cid = int(chat_id or 0)
        if cid <= 0:
            return False
        checker = globals().get("_qx114_is_student")
        if callable(checker):
            return bool(checker(cid))
    return False


# ─────────────────────────────────────────────────────────────────────────────
# 1) Student text scrub — channel directory + publish hints never reach them
# ─────────────────────────────────────────────────────────────────────────────
_QX121_DROP_MARKERS = (
    "unique set", "Topic publish", "Channel Directory", "চ্যানেল সিরিয়াল",
    "/addchannel", "channel#", "group#", "topic#",
)
_QX121_SERIAL_LINE = _re121.compile(r"^\s*(?:<code>)?\d{1,3}(?:</code>)?\s*[·\.\)]\s+\S")


def _qx121_scrub(text: str) -> str:
    body = str(text or "")
    if not body:
        return body
    kept, changed = [], False
    for line in body.split("\n"):
        if any(marker in line for marker in _QX121_DROP_MARKERS) or _QX121_SERIAL_LINE.match(line):
            changed = True
            continue
        kept.append(line)
    if not changed:
        return body
    cleaned = _re121.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return cleaned or body


def _qx121_wrap_text(name: str) -> None:
    original = getattr(_tg121.Bot, name, None)
    if not callable(original) or getattr(original, "_qx121", False):
        return

    async def wrapper(self, *args, **kwargs):
        with _cx121.suppress(Exception):
            body = kwargs.get("text")
            if isinstance(body, str) and body and _qx121_is_student(kwargs.get("chat_id")):
                kwargs["text"] = _qx121_scrub(body)
        return await original(self, *args, **kwargs)

    wrapper._qx121 = True  # type: ignore[attr-defined]
    setattr(_tg121.Bot, name, wrapper)


for _qx121_name in ("send_message", "edit_message_text"):
    with _cx121.suppress(Exception):
        _qx121_wrap_text(_qx121_name)


_qx121_prev_directory = globals().get("_qx95_channel_directory")

if callable(_qx121_prev_directory):
    def _qx95_channel_directory(uid: int) -> str:  # noqa: F811
        if _qx121_is_student(uid):
            return ""
        return _qx121_prev_directory(uid)

    globals()["_qx95_channel_directory"] = _qx95_channel_directory


# ─────────────────────────────────────────────────────────────────────────────
# 2) Buffer count card — add a working "Send to Inbox" button for every role
# ─────────────────────────────────────────────────────────────────────────────
def _qx121_bc_keyboard(uid):
    base = None
    with _cx121.suppress(Exception):
        base = _qx93_menu_kb()  # type: ignore[name-defined]
    rows = []
    with _cx121.suppress(Exception):
        rows = [list(row) for row in (getattr(base, "inline_keyboard", None) or [])]
    with _cx121.suppress(Exception):
        rows.insert(0, [
            InlineKeyboardButton("📥 Send to Inbox", callback_data="qx121:inbox"),  # type: ignore[name-defined]
            InlineKeyboardButton("📂 Export CSV", callback_data="qx121:csv"),  # type: ignore[name-defined]
        ])
    with _cx121.suppress(Exception):
        markup = InlineKeyboardMarkup(rows)  # type: ignore[name-defined]
        if _qx121_is_student(uid):
            filt = globals().get("_qx120_filter_markup")
            if callable(filt):
                cleaned = filt(markup)
                if cleaned is not None:
                    return cleaned
        return markup
    return base


_qx121_prev_bc = globals().get("qx95_cmd_buffercount")


async def qx95_cmd_buffercount(update, context):  # noqa: F811
    uid = 0
    with _cx121.suppress(Exception):
        uid = int(_qx95_scope_uid(update, context) or 0)  # type: ignore[name-defined]
    ok = True
    with _cx121.suppress(Exception):
        ok = bool(_qx_access(uid).get("ok"))  # type: ignore[name-defined]
    if not ok:
        if callable(_qx121_prev_bc):
            return await _qx121_prev_bc(update, context)
        return None
    card = ""
    with _cx121.suppress(Exception):
        card = str(_qx95_buffer_card(uid) or "")  # type: ignore[name-defined]
    if not card:
        if callable(_qx121_prev_bc):
            return await _qx121_prev_bc(update, context)
        return None
    with _cx121.suppress(Exception):
        await _qx94_clean_send(update, context, card, _qx121_bc_keyboard(uid))  # type: ignore[name-defined]
    raise ApplicationHandlerStop  # type: ignore[name-defined]


globals()["qx95_cmd_buffercount"] = qx95_cmd_buffercount


async def _qx121_deliver_inbox(context, uid, chat_id):
    deliver = globals().get("_qx114_deliver")
    if callable(deliver):
        return await deliver(context, int(uid), int(chat_id))
    items = []
    with _cx121.suppress(Exception):
        items = list(buffer_list(int(uid), limit=99999) or [])  # type: ignore[name-defined]
    poster = globals().get("_post_buffer_to_chat")
    if not items or not callable(poster):
        return (0, 0, None)
    with _cx121.suppress(Exception):
        result = await poster(context, int(uid), int(chat_id), items, None, "", "")
        if isinstance(result, tuple) and len(result) >= 2:
            return (int(result[0] or 0), int(result[1] or 0), result[2] if len(result) > 2 else None)
    return (0, 0, None)


async def qx121_cb(update, context):
    query = getattr(update, "callback_query", None)
    data = str(getattr(query, "data", "") or "")
    if not data.startswith("qx121:"):
        return
    action = data.split(":", 1)[1]
    uid = 0
    with _cx121.suppress(Exception):
        uid = int(_qx95_scope_uid(update, context) or 0)  # type: ignore[name-defined]
    chat_id = uid
    with _cx121.suppress(Exception):
        chat_id = int(getattr(getattr(query, "message", None), "chat_id", uid) or uid)

    if action == "csv":
        with _cx121.suppress(Exception):
            await query.answer("CSV…")
        exporter = globals().get("_qx106_export")
        count = 0
        if callable(exporter):
            with _cx121.suppress(Exception):
                count = int(await exporter(context, chat_id, uid, "") or 0)
        if not count:
            sender = globals().get("_send_done_export_62")
            if callable(sender):
                with _cx121.suppress(Exception):
                    await sender(update, context, uid)
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    with _cx121.suppress(Exception):
        await query.answer("পাঠানো হচ্ছে…")
    with _cx121.suppress(Exception):
        _QX_ACTING_OWNER.set(int(uid))  # type: ignore[name-defined]
    ok_count, fail_count, first_id = await _qx121_deliver_inbox(context, uid, chat_id)
    if ok_count:
        note = f"✅ পাঠানো হয়েছে: <b>{ok_count}</b>" + (
            f"\n⚠️ বাদ পড়েছে: <b>{fail_count}</b>" if fail_count else ""
        )
    else:
        note = "এখন buffer-এ কোনো quiz নেই।"
    kwargs = {
        "chat_id": chat_id,
        "text": "📥 <b>Inbox Practice</b>\n" + note,
        "parse_mode": ParseMode.HTML,  # type: ignore[name-defined]
        "disable_web_page_preview": True,
    }
    if ok_count and first_id:
        kwargs["reply_to_message_id"] = int(first_id)
    with _cx121.suppress(Exception):
        await context.bot.send_message(**kwargs)
    raise ApplicationHandlerStop  # type: ignore[name-defined]


# ─────────────────────────────────────────────────────────────────────────────
# 3) `.gen` — instant status card, and `.gen N` on a PDF = page N
# ─────────────────────────────────────────────────────────────────────────────
_qx121_prev_cmd_gen = globals().get("cmd_gen")
_QX121_SINGLE = _re121.compile(r"^\d{1,4}$")


def _qx121_pages_from_tokens(tokens):
    pages = []
    parser = globals().get("_qxz_parse_pages")
    if callable(parser):
        with _cx121.suppress(Exception):
            pages, _count = parser(tokens)
    if not pages:
        for token in tokens:
            if _QX121_SINGLE.match(token):
                with _cx121.suppress(Exception):
                    value = int(token)
                    if 1 <= value <= 5000 and value not in pages:
                        pages.append(value)
    return pages


async def cmd_gen(update, context):  # noqa: F811
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        if callable(_qx121_prev_cmd_gen):
            return await _qx121_prev_cmd_gen(update, context)
        return None
    uid = int(getattr(user, "id", 0) or 0)

    text = str(getattr(message, "text", "") or "").strip()
    tokens = [t for t in text.split()[1:] if not t.startswith("@")]
    translate = globals().get("_QXV_BN_DIGITS")
    normalised = [t.translate(translate) if translate else t for t in tokens]

    pdf_finder = globals().get("_qxv_pdf_document")
    pdf_doc = pdf_finder(message) if callable(pdf_finder) else None
    has_pdf = pdf_doc is not None or bool(
        (getattr(context, "user_data", None) or {}).get("_qxz_last_pdf")
    )

    # (a) PDF + any page spec (including a single number) → those pages
    pages_flow = globals().get("_qxv_pdf_pages_flow")
    if has_pdf and normalised and callable(pages_flow):
        pages = _qx121_pages_from_tokens(normalised)
        if pages:
            handled = False
            with _cx121.suppress(Exception):
                handled = bool(await pages_flow(update, context, uid, pages))
            if handled:
                raise ApplicationHandlerStop  # type: ignore[name-defined]

    # (b) plain `.gen` on a question sheet → instant status, then harvest
    plain_tokens = globals().get("_QXV_PLAIN_TOKENS") or set()
    is_media = globals().get("_qxv_reply_is_media")
    harvest = globals().get("_qxv_harvest")
    report = globals().get("_qxv_report")
    boxer = globals().get("_qxv_box")
    only_plain = all(t.lower() in plain_tokens for t in tokens)
    if (
        only_plain and callable(is_media) and is_media(message)
        and callable(harvest) and callable(report) and callable(boxer)
    ):
        status = None
        with _cx121.suppress(Exception):
            status = await message.reply_text(
                boxer("Reading Questions", "পাতায় থাকা সব প্রশ্ন quiz-এ রূপান্তর হচ্ছে…", "🔎"),
                parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
            )
        resolver = globals().get("_resolve_ocr_ctx_59")
        ocr_ctx = None
        if callable(resolver):
            with _cx121.suppress(Exception):
                ocr_ctx = await resolver(update, context, message.reply_to_message, uid)
        source_text = ""
        if isinstance(ocr_ctx, dict):
            source_text = str(ocr_ctx.get("clean_text") or ocr_ctx.get("raw_markdown") or "").strip()
        if source_text:
            added = dup = found = 0
            with _cx121.suppress(Exception):
                added, dup, found = await harvest(update, context, uid, source_text, status, "উক্ত পাতা")
            with _cx121.suppress(Exception):
                if status is not None:
                    await status.delete()
            if found:
                await report(update, context, uid, added, dup, found, "উক্ত পাতা")
                raise ApplicationHandlerStop  # type: ignore[name-defined]
        else:
            with _cx121.suppress(Exception):
                if status is not None:
                    await status.delete()

    if callable(_qx121_prev_cmd_gen):
        return await _qx121_prev_cmd_gen(update, context)
    return None


globals()["cmd_gen"] = cmd_gen


# ─────────────────────────────────────────────────────────────────────────────
# 4) Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx121_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx121_prev_build_app() if callable(_qx121_prev_build_app) else None
    if app is None:
        return app
    with _cx121.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx121_cb, pattern=r"^qx121:"), group=-30006  # type: ignore[name-defined]
        )
    for _name in ("buffercount", "bc"):
        with _cx121.suppress(Exception):
            dual = globals().get("_dual")
            if callable(dual):
                dual(_name, qx95_cmd_buffercount, -30006)
    _qx121_log("student scrub · instant gen · pdf page gen · bc inbox wired")
    return app


_qx121_log("section 121 loaded")