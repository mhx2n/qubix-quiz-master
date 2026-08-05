# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 119 — QUBIX ROLE SURFACES · SERIAL CARDS · POST LOCK (2026-08-05)
#
#   1. Generation result card never shows channel buttons any more. Every role
#      gets its own card (owner / master / student), its own wording and its own
#      buttons. Channels are reachable only through their SERIAL numbers.
#   2. Serial space is per account and always starts at 1 (buffer is per user,
#      so the card prints the real serial range of the batch).
#   3. Students can never publish: post / channel callbacks are refused with a
#      student-flavoured card even if an older keyboard is still on screen.
#   4. One channel publish at a time per account — a second publish is refused
#      until the running one finishes.
#   5. `.done` / CSV export always empties the buffer after a successful file.
#   6. Re-running `.gen` on the SAME source deletes the previous batch (rows +
#      cards) and rebuilds it, so the count is never eaten by duplicates.
#
#   Layer-only: no earlier section is rewritten.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx119
import hashlib as _hs119
import re as _re119
import time as _t119
import uuid as _uu119

import telegram.ext as _tgext119


def _qx119_log(message, level="info"):
    with _cx119.suppress(Exception):
        getattr(logger, level)("[QX119] %s", message)  # type: ignore[name-defined]


def _qx119_box(title, body, emoji="✅"):
    with _cx119.suppress(Exception):
        return ui_box_html(title, body, emoji=emoji)  # type: ignore[name-defined]
    return f"{emoji} <b>{title}</b>\n{body}"


# ─────────────────────────────────────────────────────────────────────────────
# 0) Role resolution — owner · master · student
# ─────────────────────────────────────────────────────────────────────────────
def _qx119_role(uid) -> str:
    try:
        uid = int(uid or 0)
    except Exception:
        return "master"
    if uid <= 0:
        return "master"
    with _cx119.suppress(Exception):
        if _qx_real_owner(uid):  # type: ignore[name-defined]
            return "owner"
    tier = ""
    with _cx119.suppress(Exception):
        tier = str(_qx112_tier(uid) or "")  # type: ignore[name-defined]
    if tier == "student":
        return "student"
    if tier == "master":
        return "master"
    return "trial" if tier == "" else "master"


def _qx119_can_publish(uid) -> bool:
    return _qx119_role(uid) in ("owner", "master", "trial")


# ─────────────────────────────────────────────────────────────────────────────
# 1) Role-specific result card — serials only, never channel buttons
# ─────────────────────────────────────────────────────────────────────────────
_QX119_CARD_STORE = "_qx119_card_store"


def _qx119_store(context) -> dict:
    bucket = context.application.bot_data
    if _QX119_CARD_STORE not in bucket:
        bucket[_QX119_CARD_STORE] = {}
    return bucket[_QX119_CARD_STORE]


def _qx119_channel_lines(uid) -> str:
    rows = []
    with _cx119.suppress(Exception):
        for serial, ch in enumerate(channel_list_for_user(uid) or [], start=1):  # type: ignore[name-defined]
            title = str(getattr(ch, "title", "") or getattr(ch, "channel_chat_id", "?"))[:28]
            rows.append(f"<code>{serial}</code> · {h(title)}")  # type: ignore[name-defined]
            if serial >= 10:
                break
    if not rows:
        return ""
    return "\n".join(rows)


