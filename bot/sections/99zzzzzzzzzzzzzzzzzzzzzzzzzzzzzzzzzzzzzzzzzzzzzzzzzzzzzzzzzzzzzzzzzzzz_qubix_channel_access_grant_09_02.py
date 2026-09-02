# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 149 (2026-09-02) — ADVANCED CHANNEL ACCESS GRANT (/adch)
#
#   /adch <user_id>   → ঐ ইউজার owner-এর সব চ্যানেলের access পায়।
#   /rmch <user_id>   → access ফিরিয়ে নেওয়া।
#   /chaccess         → কাকে কাকে access দেওয়া হয়েছে তার তালিকা।
#
#   Granted user-এর জন্য:
#     • owner-এর channel তালিকা + সিরিয়াল হুবহু একই ভাবে দেখা যায়
#     • owner-এর prefix / explanation link / score template / score on-off
#       সবকিছুই আগের মতোই কাজ করে — নতুন করে কিছু সেট করতে হয় না
#     • সে শুধু quiz generation + ঐ চ্যানেলে publish করতে পারে
#       (/post, /p, /postemoji, /listchannels) — অন্য কোনো admin/owner
#       কমান্ড খোলে না
#
#   Additive only: কোনো পুরোনো global মুছে ফেলা বা re-route করা হয়নি।
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx149
import time as _t149


def _qx149_log(message, level="info"):
    with _cx149.suppress(Exception):
        getattr(logger, str(level), logger.info)("[S149] %s", message)  # type: ignore[name-defined]


def _qx149_box(title, body, emoji="🔑"):
    boxer = globals().get("ui_box_html")
    if callable(boxer):
        with _cx149.suppress(Exception):
            return boxer(title, body, emoji=emoji)
    return "%s <b>%s</b>\n%s" % (emoji, title, body)


def _qx149_h(value):
    helper = globals().get("h")
    if callable(helper):
        with _cx149.suppress(Exception):
            return helper(value)
    return str(value)


# ─────────────────────────────────────────────────────────────────────────────
# 1) Storage
# ─────────────────────────────────────────────────────────────────────────────
_QX149_TABLE = "qubix_channel_access"


def _qx149_init():
    with _cx149.suppress(Exception):
        conn = db_connect()  # type: ignore[name-defined]
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS %s ("
                "user_id INTEGER PRIMARY KEY, "
                "owner_id INTEGER NOT NULL DEFAULT 0, "
                "name TEXT NOT NULL DEFAULT '', "
                "created_at REAL NOT NULL DEFAULT 0)" % _QX149_TABLE
            )
            conn.commit()
        finally:
            conn.close()


_qx149_init()


def _qx149_grant(user_id, owner_id, name=""):
    conn = db_connect()  # type: ignore[name-defined]
    try:
        conn.execute(
            "INSERT OR REPLACE INTO %s(user_id,owner_id,name,created_at) "
            "VALUES(?,?,?,?)" % _QX149_TABLE,
            (int(user_id), int(owner_id or 0), str(name or ""), _t149.time()),
        )
        conn.commit()
    finally:
        conn.close()
    _QX149_CACHE.clear()


def _qx149_revoke(user_id) -> bool:
    conn = db_connect()  # type: ignore[name-defined]
    try:
        cur = conn.execute("DELETE FROM %s WHERE user_id=?" % _QX149_TABLE, (int(user_id),))
        conn.commit()
        removed = int(getattr(cur, "rowcount", 0) or 0) > 0
    finally:
        conn.close()
    _QX149_CACHE.clear()
    return removed


def _qx149_rows():
    with _cx149.suppress(Exception):
        conn = db_connect()  # type: ignore[name-defined]
        try:
            return list(conn.execute(
                "SELECT user_id,owner_id,name,created_at FROM %s "
                "ORDER BY created_at ASC" % _QX149_TABLE
            ).fetchall())
        finally:
            conn.close()
    return []


_QX149_CACHE = {}      # uid -> (owner_id, ts)
_QX149_TTL = 15.0


