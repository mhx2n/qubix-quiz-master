# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 120 — QUBIX STUDENT SURFACE + INBOX DELIVERY FIX (2026-08-05)
#
#   1. Student inbox never shows master-only buttons any more:
#      Channels · Buffer · Topics · Groups · My Bot are stripped from every
#      keyboard that reaches a student private chat (any section, any card).
#   2. "🎯 আমার প্র্যাকটিস" now really delivers. Section 119 blocked
#      `_post_buffer_to_chat` for students, which also blocked delivery to the
#      student's OWN inbox → "buffer-এ কোনো quiz নেই" while the buffer had rows.
#      Self-inbox delivery is now always allowed; only channel/group publishing
#      stays blocked for students.
#
#   Layer-only: no earlier section is rewritten.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx120
import telegram as _tg120


# ─────────────────────────────────────────────────────────────────────────────
# 1) Self-inbox delivery is never treated as publishing
# ─────────────────────────────────────────────────────────────────────────────
_qx120_guarded_post = globals().get("_post_buffer_to_chat")
_qx120_inner_post = globals().get("_qx119_prev_post_buffer")

if callable(_qx120_guarded_post):
    async def _post_buffer_to_chat(context, admin_id, chat_id, items, thread_id=None,  # noqa: F811
                                   group_prefix="", group_expl_link=""):
        same_inbox = False
        with _cx120.suppress(Exception):
            same_inbox = int(chat_id or 0) > 0 and int(chat_id or 0) == int(admin_id or 0)
        if same_inbox and callable(_qx120_inner_post):
            return await _qx120_inner_post(
                context, admin_id, chat_id, items, thread_id, group_prefix, group_expl_link,
            )
        return await _qx120_guarded_post(
            context, admin_id, chat_id, items, thread_id, group_prefix, group_expl_link,
        )

    globals()["_post_buffer_to_chat"] = _post_buffer_to_chat


# ─────────────────────────────────────────────────────────────────────────────
# 2) Student keyboards — strip master-only buttons everywhere
# ─────────────────────────────────────────────────────────────────────────────
_QX120_DROP_TEXT = (
    "channel", "চ্যানেল",
    "topic", "টপিক",
    "group", "গ্রুপ",
    "my bot", "mybot", "মাই বট",
)
_QX120_DROP_CB = (
    "channels", "channel", "topics", "topic", "groups", "group", "mybot",
    "listchannels", "addchannel",
)
_QX120_KEEP = ("খালি", "clear", "master access", "সহায়তা")


def _qx120_drop_button(button) -> bool:
    text = str(getattr(button, "text", "") or "").lower()
    data = str(getattr(button, "callback_data", "") or "").lower()
    if any(keep in text for keep in _QX120_KEEP):
        return False
    if text.strip().endswith("buffer") or "buffer count" in text or "বাফার" in text:
        return True
    if any(token in text for token in _QX120_DROP_TEXT):
        return True
    tail = data.split(":")[-1] if data else ""
    if tail and tail in _QX120_DROP_CB:
        return True
    return False


def _qx120_filter_markup(markup):
    rows_in = getattr(markup, "inline_keyboard", None)
    if not rows_in:
        return markup
    rows_out = []
    changed = False
    for row in rows_in:
        kept = []
        for button in row:
            if _qx120_drop_button(button):
                changed = True
                continue
            kept.append(button)
        if kept:
            rows_out.append(kept)
    if not changed:
        return markup
    if not rows_out:
        return None
    with _cx120.suppress(Exception):
        return InlineKeyboardMarkup(rows_out)  # type: ignore[name-defined]
    return markup


def _qx120_is_student_chat(chat_id) -> bool:
    with _cx120.suppress(Exception):
        cid = int(chat_id or 0)
        if cid <= 0:
            return False
        checker = globals().get("_qx114_is_student")
        if callable(checker):
            return bool(checker(cid))
    return False


def _qx120_wrap(name: str) -> None:
    original = getattr(_tg120.Bot, name, None)
    if not callable(original) or getattr(original, "_qx120", False):
        return

    async def wrapper(self, *args, **kwargs):
        with _cx120.suppress(Exception):
            markup = kwargs.get("reply_markup")
            chat_id = kwargs.get("chat_id")
            if markup is not None and _qx120_is_student_chat(chat_id):
                kwargs["reply_markup"] = _qx120_filter_markup(markup)
        return await original(self, *args, **kwargs)

    wrapper._qx120 = True  # type: ignore[attr-defined]
    setattr(_tg120.Bot, name, wrapper)


for _qx120_name in ("send_message", "edit_message_text", "edit_message_reply_markup",
                   "send_photo", "send_document"):
    with _cx120.suppress(Exception):
        _qx120_wrap(_qx120_name)


# ─────────────────────────────────────────────────────────────────────────────
# 3) Student menu keyboard itself — clean at the source too
# ─────────────────────────────────────────────────────────────────────────────
_qx120_prev_student_kb = globals().get("_qx112_student_menu_kb")

if callable(_qx120_prev_student_kb):
    def _qx112_student_menu_kb():  # noqa: F811
        kb = _qx120_prev_student_kb()
        cleaned = _qx120_filter_markup(kb)
        return cleaned if cleaned is not None else kb

    globals()["_qx112_student_menu_kb"] = _qx112_student_menu_kb


with _cx120.suppress(Exception):
    _qx_log.info("[SECTION 120] student surface + inbox delivery fix loaded.")  # type: ignore[name-defined]