def _qx119_card(uid, added: int, total: int) -> tuple:
    """(text, keyboard) for this account's role."""
    role = _qx119_role(uid)
    first = max(1, total - added + 1)
    serials = f"<code>{first}</code>" if added <= 1 else f"<code>{first}–{total}</code>"

    if role == "student":
        body = (
            f"➕ নতুন quiz: <b>{added}</b>\n"
            f"🔢 সিরিয়াল: {serials}\n"
            f"📦 আপনার buffer: <b>{total}</b>\n\n"
            "🎯 <code>/buffer</code> — নিজের inbox-এ প্র্যাকটিস\n"
            "📂 <code>.done</code> — CSV নামিয়ে buffer খালি"
        )
        rows = [
            [InlineKeyboardButton("🎯 আমার প্র্যাকটিস", callback_data="qx112:inbox:buffer"),  # type: ignore[name-defined]
             InlineKeyboardButton("📂 CSV", callback_data="qx119:csv")],
            [InlineKeyboardButton("🧹 Buffer খালি", callback_data="qx119:clr"),  # type: ignore[name-defined]
             InlineKeyboardButton("✖ বন্ধ", callback_data="qx119:close")],  # type: ignore[name-defined]
        ]
        return _qx119_box("🎓 Student · Quiz তৈরি হয়েছে", body, "🎓"), InlineKeyboardMarkup(rows)  # type: ignore[name-defined]

    channels = _qx119_channel_lines(uid)
    title = "👑 Owner Console · Batch Ready" if role == "owner" else "🛠 Master Workspace · Batch Ready"
    body = (
        f"➕ যোগ হলো: <b>{added}</b>\n"
        f"🔢 সিরিয়াল: {serials}\n"
        f"📦 Buffer total: <b>{total}</b>\n"
    )
    if channels:
        body += (
            "\n<b>চ্যানেল সিরিয়াল</b>\n" + channels +
            "\n\n📤 <code>.p &lt;সিরিয়াল&gt;</code> দিয়ে ঐ চ্যানেলে publish করুন।\n"
            "⏳ একসাথে একটির বেশি চ্যানেলে publish করা যাবে না।"
        )
    else:
        body += "\nℹ️ চ্যানেল যোগ করতে <code>/addchannel</code>।"
    rows = [
        [InlineKeyboardButton("📦 Buffer", callback_data="qx119:buffer"),  # type: ignore[name-defined]
         InlineKeyboardButton("📂 Export CSV", callback_data="qx119:csv")],  # type: ignore[name-defined]
        [InlineKeyboardButton("🧹 Clear Buffer", callback_data="qx119:clr"),  # type: ignore[name-defined]
         InlineKeyboardButton("✖ Close", callback_data="qx119:close")],  # type: ignore[name-defined]
    ]
    return _qx119_box(title, body, "👑" if role == "owner" else "🛠"), InlineKeyboardMarkup(rows)  # type: ignore[name-defined]


_qx119_prev_action_card = globals().get("_send_pb_action_card")


async def _send_pb_action_card(context, chat_id: int, uid: int, added: int):  # noqa: F811
    """Role-aware, channel-button-free action card."""
    total = 0
    with _cx119.suppress(Exception):
        total = int(buffer_count(uid))  # type: ignore[name-defined]
    text, keyboard = _qx119_card(uid, int(added or 0), total)
    sent = None
    with _cx119.suppress(Exception):
        sent = await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
            reply_markup=keyboard, disable_web_page_preview=True,
        )
    if sent is not None:
        _qx119_remember_card(uid, chat_id, int(getattr(sent, "message_id", 0) or 0))
    return sent


globals()["_send_pb_action_card"] = _send_pb_action_card


async def qx119_cb(update, context):
    query = getattr(update, "callback_query", None)
    if query is None or not str(getattr(query, "data", "") or "").startswith("qx119:"):
        return
    action = str(query.data).split(":", 1)[1]
    uid = int(getattr(getattr(query, "from_user", None), "id", 0) or 0)
    chat_id = int(getattr(getattr(query, "message", None), "chat_id", 0) or uid)

    if action == "close":
        with _cx119.suppress(Exception):
            await query.message.delete()
        with _cx119.suppress(Exception):
            await query.answer()
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action == "clr":
        with _cx119.suppress(Exception):
            buffer_clear(uid)  # type: ignore[name-defined]
        _QX119_SOURCES.pop(uid, None)
        with _cx119.suppress(Exception):
            await query.edit_message_text(
                _qx119_box("Buffer খালি", "সব buffered quiz মুছে ফেলা হয়েছে।", "🧹"),
                parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
            )
        with _cx119.suppress(Exception):
            await query.answer("Cleared")
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action == "csv":
        with _cx119.suppress(Exception):
            await query.answer("CSV…")
        exporter = globals().get("_qx106_export")
        count = 0
        if callable(exporter):
            with _cx119.suppress(Exception):
                count = int(await exporter(context, chat_id, uid, "") or 0)
        if not count:
            sender = globals().get("_send_done_export_62")
            if callable(sender):
                with _cx119.suppress(Exception):
                    count = int(await sender(context, chat_id, uid) or 0)
        if count:
            with _cx119.suppress(Exception):
                buffer_clear(uid)  # type: ignore[name-defined]
            _QX119_SOURCES.pop(uid, None)
            with _cx119.suppress(Exception):
                await query.message.delete()
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if action in ("buffer", "practice"):
        with _cx119.suppress(Exception):
            await query.answer()
        handler = globals().get("cmd_buffer") or globals().get("cmd_buffercount")
        if callable(handler):
            with _cx119.suppress(Exception):
                await handler(update, context)
        raise ApplicationHandlerStop  # type: ignore[name-defined]