def _qx149_owner_of(uid):
    """Owner id whose channels `uid` may use, or 0."""
    try:
        uid = int(uid or 0)
    except Exception:
        return 0
    if uid <= 0:
        return 0
    now = _t149.time()
    cached = _QX149_CACHE.get(uid)
    if cached and (now - cached[1]) < _QX149_TTL:
        return cached[0]
    owner_id = 0
    with _cx149.suppress(Exception):
        conn = db_connect()  # type: ignore[name-defined]
        try:
            row = conn.execute(
                "SELECT owner_id FROM %s WHERE user_id=?" % _QX149_TABLE, (uid,)
            ).fetchone()
        finally:
            conn.close()
        if row:
            owner_id = int(row[0] or 0)
            if owner_id <= 0:
                owner_id = _qx149_primary_owner()
    _QX149_CACHE[uid] = (owner_id, now)
    return owner_id


def _qx149_primary_owner() -> int:
    with _cx149.suppress(Exception):
        ids = globals().get("OWNER_IDS") or ()
        for oid in ids:
            with _cx149.suppress(Exception):
                if int(oid) > 0:
                    return int(oid)
    with _cx149.suppress(Exception):
        return int(globals().get("OWNER_ID") or 0)
    return 0


def _qx149_has(uid) -> bool:
    return _qx149_owner_of(uid) > 0


globals()["_qx149_has_channel_access"] = _qx149_has
globals()["_qx149_channel_owner_of"] = _qx149_owner_of


# ─────────────────────────────────────────────────────────────────────────────
# 2) Channel surface — granted user sees the owner's channels as-is
# ─────────────────────────────────────────────────────────────────────────────
_qx149_prev_ch_list = globals().get("channel_list_for_user")
_qx149_prev_ch_get = globals().get("channel_get_by_id_for_user")

if callable(_qx149_prev_ch_list):
    def channel_list_for_user(requester_id):  # noqa: F811
        owner_id = _qx149_owner_of(requester_id)
        if owner_id and owner_id != int(requester_id or 0):
            with _cx149.suppress(Exception):
                return _qx149_prev_ch_list(owner_id)
        return _qx149_prev_ch_list(requester_id)

    globals()["channel_list_for_user"] = channel_list_for_user

if callable(_qx149_prev_ch_get):
    def channel_get_by_id_for_user(requester_id, channel_id):  # noqa: F811
        owner_id = _qx149_owner_of(requester_id)
        if owner_id and owner_id != int(requester_id or 0):
            with _cx149.suppress(Exception):
                return _qx149_prev_ch_get(owner_id, channel_id)
        return _qx149_prev_ch_get(requester_id, channel_id)

    globals()["channel_get_by_id_for_user"] = channel_get_by_id_for_user


# Owner's saved score template / score toggle / explanation mode follow along.
_qx149_prev_score_tpl = globals().get("_qx106_score_template")
if callable(_qx149_prev_score_tpl):
    def _qx106_score_template(uid, chat_id):  # noqa: F811
        owner_id = _qx149_owner_of(uid)
        if owner_id and owner_id != int(uid or 0):
            with _cx149.suppress(Exception):
                tpl, title = _qx149_prev_score_tpl(owner_id, chat_id)
                if tpl or title:
                    return tpl, title
        return _qx149_prev_score_tpl(uid, chat_id)

    globals()["_qx106_score_template"] = _qx106_score_template

_qx149_prev_score_on = globals().get("_score_reply_enabled")
if callable(_qx149_prev_score_on):
    def _score_reply_enabled(admin_id):  # noqa: F811
        owner_id = _qx149_owner_of(admin_id)
        if owner_id and owner_id != int(admin_id or 0):
            with _cx149.suppress(Exception):
                return bool(_qx149_prev_score_on(owner_id))
        return _qx149_prev_score_on(admin_id)

    globals()["_score_reply_enabled"] = _score_reply_enabled

_qx149_prev_explain_on = globals().get("explain_mode_on")
if callable(_qx149_prev_explain_on):
    def explain_mode_on(user_id):  # noqa: F811
        owner_id = _qx149_owner_of(user_id)
        if owner_id and owner_id != int(user_id or 0):
            with _cx149.suppress(Exception):
                return bool(_qx149_prev_explain_on(owner_id))
        return _qx149_prev_explain_on(user_id)

    globals()["explain_mode_on"] = explain_mode_on


