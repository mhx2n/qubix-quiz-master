# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 132 (2026-08-10) — 20s Mistral failover + owner /model control panel
#
# Problem: when the default provider chain stalls (rate limit, empty JSON,
# slow lane), a whole .gen run can sit for minutes and return 0 items.
#
# Fix:
#   * Every batch call gets a hard 20s deadline on the default chain.
#     If it produces nothing in 20s (or errors), the same prompt is sent to
#     Mistral's advanced text model, which returns std/med/engg/versity quizzes
#     WITH explanations in the source language.
#   * Health/latency telemetry per engine, visible to the owner via /model,
#     with buttons to force Auto / Default / Mistral and to switch the
#     Mistral model (speed vs quality) + a live speed test.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a132
import contextlib as _cx132
import time as _t132
import requests as _rq132
from concurrent.futures import ThreadPoolExecutor as _TPE132

from telegram import InlineKeyboardButton as _IKB132, InlineKeyboardMarkup as _IKM132
from telegram.constants import ParseMode as _PM132
from telegram.ext import ApplicationHandlerStop as _AHS132, CallbackQueryHandler as _CQH132, CommandHandler as _CH132


def _log132(message, level="info"):
    with _cx132.suppress(Exception):
        getattr(logger, level)("[S132] %s", message)  # type: ignore[name-defined]


_QX132_DEADLINE = 20.0          # seconds allowed for the default chain
_QX132_MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
_QX132_MODELS = [
    ("mistral-large-latest", "Large · সবচেয়ে নির্ভুল"),
    ("mistral-medium-latest", "Medium · ব্যালান্সড"),
    ("mistral-small-latest", "Small · দ্রুততম"),
    ("open-mistral-nemo", "Nemo · হালকা/ফাস্ট"),
]
_QX132_POOL = _TPE132(max_workers=8)

_QX132_STATS = {
    "default": {"ok": 0, "fail": 0, "ms": 0, "last": "", "items": 0},
    "mistral": {"ok": 0, "fail": 0, "ms": 0, "last": "", "items": 0},
}


def _qx132_engine():
    with _cx132.suppress(Exception):
        val = str(get_setting("qx132_engine", "auto") or "auto").lower()  # type: ignore[name-defined]
        if val in ("auto", "default", "mistral"):
            return val
    return "auto"


def _qx132_set_engine(value):
    with _cx132.suppress(Exception):
        set_setting("qx132_engine", str(value))  # type: ignore[name-defined]


def _qx132_model():
    with _cx132.suppress(Exception):
        val = str(get_setting("qx132_mistral_model", "") or "").strip()  # type: ignore[name-defined]
        if val:
            return val
    return _QX132_MODELS[0][0]


def _qx132_set_model(value):
    with _cx132.suppress(Exception):
        set_setting("qx132_mistral_model", str(value))  # type: ignore[name-defined]


def _qx132_keys():
    keys = []
    getter = globals().get("get_mistral_api_keys")
    if callable(getter):
        with _cx132.suppress(Exception):
            for row in getter() or []:
                secret = str((row or {}).get("api_key") or (row or {}).get("secret") or "").strip()
                if secret and (row or {}).get("enabled", 1):
                    keys.append(secret)
    single = globals().get("get_mistral_api_key")
    if callable(single):
        with _cx132.suppress(Exception):
            one = str(single() or "").strip()
            if one and one not in keys:
                keys.append(one)
    with _cx132.suppress(Exception):
        env = str(os.getenv("MISTRAL_API_KEY", "") or "").strip()  # type: ignore[name-defined]
        if env and env not in keys:
            keys.append(env)
    return keys


def _qx132_note(engine, ok, ms, items=0, error=""):
    row = _QX132_STATS.setdefault(engine, {"ok": 0, "fail": 0, "ms": 0, "last": "", "items": 0})
    row["ms"] = int(ms)
    if ok:
        row["ok"] += 1
        row["items"] += int(items or 0)
        row["last"] = "ok"
    else:
        row["fail"] += 1
        row["last"] = (str(error) or "failed")[:90]


