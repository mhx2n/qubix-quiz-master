# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 134 (2026-08-10) — OWNER COMMAND STEALTH
#
# Problem: owner-only commands (/model, /models, /gemini, /mistral, /people,
# /tokens, .addkey …) were hidden from the "/" menu of normal users, but if a
# user *typed* them the handler still ran (or the generic error card replied),
# which proved the command exists.
#
# Fix: one ultra-early guard (group -20000) inspects the first token of every
# "/" or "." command. If it maps to an owner-only command and the sender is NOT
# a real configured owner, the update is dropped **silently** — no reply, no
# error card, no typing action, nothing. From the user's side the message looks
# like ordinary text that the bot ignored, so nothing is discoverable.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx134
import re as _re134

from telegram.ext import ApplicationHandlerStop as _AHS134, MessageHandler as _MH134, filters as _f134


def _log134(msg, level="info"):
    with _cx134.suppress(Exception):
        getattr(logger, level)("[S134] %s", msg)  # type: ignore[name-defined]


# ── Commands that MUST stay usable for every normal user / student ───────────
_QX134_ALWAYS_ALLOW = {
    "start", "help", "commands", "menu", "myid", "ask", "info",
    "gen", "generate", "bc", "buffercount", "buffer", "done", "clear",
    "post", "postemoji", "pdfpages", "pdf", "pages",
    "addchannel", "listchannels", "removechannel", "setprefix", "setexplink",
    "adg", "addgroup", "listgroups", "adtc", "listtopics", "pt", "lc", "lg", "lt",
    "topic", "aitopic", "mytopics", "usetopic", "topicpin", "topicunpin", "cleartopic",
    "score", "scoreformat", "stopquiz", "resumequiz", "practice",
    "addbot", "mybot", "removebot", "myaccess", "plan",
    "solve_on", "solve_off", "probaho_on", "probaho_off", "sh", "tutorial", "porag",
}

# ── Commands that only a real owner may even *touch* ────────────────────────
_QX134_OWNER_SEED = {
    "model", "engine", "models", "gemini", "mistral", "mk",
    "addkey", "keys", "delkey", "elevenlabs", "el_log",
    "people", "userstats", "tokens", "mongobackup", "backup", "resync",
    "restart", "rp", "broadcast", "adminpanel", "dashboard", "logs", "ownerstats",
    "banned", "ban", "unban", "users", "usersd", "private_send", "ps",
    "addadmin", "removeadmin", "add", "rad", "grantall", "revokeall", "gra", "rea",
    "grantvision", "revokevision", "grvo", "revo",
    "addrequired", "delrequired", "listrequired", "addrc", "delrc", "listrc",
    "maintenance_on", "maintenance_off", "mo", "mf",
    "quizprefix", "quizlink", "qp", "qex",
    "qapprove", "qrevoke", "qtrial", "qbots", "qkill", "qusers",
    "genlimit", "setlimit", "features",
}

# Staff-tier commands: real owner OR legacy admin/staff may use them; everyone
# else gets the same silent drop.
_QX134_STAFF_ONLY = {
    "reply", "close", "col", "filter", "ban", "unban", "uban", "banned", "banl",
    "vision_on", "vision_off", "vo", "vf", "explain_on", "explain_off",
    "exo", "exf", "scanhelp", "sch", "private_send", "ps", "usersd", "uid",
    "broadcast", "adminpanel",
}

_QX134_BLOCKED: set = set()


def _qx134_aliases(name):
    out = {str(name).lower()}
    table = globals().get("COMMAND_ALIASES") or {}
    with _cx134.suppress(Exception):
        for alias in table.get(name, []) or []:
            out.add(str(alias).lower())
        for key, vals in table.items():
            if name in [str(v).lower() for v in (vals or [])]:
                out.add(str(key).lower())
                for v in vals or []:
                    out.add(str(v).lower())
    return out


