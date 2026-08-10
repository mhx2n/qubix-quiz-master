# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 136 — GENERATION SESSION RESET · LOSSLESS POLL OPTIONS (2026-08-10)
#
# Scope is intentionally narrow:
#   • `.c` / `/c` / `.clear` / `/clear` clear the buffer AND every transient
#     OCR/generation pointer owned by that user.
#   • successful `.d` / `/d` / `.done` / `/done` export does the same reset.
#   • mathematical/chemical option text is kept verbatim; no answer option is
#     shortened merely to make its length resemble the distractors.
#
# AI generation/provider functions are not changed.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx136
import re as _re136


def _qx136_log(message, level="info"):
    with _cx136.suppress(Exception):
        getattr(logger, level)("[S136] %s", message)  # type: ignore[name-defined]


def _qx136_entry_uid(value):
    if isinstance(value, dict):
        for field in ("uid", "user_id", "owner_id", "caller"):
            with _cx136.suppress(Exception):
                if int(value.get(field) or 0) > 0:
                    return int(value.get(field))
    return 0


def _qx136_key_belongs_to_uid(key, value, uid):
    if _qx136_entry_uid(value) == uid:
        return True
    if isinstance(key, int):
        return key == uid
    text = str(key or "")
    # Known stores use uid, uid:source-hash, or tuples containing uid.
    return text == str(uid) or text.startswith(str(uid) + ":")


def _qx136_purge_mapping(mapping, uid, *, purge_ocr=False):
    if not isinstance(mapping, dict):
        return 0
    removed = 0
    for key, value in list(mapping.items()):
        belongs = _qx136_key_belongs_to_uid(key, value, uid)
        if purge_ocr and isinstance(value, dict):
            # OCR entries are keyed by Telegram message id, so ownership is
            # taken from the payload when available. Do not delete other users.
            belongs = _qx136_entry_uid(value) == uid
        if belongs:
            mapping.pop(key, None)
            removed += 1
    return removed


def _qx136_reset_generation_state(context, uid):
    """Forget this user's completed source/page flow without touching others."""
    try:
        uid = int(uid or 0)
    except Exception:
        return 0
    if uid <= 0:
        return 0

    removed = 0
    bot_data = getattr(getattr(context, "application", None), "bot_data", None)
    if isinstance(bot_data, dict):
        direct_stores = (
            "_pending_gen_state_57",
            "_pending_gen_flow_59",
            "_source_mcq_action_store_59",
            "_gen_buffer_state_56",
        )
        for name in direct_stores:
            removed += _qx136_purge_mapping(bot_data.get(name), uid)

        # OCR cache entries now carry uid when Section 136 stores them. Legacy
        # unowned entries are harmless because `.gen` resolves only the replied
        # message; new requests can no longer inherit pending-flow pointers.
        removed += _qx136_purge_mapping(
            bot_data.get("_ocr_context_store"), uid, purge_ocr=True
        )

        # Later patches created several token stores whose names may evolve.
        # Purge only entries explicitly owned by this user.
        for name, store in list(bot_data.items()):
            if name in direct_stores or name == "_ocr_context_store":
                continue
            if any(tag in str(name).lower() for tag in
                   ("genq", "pending_gen", "source_mcq", "harvest", "pdfpage")):
                removed += _qx136_purge_mapping(store, uid)

    for global_name in ("_QX102_SESSIONS", "_QX104_SESSIONS", "_QXZ_RESUME", "_QXM_TRACK"):
        removed += _qx136_purge_mapping(globals().get(global_name), uid)

    user_data = getattr(context, "user_data", None)
    if isinstance(user_data, dict):
        for key in list(user_data):
            if any(tag in str(key).lower() for tag in
                   ("gen", "ocr", "source", "pdf", "page", "harvest")):
                user_data.pop(key, None)
                removed += 1

    _qx136_log("reset transient generation state uid=%s removed=%s" % (uid, removed))
    return removed


# Add owner identity to newly remembered OCR entries so reset can safely remove
# only this user's cached source instead of flushing the shared cache.
_qx136_prev_remember_ocr = globals().get("_remember_ocr_context")
if callable(_qx136_prev_remember_ocr):
    def _remember_ocr_context(context, message_id, payload):  # noqa: F811
        enriched = dict(payload or {})
        with _cx136.suppress(Exception):
            uid = int(enriched.get("uid") or enriched.get("user_id") or 0)
            if uid <= 0:
                current = getattr(context, "_user_id", 0)
                if current:
                    enriched["uid"] = int(current)
        return _qx136_prev_remember_ocr(context, message_id, enriched)

    globals()["_remember_ocr_context"] = _remember_ocr_context