def _qx132_parse(raw):
    out = []
    grab = globals().get("_json_items_74")
    salvage = globals().get("_partial_json_items_74")
    norm = globals().get("_normalise_mcq_74")
    parsed = []
    if callable(grab):
        with _cx132.suppress(Exception):
            parsed = list(grab(raw) or [])
    if not parsed and callable(salvage):
        with _cx132.suppress(Exception):
            parsed = list(salvage(raw) or [])
    for item in parsed:
        if not callable(norm):
            break
        with _cx132.suppress(Exception):
            good = norm(item)
            if good:
                out.append(good)
    return out


def _qx132_mistral_raw(prompt, *, timeout=45, model=None):
    keys = _qx132_keys()
    if not keys:
        raise RuntimeError("Mistral API key নেই (/mistral দিয়ে key যোগ করুন)।")
    use_model = str(model or _qx132_model())
    last = ""
    for key in keys[:4]:
        payload = {
            "model": use_model,
            "messages": [
                {"role": "system", "content":
                    "You are an elite Bangladeshi exam-quiz author. Return STRICT valid JSON only, no markdown. "
                    "Keep the SAME language as the source text (Bangla source => Bangla output). "
                    "Every MCQ must have exactly 4 options, one correct answer index, and a short exam-style explanation."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.15,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": "Bearer %s" % key, "Content-Type": "application/json"}
        try:
            resp = _rq132.post(_QX132_MISTRAL_URL, json=payload, headers=headers, timeout=timeout)
            if resp.status_code in (400, 422):
                payload.pop("response_format", None)
                resp = _rq132.post(_QX132_MISTRAL_URL, json=payload, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                last = "HTTP %s: %s" % (resp.status_code, (resp.text or "")[:160])
                continue
            data = resp.json()
            return str(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
        except Exception as error:
            last = str(error)[:160]
            continue
    raise RuntimeError(last or "Mistral request failed")


def _qx132_mistral_batch(source_text, need, *, easy=0, medium=0, hard=0, avoid_text=""):
    builder = globals().get("_make_fast_new_mcq_prompt_74")
    if not callable(builder):
        raise RuntimeError("prompt builder unavailable")
    prompt = builder(source_text, need, easy=easy, medium=medium, hard=hard, avoid_text=avoid_text)
    started = _t132.time()
    try:
        raw = _qx132_mistral_raw(prompt, timeout=45)
    except Exception as error:
        _qx132_note("mistral", False, (_t132.time() - started) * 1000, error=str(error))
        raise
    items = _qx132_parse(raw)
    _qx132_note("mistral", bool(items), (_t132.time() - started) * 1000,
                items=len(items), error="no valid MCQ JSON")
    return items


globals()["_qx132_mistral_batch"] = _qx132_mistral_batch


_qx132_prev_batch = globals().get("_generate_batch_fast_74")


if callable(_qx132_prev_batch):

    def _generate_batch_fast_74(source_text, need, *, easy=0, medium=0, hard=0, avoid_text=""):  # noqa: F811
        engine = _qx132_engine()

        def _mistral():
            with _cx132.suppress(Exception):
                return _qx132_mistral_batch(source_text, need, easy=easy, medium=medium,
                                            hard=hard, avoid_text=avoid_text)
            return []

        if engine == "mistral":
            got = _mistral()
            if got:
                return got
            engine = "default"

        started = _t132.time()
        future = _QX132_POOL.submit(_qx132_prev_batch, source_text, need,
                                    easy=easy, medium=medium, hard=hard, avoid_text=avoid_text)
        items = []
        error = ""
        try:
            items = list(future.result(timeout=_QX132_DEADLINE) or [])
        except Exception as exc:
            error = type(exc).__name__ if not str(exc) else str(exc)[:120]
        _qx132_note("default", bool(items), (_t132.time() - started) * 1000,
                    items=len(items), error=error or "empty in 20s")
        if items:
            return items
        if engine == "default":
            # Owner forced default-only: still wait for the slow lane result.
            with _cx132.suppress(Exception):
                return list(future.result(timeout=60) or [])
            return []

        _log132("default chain gave 0 in %.1fs — switching to Mistral" % (_t132.time() - started))
        got = _mistral()
        if got:
            return got
        # Last chance: the slow default lane may still land.
        with _cx132.suppress(Exception):
            return list(future.result(timeout=45) or [])
        return []

    globals()["_generate_batch_fast_74"] = _generate_batch_fast_74
    _log132("20s failover wired: default chain -> Mistral advanced text model")


def _qx132_ms(row):
    ms = int(row.get("ms") or 0)
    if ms <= 0:
        return "—"
    if ms < 1000:
        return "%d ms" % ms
    return "%.1f s" % (ms / 1000.0)


def _qx132_panel_text():
    engine = _qx132_engine()
    model = _qx132_model()
    keys = _qx132_keys()
    label = {"auto": "Auto (Default → 20s → Mistral)",
             "default": "শুধু Default chain",
             "mistral": "শুধু Mistral"}.get(engine, engine)
    lines = [
        "🧠 <b>AI Engine Panel</b>",
        "│ Mode: <b>%s</b>" % h(label),  # type: ignore[name-defined]
        "│ Mistral model: <code>%s</code>" % h(model),  # type: ignore[name-defined]
        "│ Mistral keys: <b>%d</b>" % len(keys),
        "│ Failover deadline: <b>%ds</b>" % int(_QX132_DEADLINE),
        "",
        "<b>Live health</b>",
    ]
    for name, title in (("default", "Default chain"), ("mistral", "Mistral")):
        row = _QX132_STATS.get(name) or {}
        lines.append(
            "│ %s — ok <b>%s</b> · fail <b>%s</b> · quiz <b>%s</b> · শেষ কল <b>%s</b>"
            % (h(title), row.get("ok", 0), row.get("fail", 0),  # type: ignore[name-defined]
               row.get("items", 0), _qx132_ms(row))
        )
        note = str(row.get("last") or "")
        if note and note != "ok":
            lines.append("│ ↳ <i>%s</i>" % h(note))  # type: ignore[name-defined]
    lines.append("")
    lines.append("যেটা দ্রুত রেসপন্স দিচ্ছে সেটাই বেছে নিন — নিচের বাটন দিয়ে।")
    return "\n".join(lines)


def _qx132_panel_kb():
    engine = _qx132_engine()
    model = _qx132_model()
    tick = lambda flag: "✅ " if flag else ""
    rows = [
        [
            _IKB132(tick(engine == "auto") + "Auto", callback_data="qx132:e:auto"),
            _IKB132(tick(engine == "default") + "Default", callback_data="qx132:e:default"),
            _IKB132(tick(engine == "mistral") + "Mistral", callback_data="qx132:e:mistral"),
        ]
    ]
    for name, title in _QX132_MODELS:
        rows.append([_IKB132(tick(model == name) + title, callback_data="qx132:m:%s" % name)])
    rows.append([_IKB132("⚡ Speed test", callback_data="qx132:t")])
    rows.append([_IKB132("🔄 Refresh", callback_data="qx132:r"), _IKB132("✖ Close", callback_data="qx132:x")])
    return _IKM132(rows)


async def _qx132_speed_test():
    prompt_source = "পদার্থবিজ্ঞান: নিউটনের গতিসূত্র ও ভরবেগ সংরক্ষণ।"
    result = {}
    for engine in ("default", "mistral"):
        started = _t132.time()
        try:
            worker = _qx132_mistral_batch if engine == "mistral" else _qx132_prev_batch
            items = await _a132.get_event_loop().run_in_executor(
                _QX132_POOL, lambda: worker(prompt_source, 2))
            result[engine] = "%d quiz · %.1f s" % (len(items or []), _t132.time() - started)
        except Exception as error:
            result[engine] = "❌ %s" % str(error)[:70]
    return result


async def qx132_cmd_model(update, context):
    user = update.effective_user
    if not user or not _is_owner_id(user.id):  # type: ignore[name-defined]
        raise _AHS132
    bypass = globals().get("_qx127_bypass")
    unbypass = globals().get("_qx127_unbypass")
    token = bypass() if callable(bypass) else None
    try:
        with _cx132.suppress(Exception):
            await context.bot.send_message(
                chat_id=int(user.id),
                text=_qx132_panel_text()[:4000],
                parse_mode=_PM132.HTML,
                reply_markup=_qx132_panel_kb(),
                disable_web_page_preview=True,
            )
    finally:
        if callable(unbypass):
            with _cx132.suppress(Exception):
                unbypass(token)
    raise _AHS132


async def qx132_cb(update, context):
    query = update.callback_query
    if not query:
        return
    user = update.effective_user
    if not user or not _is_owner_id(user.id):  # type: ignore[name-defined]
        with _cx132.suppress(Exception):
            await query.answer("Owner only", show_alert=True)
        raise _AHS132
    data = str(query.data or "")
    note = "আপডেট হয়েছে"
    if data == "qx132:x":
        with _cx132.suppress(Exception):
            await query.answer()
            await query.message.delete()
        raise _AHS132
    if data.startswith("qx132:e:"):
        _qx132_set_engine(data.split(":")[-1])
        note = "Engine mode সেট হয়েছে"
    elif data.startswith("qx132:m:"):
        _qx132_set_model(data.split(":", 2)[-1])
        note = "Mistral model সেট হয়েছে"
    elif data == "qx132:t":
        with _cx132.suppress(Exception):
            await query.answer("Speed test চলছে…")
        result = await _qx132_speed_test()
        note = "Default: %s | Mistral: %s" % (result.get("default", "—"), result.get("mistral", "—"))
        with _cx132.suppress(Exception):
            await query.message.reply_text("⚡ <b>Speed test</b>\n│ Default: %s\n│ Mistral: %s"
                                           % (h(result.get("default", "—")),  # type: ignore[name-defined]
                                              h(result.get("mistral", "—"))),  # type: ignore[name-defined]
                                           parse_mode=_PM132.HTML)
    with _cx132.suppress(Exception):
        await query.answer(note[:190])
    with _cx132.suppress(Exception):
        await query.edit_message_text(
            _qx132_panel_text()[:4000],
            parse_mode=_PM132.HTML,
            reply_markup=_qx132_panel_kb(),
            disable_web_page_preview=True,
        )
    raise _AHS132


with _cx132.suppress(Exception):
    _menu132 = list(globals().get("QX94_OWNER_MENU_COMMANDS") or [])
    if not any(name == "model" for name, _ in _menu132):
        _menu132.append(("model", "AI engine health + model switch (owner)"))
    globals()["QX94_OWNER_MENU_COMMANDS"] = _menu132[:99]


_qx132_prev_build = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx132_prev_build() if callable(_qx132_prev_build) else None
    if app is None:
        return app
    register = globals().get("_register_dual_command")
    for name in ("model", "engine"):
        with _cx132.suppress(Exception):
            if callable(register):
                register(app, name, qx132_cmd_model, group=-1082)
            else:
                app.add_handler(_CH132(name, qx132_cmd_model), group=-1082)
    with _cx132.suppress(Exception):
        app.add_handler(_CQH132(qx132_cb, pattern=r"^qx132:"), group=-1082)
    _log132("/model panel wired (owner engine control)")
    return app


_log132("section 132 loaded (Mistral 20s failover + /model panel)")