# ─────────────────────────────────────────────────────────────────────────────
# 2) Students never publish · one publish at a time per account
# ─────────────────────────────────────────────────────────────────────────────
_QX119_PUBLISHING: dict = {}     # uid -> (chat_id, started_ts)
_QX119_PUBLISH_TTL = 3600.0


def _qx119_publish_busy(uid) -> bool:
    entry = _QX119_PUBLISHING.get(int(uid or 0))
    if not entry:
        return False
    if _t119.time() - float(entry[1] or 0) > _QX119_PUBLISH_TTL:
        _QX119_PUBLISHING.pop(int(uid or 0), None)
        return False
    return True


def _qx119_publish_begin(uid, chat_id=0) -> bool:
    uid = int(uid or 0)
    if _qx119_publish_busy(uid):
        return False
    _QX119_PUBLISHING[uid] = (chat_id, _t119.time())
    return True


def _qx119_publish_end(uid) -> None:
    _QX119_PUBLISHING.pop(int(uid or 0), None)


globals()["_qx119_publish_begin"] = _qx119_publish_begin
globals()["_qx119_publish_end"] = _qx119_publish_end

_qx119_prev_post_buffer = globals().get("_post_buffer_to_chat")

if callable(_qx119_prev_post_buffer):
    async def _post_buffer_to_chat(context, admin_id, chat_id, items, thread_id=None,  # noqa: F811
                                   group_prefix="", group_expl_link=""):
        uid = int(admin_id or 0)
        if not _qx119_can_publish(uid):
            return 0, len(list(items or [])), None
        if not _qx119_publish_begin(uid, chat_id):
            return 0, 0, None
        try:
            return await _qx119_prev_post_buffer(
                context, admin_id, chat_id, items, thread_id, group_prefix, group_expl_link,
            )
        finally:
            _qx119_publish_end(uid)

    globals()["_post_buffer_to_chat"] = _post_buffer_to_chat


_qx119_prev_cb_pba = globals().get("cb_pba")


async def cb_pba(update, context):  # noqa: F811
    """Legacy channel keyboards: refuse for students, serialise for the rest."""
    query = getattr(update, "callback_query", None)
    data = str(getattr(query, "data", "") or "")
    uid = int(getattr(getattr(query, "from_user", None), "id", 0) or 0)
    if data.startswith("pba:") and data.split(":")[1] in ("post", "list"):
        if not _qx119_can_publish(uid):
            with _cx119.suppress(Exception):
                await query.answer("Student plan-এ channel publish নেই", show_alert=True)
            with _cx119.suppress(Exception):
                await query.edit_message_text(
                    _qx119_box("🎓 Student workspace",
                               "এই plan-এ quiz শুধু নিজের inbox-এ প্র্যাকটিস আর CSV export "
                               "করা যায় — channel publish নেই।", "🎓"),
                    parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                )
            raise ApplicationHandlerStop  # type: ignore[name-defined]
        if data.split(":")[1] == "post" and _qx119_publish_busy(uid):
            with _cx119.suppress(Exception):
                await query.answer("আগের publish শেষ হওয়া পর্যন্ত অপেক্ষা করুন", show_alert=True)
            raise ApplicationHandlerStop  # type: ignore[name-defined]
        if data.split(":")[1] == "post" and callable(_qx119_prev_cb_pba):
            # `_post_buffer_to_chat` owns the lock. Taking it here as well made
            # the nested publisher see itself as busy and silently post zero.
            return await _qx119_prev_cb_pba(update, context)
    if callable(_qx119_prev_cb_pba):
        return await _qx119_prev_cb_pba(update, context)
    return None


