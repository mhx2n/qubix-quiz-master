# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 134 (2026-08-10)
#   1) /pdfpages live card floats to the bottom
#      The PDF status card was created BEFORE the long OCR step, so by the time
#      generation started the card sat far above the newest messages and the
#      10s live ticker was invisible. Now, at the moment generation begins, the
#      old card is deleted and a fresh card is posted at the bottom, registered
#      as the live progress card — exactly like the normal .gen flow.
#
#   2) `.aitopic summarize` on an image / PDF page
#      Reply to a page photo or PDF with `.aitopic summarize` (optionally
#      `.aitopic c1 summarize ...`). The page is OCR'd, everything on it is
#      summarised into ONE rich topic card (tables preserved as aligned rows),
#      then the existing review flow runs: Confirm / Send & Pin / Regenerate /
#      Cancel, plus reply-to-revise. Publishing behaviour is unchanged.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx134
import re as _re134
import time as _t134


def _log134(message, level="info"):
    with _cx134.suppress(Exception):
        getattr(logger, level)("[S134] %s", message)  # type: ignore[name-defined]


# ══════════════════════════════════════════════════════════════════════════════
# 1) Floating status card for /pdfpages
# ══════════════════════════════════════════════════════════════════════════════
_QX134_MOVE_RX = _re134.compile(r"(Generating|তৈরি হচ্ছে)", _re134.I)


class _QX134FloatStatus:
    """Status card that re-posts itself at the bottom when generation starts."""

    def __init__(self, message, bot, chat_id, uid):
        self._message = message
        self._bot = bot
        self._chat_id = int(chat_id)
        self._uid = int(uid or 0)
        self._moved = False

    def __getattr__(self, name):
        return getattr(self._message, name)

    @property
    def message_id(self):
        return int(getattr(self._message, "message_id", 0) or 0)

    def _register(self):
        with _cx134.suppress(Exception):
            cards = globals().setdefault("_QX95_LAST_GEN_CARD", {})
            cards[(self._chat_id, self._uid)] = self.message_id

    async def edit_text(self, text, **kwargs):
        if not self._moved and _QX134_MOVE_RX.search(str(text or "")):
            self._moved = True
            with _cx134.suppress(Exception):
                await self._bot.delete_message(
                    chat_id=self._chat_id, message_id=self.message_id)
            fresh = None
            with _cx134.suppress(Exception):
                fresh = await self._bot.send_message(
                    chat_id=self._chat_id, text=text, **kwargs)
            if fresh is not None:
                self._message = fresh
                self._register()
                return fresh
            # resend failed → fall back to a plain new message
            with _cx134.suppress(Exception):
                self._message = await self._bot.send_message(
                    chat_id=self._chat_id, text=str(text))
                self._register()
            return self._message
        with _cx134.suppress(Exception):
            return await self._message.edit_text(text, **kwargs)
        return self._message

    async def delete(self):
        with _cx134.suppress(Exception):
            await self._bot.delete_message(
                chat_id=self._chat_id, message_id=self.message_id)


class _QX134MessageProxy:
    def __init__(self, message, bot, uid):
        self._message = message
        self._bot = bot
        self._uid = uid

    def __getattr__(self, name):
        return getattr(self._message, name)

    async def reply_text(self, *args, **kwargs):
        sent = await self._message.reply_text(*args, **kwargs)
        return _QX134FloatStatus(
            sent, self._bot, getattr(self._message, "chat_id", 0), self._uid)


class _QX134UpdateProxy:
    def __init__(self, update, bot, uid):
        self._update = update
        message = getattr(update, "effective_message", None)
        self._proxy = (_QX134MessageProxy(message, bot, uid)
                       if message is not None else None)

    def __getattr__(self, name):
        return getattr(self._update, name)

    @property
    def effective_message(self):
        return self._proxy if self._proxy is not None else getattr(
            self._update, "effective_message", None)

    @property
    def message(self):
        real = getattr(self._update, "message", None)
        if real is not None and self._proxy is not None and \
                getattr(real, "message_id", None) == getattr(self._proxy, "message_id", None):
            return self._proxy
        return real


_qx134_prev_pdfpages = globals().get("qxz_cmd_pdfpages")
if callable(_qx134_prev_pdfpages):

    async def qxz_cmd_pdfpages(update, context):  # noqa: F811
        uid = 0
        with _cx134.suppress(Exception):
            uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
        try:
            proxy = _QX134UpdateProxy(update, context.bot, uid)
        except Exception:
            proxy = update
        return await _qx134_prev_pdfpages(proxy, context)

    globals()["qxz_cmd_pdfpages"] = qxz_cmd_pdfpages
    _log134("pdfpages live card now floats to the bottom")


