# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 131 (2026-08-09)
#   1) /scoreformat keeps the EXACT layout the user typed (multi-line, blank
#      lines, emoji) instead of collapsing everything into one line.
#   2) AI-generated score cards keep the literal {count} / {channel} tokens.
#   3) `.gen` on a photo/PDF shows the "Reading Questions" card instantly
#      (before the slow OCR round-trip), not after 10–12 seconds.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx131
import html as _html131
import re as _re131


def _log131(message, level="info"):
    with _cx131.suppress(Exception):
        getattr(logger, level)("[S131] %s", message)  # type: ignore[name-defined]


# ═════════════════════════════════════════════════════════════════════════════
# 1) Placeholder-safe AI card conversion
# ═════════════════════════════════════════════════════════════════════════════
_qx131_prev_ai_to_html = globals().get("_qx107_score_ai_to_html")

_QX131_PH = (
    (_re131.compile(r"\{\s*count\s*\}|\[\s*count\s*\]|<\s*count\s*>", _re131.I), "{count}"),
    (_re131.compile(r"\{\s*channel\s*\}|\[\s*channel\s*\]|<\s*channel\s*>", _re131.I), "{channel}"),
)
_QX131_TOKENS = (("{count}", "QXCOUNTTOKEN"), ("{channel}", "QXCHANNELTOKEN"))


def _qx131_normalise_placeholders(text):
    out = str(text or "")
    for pattern, canonical in _QX131_PH:
        out = pattern.sub(canonical, out)
    return out


if callable(_qx131_prev_ai_to_html):

    def _qx107_score_ai_to_html(text):  # noqa: F811
        raw = _qx131_normalise_placeholders(text)
        # Hide the braces from the markdown/HTML converter so it cannot eat them.
        for real, token in _QX131_TOKENS:
            raw = raw.replace(real, token)
        html = str(_qx131_prev_ai_to_html(raw) or "")
        for real, token in _QX131_TOKENS:
            html = html.replace(token, real)
        if "{count}" not in html:
            html += "\nমোট প্রশ্ন: <b>{count}</b>টি"
        return html[:3900]

    globals()["_qx107_score_ai_to_html"] = _qx107_score_ai_to_html


# ═════════════════════════════════════════════════════════════════════════════
# 2) /scoreformat — verbatim multi-line custom templates
# ═════════════════════════════════════════════════════════════════════════════
_qx131_prev_scoreformat = globals().get("qx106_cmd_scoreformat")


def _qx131_raw_custom(message):
    """Return everything the user typed after `/scoreformat <channel#>`,
    newlines and blank lines preserved. Prefers the HTML-with-entities form so
    bold/italic the user applied in Telegram survives too."""
    html_text = ""
    with _cx131.suppress(Exception):
        html_text = str(getattr(message, "text_html_urled", "") or "")
    plain = str(getattr(message, "text", "") or "")
    source = html_text or plain
    if not source.strip():
        return ""
    # drop the command token
    stripped = _re131.sub(r"^\s*[./][A-Za-z_]+(?:@\w+)?\s*", "", source, count=1)
    # drop the channel number token (keep the rest byte-for-byte)
    stripped = _re131.sub(r"^\s*[0-9০-৯]+[ \t]*", "", stripped, count=1)
    if not html_text:
        stripped = _html131.escape(stripped)
    return stripped.strip("\n").rstrip()


if callable(_qx131_prev_scoreformat):

    async def qx106_cmd_scoreformat(update, context):  # noqa: F811
        message = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        args = list(getattr(context, "args", None) or [])
        allowed = globals().get("_qx106_allowed")
        if (
            message is None or user is None or len(args) < 2
            or not callable(allowed) or not allowed(user.id)
        ):
            return await _qx131_prev_scoreformat(update, context)

        keyword = str(args[1]).strip().lower()
        if keyword in ("reset", "default", "off", "ai", "generate", "make"):
            return await _qx131_prev_scoreformat(update, context)

        channel_for = globals().get("_qx106_channel_for")
        renderer = globals().get("_qx106_render_score")
        channel = channel_for(user.id, args[0]) if callable(channel_for) else None
        if channel is None or not callable(renderer):
            return await _qx131_prev_scoreformat(update, context)

        rich = _qx131_normalise_placeholders(_qx131_raw_custom(message))
        if not rich:
            return await _qx131_prev_scoreformat(update, context)

        with _cx131.suppress(Exception):
            conn = db_connect()  # type: ignore[name-defined]
            try:
                conn.execute(
                    "UPDATE channels SET score_template=? WHERE id=?",
                    (rich[:3900], int(channel.id)),
                )
                conn.commit()
            finally:
                conn.close()

        preview = renderer(rich, 25, channel.title)
        pm = globals().get("_PM106") or globals().get("ParseMode")
        with _cx131.suppress(Exception):
            await message.reply_text(
                "✅ <b>Score format saved</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                + preview
                + "\n━━━━━━━━━━━━━━━━━━━━\n"
                  "যেভাবে লিখেছেন ঠিক সেভাবেই (line/blank line সহ) সেভ হয়েছে।\n"
                  "Placeholder: <code>{count}</code> · <code>{channel}</code>",
                parse_mode=getattr(pm, "HTML", "HTML"),
                disable_web_page_preview=True,
            )
        stop = globals().get("_AHS106") or globals().get("ApplicationHandlerStop")
        if stop is not None:
            raise stop
        return None

    globals()["qx106_cmd_scoreformat"] = qx106_cmd_scoreformat


