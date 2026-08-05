# -*- coding: utf-8 -*-
# SECTION 127 — Owner "People" pages + per-user usage analytics + full backup scope.
#
# What this adds (owner-only surface):
#   * /people (aliases /users /accesslist) — separate pages for Student access,
#     Master access, Trial users and Bot tokens, each with a real list.
#   * Per-person analytics: name, id, tier, access mode, trial/expiry, first seen,
#     last seen, total active time, generation runs, quizzes created, bot token
#     owner + username + last active.
#   * /userstats <user_id> — the same analytic card directly.
#   * Bot tokens are rendered ONLY inside the owner's private inbox.
#   * Backup scope widened: usage analytics, grant log and qubix_settings
#     (tier + trial config) are mirrored to the cloud as well.

import contextlib as _cx127
import datetime as _dt127
import time as _t127

from telegram import InlineKeyboardButton as _IKB127, InlineKeyboardMarkup as _IKM127
from telegram.constants import ParseMode as _PM127
from telegram.ext import ApplicationHandlerStop as _AHS127

QX127_IDLE_GAP = 900.0  # >15 min of silence starts a new session
QX127_PAGE = 12


def _qx127_log(msg, level="info"):
    with _cx127.suppress(Exception):
        getattr(logger, level)("[S127] %s", msg)


def _qx127_h(text):
    fn = globals().get("h")
    return fn(str(text)) if callable(fn) else str(text)


def _qx127_box(title, body, emoji="👥"):
    box = globals().get("ui_box_html")
    if callable(box):
        return box(title, body, emoji=emoji)
    return f"{emoji} <b>{title}</b>\n\n{body}"