# ══════════════════════════════════════════════════════════════════════════════
# 2) `.aitopic summarize` from image / PDF page
# ══════════════════════════════════════════════════════════════════════════════
_QX134_SUM_RX = _re134.compile(
    r"(summari[sz]e|summary|সামারাইজ|সারসংক্ষেপ|সারাংশ)", _re134.I)

_QX134_SUM_INSTRUCTIONS = (
    "Summarise EVERYTHING present in the source page into one polished, "
    "exam-ready topic card. Cover every heading, list item, definition, "
    "scientific name and table row — nothing may be dropped and nothing may be "
    "invented. Keep the source language (Bangla source → Bangla output). "
    "Structure: a strong title, then short sections with bullet points. "
    "If the source has a table, keep it as a table using aligned plain-text "
    "rows separated by ' | ' with a header row — never as a code fence. "
    "Bold the key terms. Keep it compact and readable."
)


async def _qx134_source_from_reply(update, context, reply, uid):
    """Text of the replied message, OCR'ing photo/PDF when needed."""
    text = str(getattr(reply, "text", None)
               or getattr(reply, "caption", None) or "").strip()
    if len(text) >= 40:
        return text
    resolver = globals().get("_resolve_ocr_ctx_59")
    if callable(resolver) and (getattr(reply, "photo", None)
                               or getattr(reply, "document", None)):
        ctx = None
        with _cx134.suppress(Exception):
            ctx = await resolver(update, context, reply, uid)
        if isinstance(ctx, dict):
            ocr_text = str(ctx.get("clean_text") or ctx.get("raw_markdown") or "").strip()
            if ocr_text:
                return ocr_text
    return text


def _qx134_parse_target(text):
    """Return (target_type, serial, sub_topic_id, do_pin, extra_instructions)."""
    body = _re134.sub(r"^[./]aitopic\b", "", str(text or "").strip(),
                      flags=_re134.I).strip()
    do_pin = bool(_re134.search(r"(?:^|\s)pin(?:\s|$)", body, _re134.I))
    body = _re134.sub(r"(?:^|\s)pin(?:\s|$)", " ", body, flags=_re134.I).strip()
    match = _re134.search(r"(?:^|\s)([cg])(\d+)(?:\s+(\d+))?(?=\s|$)", body, _re134.I)
    target_type, serial, sub_topic_id = "c", 1, None
    if match:
        target_type = match.group(1).lower()
        serial = int(match.group(2))
        if match.group(3) and target_type == "g":
            sub_topic_id = int(match.group(3))
        body = (body[:match.start()] + " " + body[match.end():]).strip()
    extra = _QX134_SUM_RX.sub(" ", body).strip()
    return target_type, serial, sub_topic_id, do_pin, extra


_qx134_prev_aitopic = globals().get("cmd_aitopic_80")
_qx134_show_review = globals().get("_show_topic_review_80")
_qx134_generate = globals().get("_generate_topic_sync_80")
_qx134_target = globals().get("_topic_target_80")

