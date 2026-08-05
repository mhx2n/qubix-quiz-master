# ──────────────────────────────────────────────────────────────────────────────
# Section 128 — QUBIX TOKEN VISIBILITY (2026-08-05)
#
# Fixes:
#   1. Trial users' bot tokens were memory-only, so /people → Bot Tokens and
#      /userstats reported "কোনো bot token সেট করা নেই" even though the user's
#      own bot was running. Every accepted token is now persisted (and mirrored
#      to the cloud backup) the moment it is registered.
#   2. Owner could not see the full token. The owner card now always renders the
#      complete token in the owner's private inbox, plus a live/idle state and
#      the bot @username, and a new /tokens page lists every token in full.
#
# Nothing else in the flow is touched: memory lookups still work, and every
# override falls back to the previous behaviour on any error.
# ──────────────────────────────────────────────────────────────────────────────
import contextlib as _cx128

def _qx128_log(msg):
    with _cx128.suppress(Exception):
        logger.info("[QX128] %s", msg)


# ── 1) write-through token store: trial tokens are persisted too ─────────────
class _Qx128TokenStore(dict):
    """Behaves exactly like the old in-memory dict, but also persists to DB."""

    def __setitem__(self, uid, token):
        dict.__setitem__(self, int(uid), token)
        with _cx128.suppress(Exception):
            saver = globals().get("_qx_save_bot")
            if callable(saver):
                saver(int(uid), str(token), _qx128_bot_username(int(uid)))
        with _cx128.suppress(Exception):
            push = globals().get("_qxm_push_mirror")
            if callable(push):
                push()


def _qx128_bot_username(uid):
    with _cx128.suppress(Exception):
        runner = (globals().get("_QX_RUNNERS") or {}).get(int(uid))
        name = getattr(runner, "username", "") or getattr(runner, "bot_username", "")
        if name:
            return str(name)
    with _cx128.suppress(Exception):
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT bot_username FROM qubix_bots WHERE user_id=?", (int(uid),)
            ).fetchone()
        finally:
            conn.close()
        if row and row["bot_username"]:
            return str(row["bot_username"])
    return ""


with _cx128.suppress(Exception):
    _qx128_old_tokens = globals().get("_QX_TRIAL_TOKENS") or {}
    _qx128_store = _Qx128TokenStore()
    for _uid, _tok in dict(_qx128_old_tokens).items():
        dict.__setitem__(_qx128_store, int(_uid), _tok)
    globals()["_QX_TRIAL_TOKENS"] = _qx128_store
    # backfill anything that was only in memory before this section loaded
    for _uid, _tok in dict(_qx128_store).items():
        with _cx128.suppress(Exception):
            globals()["_qx_save_bot"](int(_uid), str(_tok), _qx128_bot_username(int(_uid)))


# after a runner starts we finally know the @username — refresh the stored row
_qx128_prev_start_runner = globals().get("_qx_start_runner")

if callable(_qx128_prev_start_runner):
    async def _qx_start_runner(uid, name=""):  # noqa: F811
        ok, info = await _qx128_prev_start_runner(uid, name)
        with _cx128.suppress(Exception):
            if ok:
                tok = globals()["_qx_get_token"](int(uid))
                if tok:
                    globals()["_qx_save_bot"](int(uid), str(tok), _qx128_bot_username(int(uid)))
                    push = globals().get("_qxm_push_mirror")
                    if callable(push):
                        push()
        return ok, info


# ── 2) people list: merge DB + memory so no token is ever missing ────────────
_qx128_prev_people = globals().get("_qx127_people")

if callable(_qx128_prev_people):
    def _qx127_people():  # noqa: F811
        people = _qx128_prev_people()
        mem = dict(globals().get("_QX_TRIAL_TOKENS") or {})
        runners = globals().get("_QX_RUNNERS") or {}
        for item in people:
            with _cx128.suppress(Exception):
                uid = int(item.get("uid") or 0)
                if not item.get("token") and mem.get(uid):
                    item["token"] = str(mem[uid])
                if item.get("token") and not item.get("bot_username"):
                    item["bot_username"] = _qx128_bot_username(uid)
                runner = runners.get(uid)
                item["bot_live"] = bool(runner is not None and getattr(runner, "running", False))
        known = {int(i.get("uid") or 0) for i in people}
        for uid, tok in mem.items():
            if int(uid) in known:
                continue
            with _cx128.suppress(Exception):
                people.append({
                    "uid": int(uid), "name": "", "username": "",
                    "mode": "trial", "expires_at": None,
                    "token": str(tok), "bot_username": _qx128_bot_username(int(uid)),
                    "tier": _qx127_tier(int(uid)), "usage": _qx127_row(int(uid)),
                    "bot_live": bool((runners.get(int(uid)) is not None)
                                     and getattr(runners.get(int(uid)), "running", False)),
                })
        return people