if callable(_qx119_prev_cb_pba):
    globals()["cb_pba"] = cb_pba


# ─────────────────────────────────────────────────────────────────────────────
# 3) CSV export always empties the buffer
# ─────────────────────────────────────────────────────────────────────────────
_qx119_prev_export = globals().get("_qx106_export")

if callable(_qx119_prev_export):
    async def _qx106_export(context, chat_id, uid, filename=""):  # noqa: F811
        count = int(await _qx119_prev_export(context, chat_id, uid, filename) or 0)
        if count > 0:
            with _cx119.suppress(Exception):
                buffer_clear(uid)  # type: ignore[name-defined]
            _QX119_SOURCES.pop(int(uid or 0), None)
        return count

    globals()["_qx106_export"] = _qx106_export

_qx119_prev_done_export = globals().get("_send_done_export_62")

if callable(_qx119_prev_done_export):
    async def _send_done_export_62(context, chat_id, uid, *args, **kwargs):  # noqa: F811
        count = int(await _qx119_prev_done_export(context, chat_id, uid, *args, **kwargs) or 0)
        if count > 0:
            with _cx119.suppress(Exception):
                buffer_clear(uid)  # type: ignore[name-defined]
            _QX119_SOURCES.pop(int(uid or 0), None)
        return count

    globals()["_send_done_export_62"] = _send_done_export_62


# ─────────────────────────────────────────────────────────────────────────────
# 4) Same source · re-gen replaces the previous batch instead of deduping it
# ─────────────────────────────────────────────────────────────────────────────
_QX119_SOURCES: dict = {}        # uid -> {key: {"ids": [...], "cards": [(chat, msg)]}}
_QX119_ACTIVE: dict = {}         # uid -> key currently being harvested


def _qx119_source_key(text) -> str:
    body = str(text or "").strip()
    if not body:
        return ""
    return _hs119.sha1(body[:6000].encode("utf-8", "ignore")).hexdigest()[:16]


def _qx119_buffer_ids(uid) -> list:
    with _cx119.suppress(Exception):
        return [int(row_id) for row_id, _payload in (buffer_list(uid, limit=99999) or [])]  # type: ignore[name-defined]
    return []


def _qx119_remember_card(uid, chat_id, message_id) -> None:
    uid = int(uid or 0)
    key = str(_QX119_ACTIVE.get(uid) or "")
    if not key or not message_id:
        return
    entry = _QX119_SOURCES.setdefault(uid, {}).setdefault(key, {"ids": [], "cards": []})
    entry["cards"].append((int(chat_id), int(message_id)))


async def _qx119_drop_previous(context, uid, key) -> None:
    entry = (_QX119_SOURCES.get(int(uid or 0)) or {}).pop(key, None)
    if not entry:
        return
    ids = [int(x) for x in (entry.get("ids") or [])]
    if ids:
        with _cx119.suppress(Exception):
            buffer_remove_ids(uid, ids)  # type: ignore[name-defined]
    for chat_id, message_id in (entry.get("cards") or []):
        with _cx119.suppress(Exception):
            await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    _qx119_log(f"same-source re-gen uid={uid}: {len(ids)} old row(s) + cards removed")


_qx119_prev_harvest = globals().get("_qxv_harvest")

if callable(_qx119_prev_harvest):
    async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):  # noqa: F811
        key = _qx119_source_key(source_text)
        uid_int = int(uid or 0)
        if key:
            await _qx119_drop_previous(context, uid_int, key)
            _QX119_ACTIVE[uid_int] = key
        before = set(_qx119_buffer_ids(uid_int))
        try:
            added, dup, found = await _qx119_prev_harvest(update, context, uid, source_text, status, label)
        finally:
            pass
        if key:
            fresh = [row_id for row_id in _qx119_buffer_ids(uid_int) if row_id not in before]
            entry = _QX119_SOURCES.setdefault(uid_int, {}).setdefault(key, {"ids": [], "cards": []})
            entry["ids"] = fresh
        return added, dup, found

    globals()["_qxv_harvest"] = _qxv_harvest