# ─────────────────────────────────────────────────────────────────────────────
# 3) Role surfaces — granted user is a publisher, never a "student" surface
# ─────────────────────────────────────────────────────────────────────────────
_qx149_prev_role = globals().get("_qx119_role")
if callable(_qx149_prev_role):
    def _qx119_role(uid):  # noqa: F811
        role = "master"
        with _cx149.suppress(Exception):
            role = str(_qx149_prev_role(uid) or "master")
        if role != "owner" and _qx149_has(uid):
            return "master"
        return role

    globals()["_qx119_role"] = _qx119_role


def _qx149_wrap_student_flag(name):
    prev = globals().get(name)
    if not callable(prev):
        return

    def wrapper(value, _prev=prev):
        if _qx149_has(value):
            return False
        with _cx149.suppress(Exception):
            return bool(_prev(value))
        return False

    globals()[name] = wrapper


for _qx149_flag in ("_qx114_is_student", "_qx115_student",
                    "_qx120_is_student_chat", "_qx121_is_student"):
    _qx149_wrap_student_flag(_qx149_flag)


# Image / PDF → quiz needs the vision grant as well.
_qx149_prev_vision = globals().get("can_use_vision")
if callable(_qx149_prev_vision):
    def can_use_vision(user_id):  # noqa: F811
        if _qx149_has(user_id):
            return True
        with _cx149.suppress(Exception):
            return bool(_qx149_prev_vision(user_id))
        return False

    globals()["can_use_vision"] = can_use_vision


# ─────────────────────────────────────────────────────────────────────────────
# 4) Narrow elevation — publish commands only, nothing else
# ─────────────────────────────────────────────────────────────────────────────
_QX149_ELEVATED = set()

_qx149_prev_is_admin = globals().get("is_admin")
if callable(_qx149_prev_is_admin):
    def is_admin(user_id):  # noqa: F811
        with _cx149.suppress(Exception):
            if int(user_id or 0) in _QX149_ELEVATED:
                return True
        with _cx149.suppress(Exception):
            return bool(_qx149_prev_is_admin(user_id))
        return False

    globals()["is_admin"] = is_admin


def _qx149_publish_shim(name):
    """Allow granted users through an admin-gated publish command."""
    prev = globals().get(name)
    if not callable(prev) or getattr(prev, "_qx149", False):
        return

    async def wrapper(update, context, _prev=prev):
        uid = 0
        with _cx149.suppress(Exception):
            uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
        elevated = bool(uid) and _qx149_has(uid)
        if elevated:
            _QX149_ELEVATED.add(uid)
        try:
            return await _prev(update, context)
        finally:
            if elevated:
                _QX149_ELEVATED.discard(uid)

    wrapper._qx149 = True  # type: ignore[attr-defined]
    globals()[name] = wrapper


for _qx149_cmd in ("cmd_post", "cmd_postemoji", "cmd_listchannels"):
    _qx149_publish_shim(_qx149_cmd)


# ─────────────────────────────────────────────────────────────────────────────
# 5) Owner commands
# ─────────────────────────────────────────────────────────────────────────────
_QX149_USAGE = (
    "<b>ব্যবহার</b>\n"
    "<code>/adch &lt;user id&gt;</code> — ঐ ইউজারকে আপনার সব চ্যানেলের access দিন\n"
    "<code>/rmch &lt;user id&gt;</code> — access ফিরিয়ে নিন\n"
    "<code>/chaccess</code> — access পাওয়া ইউজারদের তালিকা\n\n"
    "reply করেও দেওয়া যায় — ঐ ইউজারের মেসেজে reply করে <code>/adch</code>।"
)


def _qx149_target(update, context):
    args = list(getattr(context, "args", None) or [])
    digits = str(args[0]).strip() if args else ""
    with _cx149.suppress(Exception):
        digits = digits.translate({ord(c): str(i) for i, c in enumerate("০১২৩৪৫৬৭৮৯")})
    if digits.lstrip("-").isdigit():
        return int(digits), ""
    message = getattr(update, "effective_message", None)
    reply = getattr(message, "reply_to_message", None)
    user = getattr(reply, "from_user", None)
    if user is not None:
        with _cx149.suppress(Exception):
            return int(user.id), str(getattr(user, "full_name", "") or "")
    return 0, ""