# ═════════════════════════════════════════════════════════════════════════════
# 3) `.gen` on media → instant status card, OCR afterwards
# ═════════════════════════════════════════════════════════════════════════════
_qx131_prev_cmd_gen = globals().get("cmd_gen")


async def qx131_cmd_gen(update, context):
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    if message is None or user is None:
        if callable(_qx131_prev_cmd_gen):
            return await _qx131_prev_cmd_gen(update, context)
        return None

    uid = int(getattr(user, "id", 0) or 0)
    text = str(getattr(message, "text", "") or "").strip()
    tokens = [t for t in text.split()[1:] if not t.startswith("@")]
    plain_tokens = set(globals().get("_QXV_PLAIN_TOKENS") or ())
    is_media = globals().get("_qxv_reply_is_media")
    harvest = globals().get("_qxv_harvest")
    report = globals().get("_qxv_report")
    boxer = globals().get("_qxv_box")
    resolver = globals().get("_resolve_ocr_ctx_59")

    plain_media = False
    with _cx131.suppress(Exception):
        plain_media = (
            bool(tokens) is False or all(t.lower() in plain_tokens for t in tokens)
        ) and callable(is_media) and bool(is_media(message))

    if not (plain_media and callable(harvest) and callable(report)
            and callable(boxer) and callable(resolver)):
        if callable(_qx131_prev_cmd_gen):
            return await _qx131_prev_cmd_gen(update, context)
        return None

    # A PDF page-range request must keep its own dedicated flow.
    pagespec = globals().get("_QXV_PAGESPEC")
    digits = globals().get("_QXV_BN_DIGITS")
    if pagespec is not None and any(
        pagespec.match(t.translate(digits) if digits else t) for t in tokens
    ):
        if callable(_qx131_prev_cmd_gen):
            return await _qx131_prev_cmd_gen(update, context)

    # ── instant feedback, BEFORE the slow OCR round-trip ────────────────────
    status = None
    with _cx131.suppress(Exception):
        status = await message.reply_text(
            boxer("Reading Questions", "পাতাটি পড়া হচ্ছে… সব প্রশ্ন quiz-এ রূপান্তর হবে।", "🔎"),
            parse_mode=getattr(globals().get("ParseMode"), "HTML", "HTML"),
        )

    ocr_ctx = None
    with _cx131.suppress(Exception):
        ocr_ctx = await resolver(update, context, message.reply_to_message, uid)
    source_text = ""
    if isinstance(ocr_ctx, dict):
        source_text = str(
            ocr_ctx.get("clean_text") or ocr_ctx.get("raw_markdown") or ""
        ).strip()

    if source_text:
        added = dup = found = 0
        with _cx131.suppress(Exception):
            added, dup, found = await harvest(
                update, context, uid, source_text, status, "উক্ত পাতা"
            )
        with _cx131.suppress(Exception):
            if status is not None:
                await status.delete()
        if found:
            await report(update, context, uid, added, dup, found, "উক্ত পাতা")
            raise ApplicationHandlerStop  # type: ignore[name-defined]
    else:
        with _cx131.suppress(Exception):
            if status is not None:
                await status.delete()

    if callable(_qx131_prev_cmd_gen):
        return await _qx131_prev_cmd_gen(update, context)
    return None


globals()["cmd_gen"] = qx131_cmd_gen


_qx131_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx131_prev_build_app() if callable(_qx131_prev_build_app) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    with _cx131.suppress(Exception):
        if callable(register):
            register(app, "gen", qx131_cmd_gen, group=-3900)
            registered = globals().get("qx106_cmd_scoreformat")
            if callable(registered):
                register(app, "scoreformat", registered,
                         filters.ChatType.PRIVATE, group=-5200)  # type: ignore[name-defined]
        else:
            app.add_handler(CommandHandler("gen", qx131_cmd_gen), group=-3900)  # type: ignore[name-defined]
    _log131("verbatim scoreformat · placeholder-safe AI card · instant .gen card wired")
    return app


_log131("section 131 loaded")