if callable(_qx134_prev_aitopic) and callable(_qx134_show_review) \
        and callable(_qx134_generate):

    async def cmd_aitopic_80(update, context):  # noqa: F811
        message = getattr(update, "message", None) or getattr(
            update, "effective_message", None)
        raw = str(getattr(message, "text", "") or "")
        reply = getattr(message, "reply_to_message", None)
        if message is None or reply is None or not _QX134_SUM_RX.search(raw):
            return await _qx134_prev_aitopic(update, context)

        user = getattr(update, "effective_user", None)
        uid = int(getattr(user, "id", 0) or 0)
        checker = globals().get("is_owner")
        if callable(checker) and not checker(uid):
            return await _qx134_prev_aitopic(update, context)

        target_type, serial, sub_topic_id, do_pin, extra = _qx134_parse_target(raw)
        if callable(_qx134_target) and not _qx134_target(
                uid, target_type, serial, sub_topic_id):
            warn = globals().get("warn")
            if callable(warn):
                await warn(update, "Target পাওয়া যায়নি",
                           "প্রথমে channel/group যোগ করুন, অথবা "
                           "<code>.aitopic c1 summarize</code> এর মতো সঠিক serial দিন।")
            return

        boxer = globals().get("ui_box_html")
        status = None
        with _cx134.suppress(Exception):
            status = await message.reply_text(
                boxer("Reading Page", "পৃষ্ঠার সব তথ্য পড়া হচ্ছে…", emoji="🔎")
                if callable(boxer) else "🔎 পৃষ্ঠার সব তথ্য পড়া হচ্ছে…",
                parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
            )
        try:
            source = await _qx134_source_from_reply(update, context, reply, uid)
            if len(str(source or "").strip()) < 20:
                raise RuntimeError("এই পৃষ্ঠা থেকে পড়ার মতো লেখা পাওয়া যায়নি।")
            with _cx134.suppress(Exception):
                if status is not None:
                    await status.edit_text(
                        boxer("Summarizing", "সব তথ্য গুছিয়ে rich topic তৈরি হচ্ছে…",
                              emoji="✨") if callable(boxer)
                        else "✨ rich topic তৈরি হচ্ছে…",
                        parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                    )
            instructions = (_QX134_SUM_INSTRUCTIONS
                            + (("\nExtra: " + extra) if extra else ""))
            draft = await _a80.wait_for(  # type: ignore[name-defined]
                _a80.to_thread(_qx134_generate, source, instructions),  # type: ignore[name-defined]
                timeout=70,
            )
            with _cx134.suppress(Exception):
                if status is not None:
                    await status.delete()
            await _qx134_show_review(update, context, uid, source, instructions,
                                     draft, target_type, serial, sub_topic_id, do_pin)
        except Exception as error:
            text = "⚠️ Summary topic তৈরি হয়নি: " + str(error)[:220]
            with _cx134.suppress(Exception):
                if status is not None:
                    await status.edit_text(text)
                else:
                    await message.reply_text(text)

    globals()["cmd_aitopic_80"] = cmd_aitopic_80
    _log134(".aitopic summarize (image/PDF page → rich topic) active")


# ── Regenerate button on the topic review card ────────────────────────────────
_qx134_prev_keyboard = globals().get("_topic_keyboard_80")
if callable(_qx134_prev_keyboard):

    def _topic_keyboard_80(owner_id):  # noqa: F811
        markup = _qx134_prev_keyboard(owner_id)
        rows = []
        with _cx134.suppress(Exception):
            rows = [list(row) for row in (markup.inline_keyboard or [])]
        button = InlineKeyboardButton(  # type: ignore[name-defined]
            "🔄 আবার Generate", callback_data="ait134:regen:%s" % owner_id)
        rows.insert(max(0, len(rows) - 1), [button])
        return InlineKeyboardMarkup(rows)  # type: ignore[name-defined]

    globals()["_topic_keyboard_80"] = _topic_keyboard_80


async def cb_aitopic_regen_134(update, context):
    query = getattr(update, "callback_query", None)
    if not query or not getattr(update, "effective_user", None):
        return
    match = _re134.fullmatch(r"ait134:regen:(\d+)", str(query.data or ""))
    if not match:
        return
    owner_id = int(update.effective_user.id)
    if int(match.group(1)) != owner_id:
        with _cx134.suppress(Exception):
            await query.answer("এটি আপনার card নয়।", show_alert=False)
        return
    getter = globals().get("_topic_get_80")
    row = getter(owner_id) if callable(getter) else None
    if not row:
        with _cx134.suppress(Exception):
            await query.answer("Draft পাওয়া যায়নি।", show_alert=True)
        return
    with _cx134.suppress(Exception):
        await query.answer("নতুন করে তৈরি হচ্ছে…")
    instructions = (
        str(row.get("instructions") or "")
        + "\nRegenerate #%s: একই তথ্য রেখে নতুন গঠন ও ভাষায় সাজিয়ে লিখুন।"
        % (int(_t134.time()) % 1000)
    )
    try:
        draft = await _a80.wait_for(  # type: ignore[name-defined]
            _a80.to_thread(_qx134_generate, row["source_text"], instructions),  # type: ignore[name-defined]
            timeout=70,
        )
        await _qx134_show_review(
            update, context, owner_id, row["source_text"], instructions, draft,
            row["target_type"], int(row["target_serial"]), row.get("sub_topic_id"),
            bool(row["do_pin"]),
        )
    except Exception as error:
        with _cx134.suppress(Exception):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Regenerate হয়নি: " + str(error)[:220])


_qx134_prev_build_app = globals().get("build_app")
if callable(_qx134_prev_build_app):

    def build_app():  # noqa: F811
        app = _qx134_prev_build_app()
        if app is None:
            return app
        with _cx134.suppress(Exception):
            app.add_handler(
                CallbackQueryHandler(  # type: ignore[name-defined]
                    cb_aitopic_regen_134, pattern=r"^ait134:regen:\d+$"),
                group=-620,
            )
        _log134("section 134 wired (floating pdf card + aitopic summarize)")
        return app

    globals()["build_app"] = build_app