def _qx149_is_owner(update) -> bool:
    uid = 0
    with _cx149.suppress(Exception):
        uid = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    with _cx149.suppress(Exception):
        checker = globals().get("_qx_real_owner")
        if callable(checker):
            return bool(checker(uid))
    with _cx149.suppress(Exception):
        return bool(is_owner(uid))  # type: ignore[name-defined]
    return False


async def _qx149_reply(update, text):
    with _cx149.suppress(Exception):
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.HTML, disable_web_page_preview=True,  # type: ignore[name-defined]
        )


async def qx149_cmd_adch(update, context):
    if not _qx149_is_owner(update):
        return
    owner_id = int(getattr(getattr(update, "effective_user", None), "id", 0) or 0)
    target, name = _qx149_target(update, context)
    if target <= 0:
        await _qx149_reply(update, _qx149_box("Channel Access", _QX149_USAGE, "🔑"))
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    if target == owner_id:
        await _qx149_reply(update, _qx149_box(
            "Channel Access", "নিজেকে access দেওয়ার দরকার নেই।", "ℹ️"))
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    if not name:
        with _cx149.suppress(Exception):
            chat = await context.bot.get_chat(target)
            name = str(getattr(chat, "full_name", "") or getattr(chat, "title", "") or "")
    _qx149_grant(target, owner_id, name)

    channels = []
    with _cx149.suppress(Exception):
        channels = list(channel_list_for_user(owner_id) or [])  # type: ignore[name-defined]
    lines = []
    for serial, ch in enumerate(channels[:10], start=1):
        title = str(getattr(ch, "title", "") or getattr(ch, "channel_chat_id", "?"))[:28]
        lines.append("<code>%d</code> · %s" % (serial, _qx149_h(title)))
    body = (
        "👤 <b>%s</b>\n🆔 <code>%d</code>\n\n"
        "✅ আপনার <b>%d</b>টি চ্যানেলের access দেওয়া হলো।\n"
        "⚙️ আপনার সেট করা prefix · explanation link · score format সবই "
        "আগের মতোই থাকবে — তাকে নতুন কিছু সেট করতে হবে না।\n"
        "📤 সে শুধু quiz তৈরি করে <code>/post &lt;সিরিয়াল&gt;</code> দিয়ে "
        "পাঠাতে পারবে।"
        % (_qx149_h(name or "User"), target, len(channels))
    )
    if lines:
        body += "\n\n<b>চ্যানেল সিরিয়াল</b>\n" + "\n".join(lines)
    await _qx149_reply(update, _qx149_box("Advanced Channel Access দেওয়া হলো", body, "🔑"))

    with _cx149.suppress(Exception):
        notice = (
            "🔑 <b>Advanced Channel Access</b>\n\n"
            "আপনাকে চ্যানেলে quiz publish করার access দেওয়া হয়েছে।\n"
            "সব সেটিংস আগে থেকেই তৈরি — আপনাকে কিছু সেট করতে হবে না।\n\n"
            "📋 <code>/listchannels</code> — চ্যানেল সিরিয়াল দেখুন\n"
            "📤 <code>/post &lt;সিরিয়াল&gt;</code> — buffer-এর quiz চ্যানেলে পাঠান\n"
            "🎯 <code>/postemoji &lt;সিরিয়াল&gt;</code> — emoji quiz আকারে পাঠান"
        )
        await context.bot.send_message(
            chat_id=target, text=notice,
            parse_mode=ParseMode.HTML, disable_web_page_preview=True,  # type: ignore[name-defined]
        )
    _qx149_log("channel access granted: %s by %s" % (target, owner_id))
    raise ApplicationHandlerStop  # type: ignore[name-defined]