# ═════════════════════════════════════════════════════════════════════════════
# 1) Storage — usage analytics + grant log
# ═════════════════════════════════════════════════════════════════════════════
def _qx127_init():
    conn = db_connect()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS qubix_usage(
                   user_id        INTEGER PRIMARY KEY,
                   name           TEXT,
                   username       TEXT,
                   first_seen     REAL,
                   last_seen      REAL,
                   active_seconds REAL NOT NULL DEFAULT 0,
                   sessions       INTEGER NOT NULL DEFAULT 0,
                   gen_runs       INTEGER NOT NULL DEFAULT 0,
                   quizzes        INTEGER NOT NULL DEFAULT 0,
                   posts          INTEGER NOT NULL DEFAULT 0,
                   last_gen_at    REAL)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS qubix_grant_log(
                   id        INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id   INTEGER NOT NULL,
                   action    TEXT,
                   tier      TEXT,
                   mode      TEXT,
                   duration  REAL,
                   at        REAL,
                   note      TEXT)"""
        )
        conn.commit()
    finally:
        with _cx127.suppress(Exception):
            conn.close()


with _cx127.suppress(Exception):
    _qx127_init()


def _qx127_row(uid):
    with _cx127.suppress(Exception):
        conn = db_connect()
        try:
            return conn.execute(
                "SELECT * FROM qubix_usage WHERE user_id=?", (int(uid),)
            ).fetchone()
        finally:
            conn.close()
    return None


def _qx127_touch(uid, name="", username=""):
    """Record activity — grows active time in sessions, never on idle gaps."""
    uid = int(uid or 0)
    if uid <= 0:
        return
    now = _t127.time()
    with _cx127.suppress(Exception):
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT last_seen, active_seconds, sessions FROM qubix_usage WHERE user_id=?",
                (uid,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO qubix_usage(user_id,name,username,first_seen,last_seen,"
                    "active_seconds,sessions) VALUES(?,?,?,?,?,0,1)",
                    (uid, str(name or ""), str(username or ""), now, now),
                )
            else:
                last = float(row["last_seen"] or now)
                gap = max(0.0, now - last)
                add = gap if gap <= QX127_IDLE_GAP else 0.0
                bump = 0 if gap <= QX127_IDLE_GAP else 1
                conn.execute(
                    "UPDATE qubix_usage SET last_seen=?, active_seconds=active_seconds+?, "
                    "sessions=sessions+?, name=COALESCE(NULLIF(?,''),name), "
                    "username=COALESCE(NULLIF(?,''),username) WHERE user_id=?",
                    (now, add, bump, str(name or ""), str(username or ""), uid),
                )
            conn.commit()
        finally:
            conn.close()


def _qx127_bump(uid, quizzes=0, gen_runs=0, posts=0):
    uid = int(uid or 0)
    if uid <= 0:
        return
    _qx127_touch(uid)
    with _cx127.suppress(Exception):
        conn = db_connect()
        try:
            conn.execute(
                "UPDATE qubix_usage SET quizzes=quizzes+?, gen_runs=gen_runs+?, posts=posts+?, "
                "last_gen_at=CASE WHEN ?>0 THEN ? ELSE last_gen_at END WHERE user_id=?",
                (int(quizzes), int(gen_runs), int(posts),
                 int(quizzes) + int(gen_runs), _t127.time(), uid),
            )
            conn.commit()
        finally:
            conn.close()


def _qx127_log_grant(uid, action, tier="", mode="", duration=None, note=""):
    with _cx127.suppress(Exception):
        conn = db_connect()
        try:
            conn.execute(
                "INSERT INTO qubix_grant_log(user_id,action,tier,mode,duration,at,note) "
                "VALUES(?,?,?,?,?,?,?)",
                (int(uid or 0), str(action or ""), str(tier or ""), str(mode or ""),
                 float(duration) if duration is not None else None, _t127.time(), str(note or "")),
            )
            conn.commit()
        finally:
            conn.close()


globals()["_qx127_touch"] = _qx127_touch
globals()["_qx127_bump"] = _qx127_bump
globals()["_qx127_log_grant"] = _qx127_log_grant


# ═════════════════════════════════════════════════════════════════════════════
# 2) Hooks — count quizzes / generations / posts, and log grants
# ═════════════════════════════════════════════════════════════════════════════
_qx127_prev_buffer_add = globals().get("buffer_add")

if callable(_qx127_prev_buffer_add):
    def buffer_add(user_id, payload):  # noqa: F811
        result = _qx127_prev_buffer_add(user_id, payload)
        with _cx127.suppress(Exception):
            _qx127_bump(user_id, quizzes=1)
        return result

    globals()["buffer_add"] = buffer_add


_qx127_prev_post = globals().get("_post_buffer_to_chat")

if callable(_qx127_prev_post):
    async def _post_buffer_to_chat(context, admin_id, chat_id, items, thread_id=None,  # noqa: F811
                                   group_prefix="", group_expl_link=""):
        result = await _qx127_prev_post(
            context, admin_id, chat_id, items, thread_id, group_prefix, group_expl_link,
        )
        with _cx127.suppress(Exception):
            ok = int((result or (0, 0, None))[0] or 0)
            if ok:
                _qx127_bump(admin_id, posts=ok)
        return result

    globals()["_post_buffer_to_chat"] = _post_buffer_to_chat


_qx127_prev_access_write = globals().get("_qx_access_write")

if callable(_qx127_prev_access_write):
    def _qx_access_write(uid, mode, expires_at):  # noqa: F811
        _qx127_prev_access_write(uid, mode, expires_at)
        with _cx127.suppress(Exception):
            left = (float(expires_at) - _t127.time()) if expires_at else None
            _qx127_log_grant(uid, "access", mode=str(mode or ""), duration=left)

    globals()["_qx_access_write"] = _qx_access_write


_qx127_prev_set_tier = globals().get("_qx112_set_tier")

if callable(_qx127_prev_set_tier):
    def _qx112_set_tier(uid, tier):  # noqa: F811
        _qx127_prev_set_tier(uid, tier)
        with _cx127.suppress(Exception):
            _qx127_log_grant(uid, "tier", tier=str(tier or ""))

    globals()["_qx112_set_tier"] = _qx112_set_tier


async def qx127_activity_probe(update, context):
    """Passive tracker — never consumes the update."""
    with _cx127.suppress(Exception):
        user = getattr(update, "effective_user", None)
        if user is not None and not bool(getattr(user, "is_bot", False)):
            _qx127_touch(
                int(user.id),
                str(getattr(user, "first_name", "") or ""),
                str(getattr(user, "username", "") or ""),
            )


# ═════════════════════════════════════════════════════════════════════════════
# 3) People directory
# ═════════════════════════════════════════════════════════════════════════════
def _qx127_tier(uid):
    fn = globals().get("_qx112_tier")
    if callable(fn):
        with _cx127.suppress(Exception):
            return str(fn(int(uid)) or "")
    return ""


def _qx127_access(uid):
    fn = globals().get("_qx_access")
    if callable(fn):
        with _cx127.suppress(Exception):
            return dict(fn(int(uid)) or {})
    return {}


def _qx127_is_owner(uid):
    fn = globals().get("_qx99_is_owner")
    if callable(fn):
        with _cx127.suppress(Exception):
            return bool(fn(int(uid)))
    fn = globals().get("_qx_real_owner")
    if callable(fn):
        with _cx127.suppress(Exception):
            return bool(fn(int(uid)))
    return False


def _qx127_people():
    """[{uid,name,username,mode,tier,expires_at,token,bot_username}] for every known tenant."""
    people = {}
    with _cx127.suppress(Exception):
        conn = db_connect()
        try:
            for row in conn.execute(
                "SELECT user_id, first_name, username FROM users"
            ).fetchall():
                uid = int(row["user_id"])
                people[uid] = {
                    "uid": uid, "name": str(row["first_name"] or ""),
                    "username": str(row["username"] or ""),
                    "mode": "", "expires_at": None, "token": "", "bot_username": "",
                }
            for row in conn.execute(
                "SELECT user_id, mode, expires_at FROM qubix_access"
            ).fetchall():
                uid = int(row["user_id"])
                item = people.setdefault(uid, {
                    "uid": uid, "name": "", "username": "",
                    "token": "", "bot_username": "",
                })
                item["mode"] = str(row["mode"] or "")
                item["expires_at"] = row["expires_at"]
            for row in conn.execute(
                "SELECT user_id, token, bot_username, last_active FROM qubix_bots"
            ).fetchall():
                uid = int(row["user_id"])
                item = people.setdefault(uid, {
                    "uid": uid, "name": "", "username": "",
                    "mode": "", "expires_at": None,
                })
                item["token"] = str(row["token"] or "")
                item["bot_username"] = str(row["bot_username"] or "")
                item["bot_last_active"] = row["last_active"]
        finally:
            conn.close()
    out = []
    for uid, item in people.items():
        if _qx127_is_owner(uid):
            continue
        item["tier"] = _qx127_tier(uid)
        usage = _qx127_row(uid)
        item["usage"] = usage
        out.append(item)
    out.sort(key=lambda p: float((p.get("usage") or {}).get("last_seen") if
                                 isinstance(p.get("usage"), dict) else
                                 (p["usage"]["last_seen"] if p.get("usage") and
                                  p["usage"]["last_seen"] else 0) or 0), reverse=True)
    return out


def _qx127_bucket(person, bucket):
    tier = str(person.get("tier") or "")
    mode = str(person.get("mode") or "")
    if bucket == "student":
        return tier == "student"
    if bucket == "master":
        return tier == "master"
    if bucket == "trial":
        return mode in ("trial", "trial_expired") and tier not in ("student", "master")
    if bucket == "tokens":
        return bool(person.get("token"))
    return True


def _qx127_dur(seconds):
    try:
        seconds = int(max(0, float(seconds or 0)))
    except Exception:
        return "—"
    if seconds < 60:
        return f"{seconds}s"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _qx127_when(value):
    try:
        if not value:
            return "—"
        return _dt127.datetime.utcfromtimestamp(float(value)).strftime("%d %b %H:%M") + " UTC"
    except Exception:
        return "—"


def _qx127_usage_get(usage, key, default=0):
    if usage is None:
        return default
    with _cx127.suppress(Exception):
        value = usage[key]
        return default if value is None else value
    return default


def _qx127_label(bucket):
    return {
        "student": "🎓 Student Access",
        "master": "👑 Master Access",
        "trial": "⏳ Trial Users",
        "tokens": "🤖 Bot Tokens",
    }.get(bucket, "👥 People")


def _qx127_list_text(bucket, page=0):
    rows = [p for p in _qx127_people() if _qx127_bucket(p, bucket)]
    total = len(rows)
    start = max(0, int(page)) * QX127_PAGE
    slice_rows = rows[start:start + QX127_PAGE]
    if not total:
        body = "এই তালিকায় এখনো কেউ নেই।"
        return _qx127_box(_qx127_label(bucket), body, emoji="👥"), rows, 0

    lines = [f"মোট: <b>{total}</b> জন\n"]
    for index, person in enumerate(slice_rows, start=start + 1):
        usage = person.get("usage")
        name = _qx127_h(person.get("name") or "—")
        uname = person.get("username")
        handle = f" · @{_qx127_h(uname)}" if uname else ""
        lines.append(
            f"<b>{index}.</b> {name}{handle}\n"
            f"   🆔 <code>{int(person['uid'])}</code> · "
            f"⏱ {_qx127_dur(_qx127_usage_get(usage, 'active_seconds'))} · "
            f"🧩 {int(_qx127_usage_get(usage, 'quizzes'))} quiz\n"
            f"   📅 শেষ সক্রিয়: {_qx127_when(_qx127_usage_get(usage, 'last_seen', None))}"
        )
        if bucket == "tokens":
            bot_name = person.get("bot_username") or "—"
            lines.append(f"   🤖 @{_qx127_h(bot_name)}")
    body = "\n".join(lines)
    body += "\n\nবিস্তারিত দেখতে নিচের বাটনে চাপুন।"
    return _qx127_box(_qx127_label(bucket), body, emoji="👥"), rows, start


def _qx127_list_kb(bucket, rows, start):
    slice_rows = rows[start:start + QX127_PAGE]
    buttons = []
    line = []
    for index, person in enumerate(slice_rows, start=start + 1):
        line.append(_IKB127(str(index), callback_data=f"qx127:u:{int(person['uid'])}"))
        if len(line) == 4:
            buttons.append(line)
            line = []
    if line:
        buttons.append(line)
    page = start // QX127_PAGE
    nav = []
    if page > 0:
        nav.append(_IKB127("◀️ আগের", callback_data=f"qx127:p:{bucket}:{page - 1}"))
    if start + QX127_PAGE < len(rows):
        nav.append(_IKB127("পরের ▶️", callback_data=f"qx127:p:{bucket}:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([_IKB127("⬅️ People Home", callback_data="qx127:home")])
    buttons.append([_IKB127("✖ Close", callback_data="qx127:cl")])
    return _IKM127(buttons)


def _qx127_home_text():
    people = _qx127_people()
    counts = {b: len([p for p in people if _qx127_bucket(p, b)])
              for b in ("student", "master", "trial", "tokens")}
    quizzes = sum(int(_qx127_usage_get(p.get("usage"), "quizzes")) for p in people)
    active = sum(float(_qx127_usage_get(p.get("usage"), "active_seconds")) for p in people)
    body = (
        f"👥 মোট tenant: <b>{len(people)}</b>\n"
        f"🎓 Student: <b>{counts['student']}</b> · 👑 Master: <b>{counts['master']}</b>\n"
        f"⏳ Trial: <b>{counts['trial']}</b> · 🤖 Bot token: <b>{counts['tokens']}</b>\n"
        f"🧩 মোট quiz তৈরি: <b>{quizzes}</b>\n"
        f"⏱ মোট ব্যবহার: <b>{_qx127_dur(active)}</b>\n\n"
        "নিচের পেজ থেকে আলাদা আলাদা তালিকা ও প্রতিজনের বিশ্লেষণ দেখুন।"
    )
    return _qx127_box("People & Analytics", body, emoji="📊")


def _qx127_home_kb():
    return _IKM127([
        [_IKB127("🎓 Student list", callback_data="qx127:p:student:0"),
         _IKB127("👑 Master list", callback_data="qx127:p:master:0")],
        [_IKB127("⏳ Trial list", callback_data="qx127:p:trial:0"),
         _IKB127("🤖 Bot tokens", callback_data="qx127:p:tokens:0")],
        [_IKB127("🔄 Refresh", callback_data="qx127:home")],
        [_IKB127("✖ Close", callback_data="qx127:cl")],
    ])


def _qx127_grant_lines(uid, limit=5):
    lines = []
    with _cx127.suppress(Exception):
        conn = db_connect()
        try:
            rows = conn.execute(
                "SELECT action,tier,mode,duration,at FROM qubix_grant_log "
                "WHERE user_id=? ORDER BY id DESC LIMIT ?", (int(uid), int(limit)),
            ).fetchall()
        finally:
            conn.close()
        for row in rows:
            what = str(row["tier"] or row["mode"] or row["action"] or "—")
            span = _qx127_dur(row["duration"]) if row["duration"] else "—"
            lines.append(f"   • {_qx127_h(what)} · {span} · {_qx127_when(row['at'])}")
    return lines


def _qx127_workspace_counts(uid):
    counts = {"channels": 0, "groups": 0, "topics": 0, "anchors": 0, "buffer": 0}
    with _cx127.suppress(Exception):
        conn = db_connect()
        try:
            def _one(sql):
                with _cx127.suppress(Exception):
                    row = conn.execute(sql, (int(uid),)).fetchone()
                    return int(row[0] or 0)
                return 0
            counts["channels"] = _one("SELECT COUNT(*) FROM channels WHERE added_by=?")
            counts["groups"] = _one("SELECT COUNT(*) FROM saved_groups WHERE added_by=?")
            counts["topics"] = _one("SELECT COUNT(*) FROM group_topics WHERE added_by=?")
            counts["anchors"] = _one("SELECT COUNT(*) FROM saved_topic_anchors WHERE admin_id=?")
            counts["buffer"] = _one("SELECT COUNT(*) FROM quiz_buffer WHERE user_id=?")
        finally:
            conn.close()
    return counts


def _qx127_person_text(uid, private=True):
    uid = int(uid)
    person = None
    for candidate in _qx127_people():
        if int(candidate["uid"]) == uid:
            person = candidate
            break
    if person is None:
        return _qx127_box("User Analytics", "এই ইউজারকে পাওয়া যায়নি।", emoji="⚠️")

    usage = person.get("usage")
    access = _qx127_access(uid)
    tier = person.get("tier") or "—"
    tier_text = {"student": "🎓 Student", "master": "👑 Master"}.get(tier, "⏳ Trial / unset")
    mode = str(access.get("mode") or person.get("mode") or "—")
    remaining = access.get("remaining")
    counts = _qx127_workspace_counts(uid)

    body = [
        f"👤 নাম: <b>{_qx127_h(person.get('name') or '—')}</b>",
        f"🔗 ইউজারনেম: {('@' + _qx127_h(person['username'])) if person.get('username') else '—'}",
        f"🆔 আইডি: <code>{uid}</code>",
        f"🎫 Tier: <b>{tier_text}</b> · Access: <code>{_qx127_h(mode)}</code>",
        f"⏳ বাকি সময়: <b>{_qx127_dur(remaining) if remaining else '—'}</b>"
        f" · শেষ: {_qx127_when(person.get('expires_at'))}",
        "",
        "<b>📊 ব্যবহার বিশ্লেষণ</b>",
        f"   🗓 প্রথম: {_qx127_when(_qx127_usage_get(usage, 'first_seen', None))}",
        f"   📅 শেষ সক্রিয়: {_qx127_when(_qx127_usage_get(usage, 'last_seen', None))}",
        f"   ⏱ মোট ব্যবহার: <b>{_qx127_dur(_qx127_usage_get(usage, 'active_seconds'))}</b>"
        f" · সেশন: {int(_qx127_usage_get(usage, 'sessions'))}",
        f"   🧩 তৈরি quiz: <b>{int(_qx127_usage_get(usage, 'quizzes'))}</b>"
        f" · 🚀 পোস্ট: {int(_qx127_usage_get(usage, 'posts'))}",
        f"   🕒 শেষ generation: {_qx127_when(_qx127_usage_get(usage, 'last_gen_at', None))}",
        "",
        "<b>🗂 Workspace</b>",
        f"   📢 Channel: {counts['channels']} · 👥 Group: {counts['groups']}",
        f"   🧵 Topic: {counts['topics']} · 📌 Anchor: {counts['anchors']}",
        f"   📦 Buffer: {counts['buffer']}",
    ]

    token = str(person.get("token") or "")
    body.append("")
    body.append("<b>🤖 Personal bot</b>")
    if token:
        bot_name = person.get("bot_username") or "—"
        body.append(f"   @{_qx127_h(bot_name)} · শেষ সক্রিয়: "
                    f"{_qx127_when(person.get('bot_last_active'))}")
        if private:
            body.append(f"   🔑 Token: <code>{_qx127_h(token)}</code>")
        else:
            body.append("   🔑 Token: শুধু owner-এর private inbox-এ দেখানো হয়।")
    else:
        body.append("   — কোনো bot token সেট করা নেই।")

    grants = _qx127_grant_lines(uid)
    if grants:
        body.append("")
        body.append("<b>🧾 Access history</b>")
        body.extend(grants)

    return _qx127_box("User Analytics", "\n".join(body), emoji="🧭")


def _qx127_person_kb(uid):
    return _IKM127([
        [_IKB127("🔄 Refresh", callback_data=f"qx127:u:{int(uid)}")],
        [_IKB127("⬅️ People Home", callback_data="qx127:home")],
        [_IKB127("✖ Close", callback_data="qx127:cl")],
    ])


# ═════════════════════════════════════════════════════════════════════════════
# 4) Commands & callbacks (owner only, private inbox only)
# ═════════════════════════════════════════════════════════════════════════════
def _qx127_bypass():
    holder = globals().get("_QX99_BYPASS")
    if holder is None:
        return None
    with _cx127.suppress(Exception):
        return holder.set(True)
    return None


def _qx127_unbypass(token):
    holder = globals().get("_QX99_BYPASS")
    if holder is not None and token is not None:
        with _cx127.suppress(Exception):
            holder.reset(token)


def _qx127_update_uid(update):
    fn = globals().get("_qx99_uid")
    if callable(fn):
        with _cx127.suppress(Exception):
            return int(fn(update))
    with _cx127.suppress(Exception):
        return int(update.effective_user.id)
    return 0


def _qx127_private(update):
    with _cx127.suppress(Exception):
        return str(getattr(update.effective_chat, "type", "")) == "private"
    return False


async def qx127_cmd_people(update, context):
    message = getattr(update, "effective_message", None)
    uid = _qx127_update_uid(update)
    if message is None or not _qx127_is_owner(uid):
        raise _AHS127
    token = _qx127_bypass()
    try:
        with _cx127.suppress(Exception):
            await message.delete()
        with _cx127.suppress(Exception):
            await context.bot.send_message(
                chat_id=int(uid),  # owner inbox only
                text=_qx127_home_text()[:4000],
                parse_mode=_PM127.HTML,
                reply_markup=_qx127_home_kb(),
                disable_web_page_preview=True,
            )
    finally:
        _qx127_unbypass(token)
    raise _AHS127


async def qx127_cmd_userstats(update, context):
    message = getattr(update, "effective_message", None)
    uid = _qx127_update_uid(update)
    if message is None or not _qx127_is_owner(uid):
        raise _AHS127
    args = list(getattr(context, "args", None) or [])
    target = 0
    with _cx127.suppress(Exception):
        target = int(str(args[0]).strip())
    token = _qx127_bypass()
    try:
        if target <= 0:
            with _cx127.suppress(Exception):
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=_qx127_box(
                        "User Analytics",
                        "ব্যবহার: <code>/userstats &lt;user_id&gt;</code>\n"
                        "অথবা <code>/people</code> থেকে তালিকা দেখে বাটনে চাপুন।",
                        emoji="ℹ️",
                    ),
                    parse_mode=_PM127.HTML,
                )
            raise _AHS127
        with _cx127.suppress(Exception):
            await context.bot.send_message(
                chat_id=int(uid),
                text=_qx127_person_text(target, private=True)[:4000],
                parse_mode=_PM127.HTML,
                reply_markup=_qx127_person_kb(target),
                disable_web_page_preview=True,
            )
    finally:
        _qx127_unbypass(token)
    raise _AHS127


async def qx127_cb(update, context):
    query = getattr(update, "callback_query", None)
    if query is None:
        return
    uid = 0
    with _cx127.suppress(Exception):
        uid = int(query.from_user.id)
    if not _qx127_is_owner(uid):
        with _cx127.suppress(Exception):
            await query.answer("Owner only.", show_alert=True)
        raise _AHS127

    data = str(query.data or "")
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else "home"
    token = _qx127_bypass()
    try:
        with _cx127.suppress(Exception):
            await query.answer()
        if action == "cl":
            with _cx127.suppress(Exception):
                await query.message.delete()
            raise _AHS127

        if action == "home":
            text, kb = _qx127_home_text(), _qx127_home_kb()
        elif action == "p":
            bucket = parts[2] if len(parts) > 2 else "student"
            try:
                page = int(parts[3]) if len(parts) > 3 else 0
            except Exception:
                page = 0
            text, rows, start = _qx127_list_text(bucket, page)
            kb = _qx127_list_kb(bucket, rows, start)
        elif action == "u":
            target = 0
            with _cx127.suppress(Exception):
                target = int(parts[2])
            private = _qx127_private(update)
            text = _qx127_person_text(target, private=private)
            kb = _qx127_person_kb(target)
        else:
            text, kb = _qx127_home_text(), _qx127_home_kb()

        with _cx127.suppress(Exception):
            await query.edit_message_text(
                text[:4000], parse_mode=_PM127.HTML, reply_markup=kb,
                disable_web_page_preview=True,
            )
    finally:
        _qx127_unbypass(token)
    raise _AHS127


# ═════════════════════════════════════════════════════════════════════════════
# 5) Backup scope — analytics, grant log and settings now mirror to cloud
# ═════════════════════════════════════════════════════════════════════════════
with _cx127.suppress(Exception):
    _tables127 = list(globals().get("QX100_BACKUP_TABLES") or [])
    _known127 = {str(row[0]) for row in _tables127}
    for _entry in (
        ("qubix_settings", "qubix_settings", "key", "Settings / tiers / trial"),
        ("qubix_usage", "qubix_usage", "user_id", "Usage analytics"),
        ("qubix_grant_log", "qubix_grant_log", None, "Access history"),
    ):
        if _entry[0] not in _known127:
            _tables127.append(_entry)
    globals()["QX100_BACKUP_TABLES"] = _tables127
    QX100_BACKUP_TABLES = _tables127
    globals()["_MONGO_TABLES"] = [(t, c, k) for (t, c, k, _l) in _tables127]
    globals()["QX100_LABELS"] = {t: l for (t, _c, _k, l) in _tables127}


# ═════════════════════════════════════════════════════════════════════════════
# 6) Wiring
# ═════════════════════════════════════════════════════════════════════════════
with _cx127.suppress(Exception):
    _ws127 = globals().get("QX_WORKSPACE_COMMANDS")
    if isinstance(_ws127, set):
        _ws127 |= {"people", "users", "accesslist", "userstats"}

with _cx127.suppress(Exception):
    _pref127 = tuple(globals().get("QX_WORKSPACE_CALLBACK_PREFIXES") or ())
    if "qx127:" not in _pref127:
        globals()["QX_WORKSPACE_CALLBACK_PREFIXES"] = _pref127 + ("qx127:",)
        QX_WORKSPACE_CALLBACK_PREFIXES = globals()["QX_WORKSPACE_CALLBACK_PREFIXES"]

with _cx127.suppress(Exception):
    _menu127 = list(globals().get("QX94_OWNER_MENU_COMMANDS") or [])
    for _name, _desc in (
        ("people", "Student/Master list ও analytics"),
        ("userstats", "একজনের বিস্তারিত analytics"),
    ):
        if not any(n == _name for n, _ in _menu127):
            _menu127.append((_name, _desc))
    globals()["QX94_OWNER_MENU_COMMANDS"] = _menu127[:99]

with _cx127.suppress(Exception):
    if "/people" not in str(globals().get("QX94_OWNER_CARD") or ""):
        globals()["QX94_OWNER_CARD"] = str(globals().get("QX94_OWNER_CARD") or "") + (
            "\n<code>/people</code> — Student / Master / Trial আলাদা পেজ, "
            "প্রতিজনের ব্যবহার ও quiz analytics (bot token শুধু এখানেই)।"
            "\n<code>/userstats &lt;id&gt;</code> — একজনের সম্পূর্ণ বিশ্লেষণ।"
        )

_qx127_prev_build = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx127_prev_build() if callable(_qx127_prev_build) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    for name, handler in (
        ("people", qx127_cmd_people),
        ("users", qx127_cmd_people),
        ("accesslist", qx127_cmd_people),
        ("userstats", qx127_cmd_userstats),
    ):
        with _cx127.suppress(Exception):
            if callable(register):
                register(app, name, handler, group=-1071)
            else:
                app.add_handler(CommandHandler(name, handler), group=-1071)
    with _cx127.suppress(Exception):
        app.add_handler(
            CallbackQueryHandler(qx127_cb, pattern=r"^qx127:"), group=-1071
        )
    with _cx127.suppress(Exception):
        app.add_handler(
            MessageHandler(filters.ALL, qx127_activity_probe), group=9500
        )
    _qx127_log("owner people pages + usage analytics wired (/people, /userstats)")
    return app


_qx127_log("section 127 loaded (people analytics, token privacy, wider backup scope)")