# The old parity helper shortened the *correct* answer after generation, which
# could make it disagree with the explanation. Parity must be a prompt concern;
# persisted and displayed options remain byte-for-byte equivalent after strip.
def _enforce_option_parity(item):  # noqa: F811
    return dict(item or {})


# Preserve square brackets, braces, coefficients, charges, equilibrium arrows,
# superscripts and leading symbols. Convert only explicit LaTeX commands; avoid
# the former optional-backslash regexes that also treated ordinary words as TeX.
_qx136_prev_plain = globals().get("_tg_plain_text")


def _qx136_lossless_plain(value):
    text = str(value or "")
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"')
                .replace("&apos;", "'").replace("&nbsp;", " "))
    text = _re136.sub(r"\\\(|\\\)|\\\[|\\\]", "", text)
    text = _re136.sub(r"\$(.+?)\$", r"\1", text, flags=_re136.DOTALL)
    text = _re136.sub(
        r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}",
        lambda match: "(%s)/(%s)" % (match.group(1).strip(), match.group(2).strip()),
        text,
    )
    text = _re136.sub(
        r"\\sqrt\s*\{([^{}]*)\}",
        lambda match: "√(%s)" % match.group(1).strip(),
        text,
    )
    text = _re136.sub(
        r"\\(?:text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}",
        r"\1",
        text,
    )
    text = _re136.sub(r"[ \t]+", " ", text)
    text = _re136.sub(r"\s*\n\s*", "\n", text)
    return text.strip()


def _tg_plain_text(value):  # noqa: F811
    return _qx136_lossless_plain(value)


def _sanitize_item_for_poll(item):  # noqa: F811
    output = dict(item or {})
    for field in ("questions", "option1", "option2", "option3", "option4", "option5", "explanation"):
        if field in output and output[field] is not None:
            output[field] = _qx136_lossless_plain(output[field])
    return output


# Clear command: clear rows first, then terminate all source/page sessions.
async def _qx136_cmd_clear(update, context):
    ensure_user(update)  # type: ignore[name-defined]
    user = getattr(update, "effective_user", None)
    if user is None:
        return
    uid = int(user.id)
    buffer_clear(uid)  # type: ignore[name-defined]
    _qx136_reset_generation_state(context, uid)
    with _cx136.suppress(Exception):
        await ok(update, "Buffer Cleared", "Previous generation session cleared. Reply to a new source to begin again.")  # type: ignore[name-defined]
    raise ApplicationHandlerStop  # type: ignore[name-defined]


_qx136_prev_done = globals().get("cmd_done")


async def _qx136_cmd_done(update, context):
    user = getattr(update, "effective_user", None)
    uid = int(getattr(user, "id", 0) or 0)
    before = 0
    with _cx136.suppress(Exception):
        before = int(buffer_count(uid))  # type: ignore[name-defined]
    if callable(_qx136_prev_done):
        await _qx136_prev_done(update, context)
    after = before
    with _cx136.suppress(Exception):
        after = int(buffer_count(uid))  # type: ignore[name-defined]
    # Reset only after a successful export/clear; an empty or failed export keeps
    # the active source available for retry.
    if uid > 0 and before > 0 and after == 0:
        _qx136_reset_generation_state(context, uid)
    raise ApplicationHandlerStop  # type: ignore[name-defined]


cmd_clear = _qx136_cmd_clear
cmd_done = _qx136_cmd_done


_qx136_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx136_prev_build_app() if callable(_qx136_prev_build_app) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    if callable(register):
        for command in ("clear", "c"):
            with _cx136.suppress(Exception):
                register(app, command, _qx136_cmd_clear,
                         filters.ChatType.PRIVATE, group=-6100)  # type: ignore[name-defined]
        for command in ("done", "d"):
            with _cx136.suppress(Exception):
                register(app, command, _qx136_cmd_done,
                         filters.ChatType.PRIVATE, group=-6100)  # type: ignore[name-defined]
    _qx136_log("session reset and lossless poll option layer active")
    return app