async def qx149_cmd_rmch(update, context):
    if not _qx149_is_owner(update):
        return
    target, _name = _qx149_target(update, context)
    if target <= 0:
        await _qx149_reply(update, _qx149_box("Channel Access", _QX149_USAGE, "🔑"))
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    removed = _qx149_revoke(target)
    body = ("🆔 <code>%d</code>\n\n%s" % (
        target,
        "❎ channel access সরিয়ে দেওয়া হয়েছে।" if removed
        else "ℹ️ এই ইউজারের কোনো channel access ছিল না।"))
    await _qx149_reply(update, _qx149_box("Channel Access", body, "🔑"))
    with _cx149.suppress(Exception):
        if removed:
            await context.bot.send_message(
                chat_id=target,
                text="ℹ️ আপনার channel publish access সরিয়ে নেওয়া হয়েছে।",
            )
    raise ApplicationHandlerStop  # type: ignore[name-defined]


async def qx149_cmd_chaccess(update, context):
    if not _qx149_is_owner(update):
        return
    rows = _qx149_rows()
    if not rows:
        body = "এখনো কাউকে channel access দেওয়া হয়নি।\n\n" + _QX149_USAGE
        await _qx149_reply(update, _qx149_box("Channel Access", body, "🔑"))
        raise ApplicationHandlerStop  # type: ignore[name-defined]
    lines = []
    for index, row in enumerate(rows, start=1):
        uid = int(row[0] or 0)
        name = str(row[2] or "User")
        lines.append("<code>%d</code> · %s — <code>%d</code>" % (index, _qx149_h(name), uid))
    body = "মোট <b>%d</b> জন:\n\n%s\n\n%s" % (len(rows), "\n".join(lines[:40]), _QX149_USAGE)
    await _qx149_reply(update, _qx149_box("Channel Access তালিকা", body, "🔑"))
    raise ApplicationHandlerStop  # type: ignore[name-defined]


# ─────────────────────────────────────────────────────────────────────────────
# 6) Backup scope — grants mirror to the cloud like every other owner save
# ─────────────────────────────────────────────────────────────────────────────
with _cx149.suppress(Exception):
    _tables149 = list(globals().get("QX100_BACKUP_TABLES") or [])
    if _QX149_TABLE not in {str(row[0]) for row in _tables149}:
        _tables149.append((_QX149_TABLE, _QX149_TABLE, "user_id", "Channel access grants"))
    globals()["QX100_BACKUP_TABLES"] = _tables149
    QX100_BACKUP_TABLES = _tables149
    globals()["_MONGO_TABLES"] = [(t, c, k) for (t, c, k, _l) in _tables149]
    globals()["QX100_LABELS"] = {t: l for (t, _c, _k, l) in _tables149}


# ─────────────────────────────────────────────────────────────────────────────
# 7) Owner command menu
# ─────────────────────────────────────────────────────────────────────────────
def _qx149_install_owner_menu():
    sections = globals().get("PRIVATE_COMMAND_SECTIONS")
    if not isinstance(sections, dict) or not isinstance(sections.get("owner"), list):
        return
    with _cx149.suppress(Exception):
        known = {str(row[0]) for row in sections["owner"] if row}
        for entry in (
            ("adch", "ইউজারকে সব চ্যানেলের access দিন"),
            ("rmch", "চ্যানেল access ফিরিয়ে নিন"),
            ("chaccess", "channel access পাওয়া ইউজারের তালিকা"),
        ):
            if entry[0] not in known:
                sections["owner"].append(entry)
        sections["owner"].sort(key=lambda item: str(item[0]).lower())


_qx149_install_owner_menu()


# ─────────────────────────────────────────────────────────────────────────────
# 8) Wiring
# ─────────────────────────────────────────────────────────────────────────────
_qx149_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx149_prev_build_app() if callable(_qx149_prev_build_app) else None
    if app is None:
        return app
    with _cx149.suppress(Exception):
        _qx149_init()
    register = globals().get("_register_dual_command")
    for name, handler in (
        ("adch", qx149_cmd_adch),
        ("rmch", qx149_cmd_rmch),
        ("chaccess", qx149_cmd_chaccess),
    ):
        with _cx149.suppress(Exception):
            if callable(register):
                register(app, name, handler, group=-3400)
            else:
                app.add_handler(CommandHandler(name, handler), group=-3400)  # type: ignore[name-defined]
    _qx149_log("/adch · /rmch · /chaccess wired (advanced channel access)")
    return app