def _qx134_build():
    """Owner-only set = (owner menus ∪ seed) − everything a user legitimately has."""
    owner_names = set(_QX134_OWNER_SEED)
    for key in ("QX94_OWNER_MENU_COMMANDS",):
        with _cx134.suppress(Exception):
            for item in globals().get(key) or []:
                owner_names.add(str(item[0]).lower())
    with _cx134.suppress(Exception):
        sections = globals().get("PRIVATE_COMMAND_SECTIONS") or {}
        for name, _desc in sections.get("owner", []) or []:
            owner_names.add(str(name).lower())

    allow = set(_QX134_ALWAYS_ALLOW)
    for key in ("QX94_USER_MENU_COMMANDS", "QX97_USER_MENU_COMMANDS",
                "QX112_STUDENT_MENU_COMMANDS"):
        with _cx134.suppress(Exception):
            for item in globals().get(key) or []:
                allow.add(str(item[0]).lower())
    with _cx134.suppress(Exception):
        sections = globals().get("PRIVATE_COMMAND_SECTIONS") or {}
        for name, _desc in sections.get("user", []) or []:
            allow.add(str(name).lower())

    expanded_allow = set()
    for name in allow:
        expanded_allow |= _qx134_aliases(name)

    blocked = set()
    for name in owner_names:
        for alias in _qx134_aliases(name):
            if alias and alias not in expanded_allow:
                blocked.add(alias)

    _QX134_BLOCKED.clear()
    _QX134_BLOCKED.update(blocked)
    return _QX134_BLOCKED


def _qx134_staff(uid) -> bool:
    if _qx134_real_owner(uid):
        return True
    checker = globals().get("is_admin")
    if callable(checker):
        with _cx134.suppress(Exception):
            return bool(checker(int(uid or 0)))
    return False


def _qx134_real_owner(uid) -> bool:
    checker = globals().get("_qx96_hard_owner")
    if callable(checker):
        with _cx134.suppress(Exception):
            return bool(checker(uid))
    with _cx134.suppress(Exception):
        ids = set(int(x) for x in (globals().get("OWNER_IDS") or ()))
        return int(uid or 0) in ids
    return False


_QX134_TOKEN = _re134.compile(r"^\s*[/.!]([A-Za-z0-9_]{1,32})")


def _qx134_command_token(text):
    match = _QX134_TOKEN.match(str(text or ""))
    if not match:
        return ""
    name = match.group(1).lower()
    if "@" in name:
        name = name.split("@", 1)[0]
    return name


def _qx134_is_owner_command(name) -> bool:
    if not name:
        return False
    if not _QX134_BLOCKED:
        _qx134_build()
    return name in _QX134_BLOCKED


globals()["_qx134_is_owner_command"] = _qx134_is_owner_command


async def _qx134_guard(update, context):
    message = getattr(update, "effective_message", None)
    if message is None:
        return
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    name = _qx134_command_token(text)
    if not name:
        return
    staff_tier = name in _QX134_STAFF_ONLY
    if not staff_tier and not _qx134_is_owner_command(name):
        return
    user = getattr(update, "effective_user", None)
    uid = 0
    with _cx134.suppress(Exception):
        uid = int(getattr(user, "id", 0) or 0)
    if _qx134_staff(uid) if staff_tier else _qx134_real_owner(uid):
        return
    # Silent drop: absolutely no feedback so the command stays undiscoverable.
    _log134("silently dropped owner command /%s from uid=%s" % (name, uid))
    raise _AHS134


_qx134_prev_build = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx134_prev_build() if callable(_qx134_prev_build) else None
    if app is None:
        return app
    _qx134_build()
    with _cx134.suppress(Exception):
        app.add_handler(_MH134(_f134.TEXT | _f134.COMMAND | _f134.CAPTION, _qx134_guard),
                        group=-20000)
    _log134("owner-command stealth armed (%d hidden commands)" % len(_QX134_BLOCKED))
    return app


_log134("section 134 loaded (owner command stealth)")