_qx119_prev_report = globals().get("_qxv_report")

if callable(_qx119_prev_report):
    async def _qxv_report(update, context, uid, added, dup, found, label):  # noqa: F811
        """Role-specific harvest summary — one card, serials, no channel buttons."""
        uid_int = int(uid or 0)
        total = 0
        with _cx119.suppress(Exception):
            total = int(buffer_count(uid_int))  # type: ignore[name-defined]
        role = _qx119_role(uid_int)
        if added:
            first = max(1, total - int(added or 0) + 1)
            serials = f"<code>{first}</code>" if int(added) <= 1 else f"<code>{first}–{total}</code>"
            head = {
                "student": "🎓 Student · প্রশ্ন → Quiz",
                "owner": "👑 Owner · প্রশ্ন → Quiz",
            }.get(role, "🛠 Master · প্রশ্ন → Quiz")
            body = (
                f"📄 Source: <b>{h(str(label))}</b>\n"  # type: ignore[name-defined]
                f"🔎 পাওয়া প্রশ্ন: <b>{found}</b>\n"
                f"➕ যোগ হলো: <b>{added}</b>\n"
                f"🔢 সিরিয়াল: {serials}\n"
                f"📦 Buffer total: <b>{total}</b>"
            )
            emoji = "✅"
        else:
            head = "কোনো নতুন Quiz পাওয়া যায়নি"
            body = (
                f"📄 Source: <b>{h(str(label))}</b>\n"  # type: ignore[name-defined]
                f"🔎 পাওয়া প্রশ্ন: <b>{found}</b>\n"
                "ℹ️ পরিষ্কার ছবি বা অন্য পৃষ্ঠা দিয়ে আবার চেষ্টা করুন।"
            )
            emoji = "ℹ️"
        if int(added or 0) > 0:
            # The action card immediately below already contains the successful
            # batch count, serial range and buffer total.  Sending this summary
            # as well left a redundant top card in every inbox.
            with _cx119.suppress(Exception):
                await _send_pb_action_card(context, update.effective_message.chat_id, uid_int, int(added))
        else:
            sent = None
            with _cx119.suppress(Exception):
                sent = await update.effective_message.reply_text(
                    _qx119_box(head, body, emoji), parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                )
            if sent is not None:
                _qx119_remember_card(uid_int, sent.chat_id, int(getattr(sent, "message_id", 0) or 0))
        _QX119_ACTIVE.pop(uid_int, None)

    globals()["_qxv_report"] = _qxv_report


# ─────────────────────────────────────────────────────────────────────────────
# 5) Restore the universal reply-based `.gen` route
# ─────────────────────────────────────────────────────────────────────────────
# Section 117 intentionally intercepts page-range and no-argument media harvests,
# but its registered handler also caught `.gen 10` before the proven workspace
# resolver. That delegated into an old staff-only OCR command and produced the
# misleading “No OCR Context” card for ordinary photos/text/polls.
_qx119_prev_cmd_gen = globals().get("cmd_gen")


def _qx119_is_pdf_range_command(message, context) -> bool:
    text = str(getattr(message, "text", "") or "").strip()
    tokens = [token.translate(globals().get("_QXV_BN_DIGITS", {}))
              for token in text.split()[1:] if not token.startswith("@")]
    page_pattern = globals().get("_QXV_PAGESPEC")
    has_range = bool(page_pattern and any(page_pattern.match(token) for token in tokens))
    if not has_range:
        return False
    detector = globals().get("_qxv_pdf_document")
    with _cx119.suppress(Exception):
        if callable(detector) and detector(message) is not None:
            return True
    return bool((getattr(context, "user_data", None) or {}).get("_qxz_last_pdf"))