# ── 3) owner card: always show the FULL token in the owner inbox ─────────────
_qx128_prev_person_text = globals().get("_qx127_person_text")

if callable(_qx128_prev_person_text):
    def _qx127_person_text(uid, private=True):  # noqa: F811
        text = _qx128_prev_person_text(uid, private=True)
        with _cx128.suppress(Exception):
            person = None
            for item in _qx127_people():
                if int(item.get("uid") or 0) == int(uid):
                    person = item
                    break
            if person and person.get("token"):
                tok = str(person["token"])
                live = "🟢 চালু" if person.get("bot_live") else "⚪ idle"
                extra = (
                    "\n<b>🔐 Bot token (owner only)</b>"
                    f"\n   🤖 @{_qx127_h(person.get('bot_username') or '—')} · {live}"
                    f"\n   🔑 <code>{_qx127_h(tok)}</code>"
                )
                text = text.replace("   — কোনো bot token সেট করা নেই।", extra.strip())
                if "<code>" + _qx127_h(tok) + "</code>" not in text:
                    text = text + "\n" + extra
        return text


# ── 4) /tokens — full token directory (owner private inbox only) ────────────
def _qx128_tokens_text():
    lines = []
    total = 0
    for person in _qx127_people():
        tok = str(person.get("token") or "")
        if not tok:
            continue
        total += 1
        uid = int(person.get("uid") or 0)
        live = "🟢" if person.get("bot_live") else "⚪"
        name = _qx127_h(person.get("name") or "—")
        lines.append(
            f"{live} <b>{name}</b> · <code>{uid}</code>"
            f"\n   🤖 @{_qx127_h(person.get('bot_username') or '—')}"
            f" · 🎫 {_qx127_h(person.get('tier') or person.get('mode') or '—')}"
            f"\n   🔑 <code>{_qx127_h(tok)}</code>"
        )
    if not lines:
        body = "এখনো কেউ নিজের bot token যুক্ত করেনি।"
    else:
        body = f"মোট token: <b>{total}</b>\n\n" + "\n\n".join(lines)
    return _qx127_box("Bot Tokens", body, emoji="🔐")


async def qx128_cmd_tokens(update, context):
    message = getattr(update, "effective_message", None)
    uid = _qx127_update_uid(update)
    if message is None or not _qx127_is_owner(uid):
        raise _AHS127
    bypass = _qx127_bypass()
    try:
        with _cx128.suppress(Exception):
            await message.delete()
        with _cx128.suppress(Exception):
            await context.bot.send_message(
                chat_id=int(uid),  # owner inbox only — never anywhere else
                text=_qx128_tokens_text()[:4000],
                parse_mode=_PM127.HTML,
                reply_markup=_IKM127([
                    [_IKB127("🔄 Refresh", callback_data="qx127:p:tokens:0")],
                    [_IKB127("⬅️ People Home", callback_data="qx127:home")],
                    [_IKB127("✖ Close", callback_data="qx127:cl")],
                ]),
                disable_web_page_preview=True,
            )
    finally:
        _qx127_unbypass(bypass)
    raise _AHS127


with _cx128.suppress(Exception):
    _menu128 = list(globals().get("QX94_OWNER_MENU_COMMANDS") or [])
    if not any(n == "tokens" for n, _ in _menu128):
        _menu128.append(("tokens", "সব bot token (owner inbox only)"))
    globals()["QX94_OWNER_MENU_COMMANDS"] = _menu128[:99]

_qx128_prev_build = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx128_prev_build() if callable(_qx128_prev_build) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    for name in ("tokens", "bottokens"):
        with _cx128.suppress(Exception):
            if callable(register):
                register(app, name, qx128_cmd_tokens, group=-1081)
            else:
                app.add_handler(CommandHandler(name, qx128_cmd_tokens), group=-1081)
    _qx128_log("token visibility wired (/tokens, persisted trial tokens)")
    return app


_qx128_log("section 128 loaded (owner token visibility + persistence)")