async def qx119_cmd_gen(update, context):
    """Keep new PDF/full-page features, otherwise use the stable any-reply flow."""
    message = getattr(update, "effective_message", None)
    if message is None:
        if callable(_qx119_prev_cmd_gen):
            return await _qx119_prev_cmd_gen(update, context)
        return None

    text = str(getattr(message, "text", "") or "").strip()
    args = [token for token in text.split()[1:] if not token.startswith("@")]
    plain_tokens = set(globals().get("_QXV_PLAIN_TOKENS") or ())
    media_detector = globals().get("_qxv_reply_is_media")
    is_plain_harvest = False
    with _cx119.suppress(Exception):
        is_plain_harvest = (
            callable(media_detector)
            and bool(media_detector(message))
            and all(token.lower() in plain_tokens for token in args)
        )

    if _qx119_is_pdf_range_command(message, context) or is_plain_harvest:
        if callable(_qx119_prev_cmd_gen):
            return await _qx119_prev_cmd_gen(update, context)

    stable = globals().get("qx95_cmd_gen")
    if callable(stable):
        return await stable(update, context)
    if callable(_qx119_prev_cmd_gen):
        return await _qx119_prev_cmd_gen(update, context)
    return None


globals()["cmd_gen"] = qx119_cmd_gen


async def _qx95_result_kb(context, uid: int, chat_id: int):  # noqa: F811
    """Use the same isolated actions on the restored classic generation card."""
    if _qx119_role(uid) == "student":
        rows = [
            [InlineKeyboardButton("🎯 আমার প্র্যাকটিস", callback_data="qx112:inbox:buffer"),  # type: ignore[name-defined]
             InlineKeyboardButton("📂 CSV", callback_data="qx119:csv")],
            [InlineKeyboardButton("🧹 Buffer খালি", callback_data="qx119:clr"),  # type: ignore[name-defined]
             InlineKeyboardButton("✖ বন্ধ", callback_data="qx119:close")],  # type: ignore[name-defined]
        ]
    else:
        rows = [
            [InlineKeyboardButton("📦 Buffer", callback_data="qx119:buffer"),  # type: ignore[name-defined]
             InlineKeyboardButton("📂 Export CSV", callback_data="qx119:csv")],
            [InlineKeyboardButton("🧹 Clear Buffer", callback_data="qx119:clr"),  # type: ignore[name-defined]
             InlineKeyboardButton("✖ Close", callback_data="qx119:close")],  # type: ignore[name-defined]
        ]
    return InlineKeyboardMarkup(rows)  # type: ignore[name-defined]


globals()["_qx95_result_kb"] = _qx95_result_kb


# ─────────────────────────────────────────────────────────────────────────────
# 6) Delete transient publish progress after every terminal publish card
# ─────────────────────────────────────────────────────────────────────────────
_QX119_POST_PROGRESS = ("Posting to Channel", "Posting to Topic", "Posting to Group")
_QX119_POST_DONE = (
    "Posting Complete", "Posted", "Posting Failed", "Stop Requested",
    "Buffer Empty", "Channel Not Found",
)
_QX119_POST_CARDS: dict = {}       # (bot identity, chat id) -> message id
_qx119_prev_ext_send = getattr(_tgext119.ExtBot, "send_message", None)
_qx119_prev_ext_edit = getattr(_tgext119.ExtBot, "edit_message_text", None)


if callable(_qx119_prev_ext_send) and not getattr(_qx119_prev_ext_send, "_qx119_cleanup", False):
    async def _qx119_ext_send_message(self, *args, **kwargs):
        chat_id = kwargs.get("chat_id", args[0] if args else None)
        text = kwargs.get("text", args[1] if len(args) > 1 else "")
        message = await _qx119_prev_ext_send(self, *args, **kwargs)
        body = str(text or "")
        slot = (id(self), str(chat_id))
        if any(marker in body for marker in _QX119_POST_PROGRESS):
            old = _QX119_POST_CARDS.get(slot)
            _QX119_POST_CARDS[slot] = int(getattr(message, "message_id", 0) or 0)
            if old and old != _QX119_POST_CARDS[slot]:
                with _cx119.suppress(Exception):
                    await self.delete_message(chat_id=chat_id, message_id=int(old))
        elif any(marker in body for marker in _QX119_POST_DONE):
            old = _QX119_POST_CARDS.pop(slot, None)
            if old:
                with _cx119.suppress(Exception):
                    await self.delete_message(chat_id=chat_id, message_id=int(old))
        return message

    _qx119_ext_send_message._qx119_cleanup = True  # type: ignore[attr-defined]
    _tgext119.ExtBot.send_message = _qx119_ext_send_message


if callable(_qx119_prev_ext_edit) and not getattr(_qx119_prev_ext_edit, "_qx119_cleanup", False):
    async def _qx119_ext_edit_message_text(self, *args, **kwargs):
        # ExtBot.edit_message_text(text, chat_id=None, message_id=None, ...)
        text = kwargs.get("text", args[0] if args else "")
        chat_id = kwargs.get("chat_id", args[1] if len(args) > 1 else None)
        message_id = kwargs.get("message_id", args[2] if len(args) > 2 else None)
        message = await _qx119_prev_ext_edit(self, *args, **kwargs)
        body = str(text or "")
        if chat_id is None:
            chat_id = getattr(getattr(message, "chat", None), "id", None)
        if message_id is None:
            message_id = getattr(message, "message_id", None)
        slot = (id(self), str(chat_id))
        if chat_id is not None and message_id and any(marker in body for marker in _QX119_POST_PROGRESS):
            old = _QX119_POST_CARDS.get(slot)
            _QX119_POST_CARDS[slot] = int(message_id)
            if old and old != int(message_id):
                with _cx119.suppress(Exception):
                    await self.delete_message(chat_id=chat_id, message_id=int(old))
        elif any(marker in body for marker in _QX119_POST_DONE):
            old = _QX119_POST_CARDS.pop(slot, None)
            if old and int(old) != int(message_id or 0):
                with _cx119.suppress(Exception):
                    await self.delete_message(chat_id=chat_id, message_id=int(old))
        return message

    _qx119_ext_edit_message_text._qx119_cleanup = True  # type: ignore[attr-defined]
    _tgext119.ExtBot.edit_message_text = _qx119_ext_edit_message_text


# ─────────────────────────────────────────────────────────────────────────────
# 7) Wiring
# ─────────────────────────────────────────────────────────────────────────────
for _qx119_ok_name in ("QX113_STUDENT_CALLBACK_OK", "QX112_STUDENT_CALLBACK_OK"):
    with _cx119.suppress(Exception):
        bucket = tuple(globals().get(_qx119_ok_name) or ())
        if "qx119:" not in bucket:
            globals()[_qx119_ok_name] = bucket + ("qx119:",)

with _cx119.suppress(Exception):
    _qx119_prefixes = tuple(globals().get("QX_WORKSPACE_CALLBACK_PREFIXES") or ())
    if "qx119:" not in _qx119_prefixes:
        globals()["QX_WORKSPACE_CALLBACK_PREFIXES"] = _qx119_prefixes + ("qx119:",)
        QX_WORKSPACE_CALLBACK_PREFIXES = globals()["QX_WORKSPACE_CALLBACK_PREFIXES"]

_qx119_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx119_prev_build_app() if callable(_qx119_prev_build_app) else None
    if app is None:
        return app
    with _cx119.suppress(Exception):
        app.add_handler(CallbackQueryHandler(qx119_cb, pattern=r"^qx119:"), group=-3600)  # type: ignore[name-defined]
    register = globals().get("_register_dual_command")
    with _cx119.suppress(Exception):
        if callable(register):
            register(app, "gen", qx119_cmd_gen, group=-3601)
        else:
            app.add_handler(CommandHandler("gen", qx119_cmd_gen), group=-3601)  # type: ignore[name-defined]
            app.add_handler(_build_dot_command_handler("gen", qx119_cmd_gen), group=-3601)  # type: ignore[name-defined]
    with _cx119.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(cb_pba, pattern=r"^pba:(post|list):.+$"), group=-3600,  # type: ignore[name-defined]
        )
    _qx119_log("role surfaces + serial cards + publish lock wired")
    return app


_qx119_log("section 119 loaded")

# ===== END SECTION 119 =====
