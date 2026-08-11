# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 140 (2026-08-11) — pure explanations + 10s live tick everywhere
#
# 1) Explanations leaked answer-letter headers and markdown, e.g.
#    "**উত্তর: (d) 1, (3π/2)** ব্যাখ্যা: …", "(a) 20 ব্যাখ্যা: …",
#    "Answer: (c) — Explanation: …", "**Option Test:**".
#    Now only the reasoning body survives; the option letter is never printed.
# 2) The verbatim (PDF/image) status card only moved when a chunk finished.
#    A 10-second ticker now refreshes it continuously, matching the generation
#    lanes which already tick every 10s.
#
# No provider, prompt, storage or command flow is changed.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a140
import contextlib as _cx140
import re as _re140
import time as _t140

_QX140_TICK = 10.0


def _qx140_log(message, level="info"):
    with _cx140.suppress(Exception):
        getattr(logger, level)("[S140] %s", message)  # type: ignore[name-defined]


# ═════════════════════════════════════════════════════════════════════════════
# 1) Explanation purifier
# ═════════════════════════════════════════════════════════════════════════════
_QX140_MD = _re140.compile(r"(?<!\\)(?:\*\*+|__|`+)")
_QX140_LABELS = [
    # "উত্তর: (d) 1, (3π/2) ব্যাখ্যা:"  /  "সঠিক উত্তর (c):"
    r"^\s*(?:সঠিক\s*)?(?:উত্তর|উঃ|উত্তরঃ|ans(?:wer)?|correct\s*answer|option)\s*"
    r"[:ঃ\-–—]?\s*\(?\s*[a-dA-Dকখগঘ1-4১-৪]?\s*\)?\s*[^\n]{0,80}?"
    r"(?=\s*(?:ব্যাখ্যা|ব্যখ্যা|explanation|expl)\s*[:ঃ\-–—])",
    # bare leading "(a)" / "(খ)" / "a)" / "d." markers
    r"^\s*\(?\s*[a-dA-Dকখগঘ]\s*\)\s*[:ঃ\-–—]?\s*",
    r"^\s*[a-dA-D]\s*[\.\)]\s+",
    # leading "ব্যাখ্যা:" / "Explanation:" once the header above is gone
    r"^\s*(?:ব্যাখ্যা|ব্যখ্যা|explanation|expl|solution|সমাধান)\s*[:ঃ\-–—]\s*",
    # "সঠিক উত্তর হলো (c)।"
    r"^\s*(?:সঠিক\s*)?উত্তর\s*(?:হলো|হবে|হল|is)\s*\(?\s*[a-dA-Dকখগঘ1-4১-৪]\s*\)?\s*[।.,:\-–—]?\s*",
    r"^\s*option\s*test\s*[:ঃ\-–—]?\s*",
]
_QX140_LABEL_RX = [_re140.compile(p, _re140.IGNORECASE) for p in _QX140_LABELS]
_QX140_INLINE = [
    _re140.compile(r"\s*option\s*test\s*[:ঃ]\s*", _re140.IGNORECASE),
    _re140.compile(
        r"\s*(?:তাই|সুতরাং|অতএব)?\s*(?:সঠিক\s*)?উত্তর\s*[:ঃ]?\s*\(\s*[a-dA-Dকখগঘ]\s*\)\s*[।.]?",
        _re140.IGNORECASE),
]


def _qx140_pure_expl(text):
    """Strip answer-letter headers and display markup; keep the reasoning."""
    out = str(text or "")
    if not out.strip():
        return ""
    out = _QX140_MD.sub("", out)
    for _ in range(4):
        before = out
        for rx in _QX140_LABEL_RX:
            out = rx.sub("", out, count=1).strip()
        if out == before:
            break
    for rx in _QX140_INLINE:
        out = rx.sub(" ", out)
    prev = globals().get("_qx133_clean_expl")
    if callable(prev):
        with _cx140.suppress(Exception):
            out = str(prev(out) or out)
    out = _re140.sub(r"[ \t]{2,}", " ", out).strip(" ,;:।-–—")
    return out.strip()


globals()["_qx140_pure_expl"] = _qx140_pure_expl

_QX140_EXPL_KEYS = ("explanation", "expl", "why", "reason", "solution")


def _qx140_purify_dict(payload):
    if not isinstance(payload, dict):
        return payload
    for key in _QX140_EXPL_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            with _cx140.suppress(Exception):
                payload[key] = _qx140_pure_expl(value)
    return payload


# a) normalised MCQ objects (generation path)
_qx140_prev_norm = globals().get("_normalise_mcq_74")
if callable(_qx140_prev_norm):
    def _normalise_mcq_74(item):  # noqa: F811
        good = _qx140_prev_norm(item)
        return _qx140_purify_dict(good) if isinstance(good, dict) else good

    globals()["_normalise_mcq_74"] = _normalise_mcq_74

# b) stored rows (buffer + verbatim harvest)
_qx140_prev_store = globals().get("_qxz_store_rows")
if callable(_qx140_prev_store):
    def _qxz_store_rows(uid, rows, mode="std"):  # noqa: F811
        cleaned = []
        for row in rows or []:
            cleaned.append(_qx140_purify_dict(dict(row)) if isinstance(row, dict) else row)
        return _qx140_prev_store(uid, cleaned, mode)

    globals()["_qxz_store_rows"] = _qxz_store_rows

# c) poll payloads
_qx140_prev_sanitize = globals().get("_sanitize_item_for_poll")


def _sanitize_item_for_poll(item):  # noqa: F811
    payload = dict(item or {})
    if callable(_qx140_prev_sanitize):
        with _cx140.suppress(Exception):
            payload = dict(_qx140_prev_sanitize(payload) or payload)
    return _qx140_purify_dict(payload)


globals()["_sanitize_item_for_poll"] = _sanitize_item_for_poll

# d) the last gate before Telegram — body purified, owner link untouched
_qx140_prev_trim = globals().get("_trim_expl_for_poll")
if callable(_qx140_prev_trim):
    def _trim_expl_for_poll(expl, link=""):  # noqa: F811
        body = expl
        with _cx140.suppress(Exception):
            body = _qx140_pure_expl(expl)
        return _qx140_prev_trim(body, link)

    globals()["_trim_expl_for_poll"] = _trim_expl_for_poll

_qx140_prev_clean133 = globals().get("_qx133_clean_expl")
if callable(_qx140_prev_clean133):
    def _qx133_clean_expl(text):  # noqa: F811
        out = text
        with _cx140.suppress(Exception):
            out = _QX140_MD.sub("", str(text or ""))
            for rx in _QX140_LABEL_RX:
                out = rx.sub("", out, count=1).strip()
        return _qx140_prev_clean133(out)

    globals()["_qx133_clean_expl"] = _qx133_clean_expl


# ═════════════════════════════════════════════════════════════════════════════
# 2) 10-second live tick on the verbatim (PDF/image) status card
# ═════════════════════════════════════════════════════════════════════════════
_qx140_prev_card = globals().get("_qx138_card")
_QX140_SNAP = {}


if callable(_qx140_prev_card):
    async def _qx138_card(status, found, expected, added, started,
                          title="Converting Questions"):  # noqa: F811
        _QX140_SNAP["args"] = (status, found, expected, added, started, title)
        _QX140_SNAP["at"] = _t140.time()
        return await _qx140_prev_card(status, found, expected, added, started, title)

    globals()["_qx138_card"] = _qx138_card


async def _qx140_ticker():
    while True:
        await _a140.sleep(_QX140_TICK)
        args = _QX140_SNAP.get("args")
        if not args or _t140.time() - float(_QX140_SNAP.get("at") or 0) < _QX140_TICK - 1:
            continue
        renderer = _qx140_prev_card
        if not callable(renderer):
            continue
        with _cx140.suppress(Exception):
            await renderer(*args)
            _QX140_SNAP["at"] = _t140.time()


_qx140_prev_harvest = globals().get("_qxv_harvest")
if callable(_qx140_prev_harvest):
    async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):  # noqa: F811
        _QX140_SNAP.clear()
        ticker = None
        with _cx140.suppress(Exception):
            ticker = _a140.create_task(_qx140_ticker())
        try:
            return await _qx140_prev_harvest(update, context, uid, source_text, status, label)
        finally:
            _QX140_SNAP.clear()
            if ticker is not None and not ticker.done():
                ticker.cancel()
                with _cx140.suppress(Exception):
                    await _a140.gather(ticker, return_exceptions=True)

    globals()["_qxv_harvest"] = _qxv_harvest

_qx140_log("pure explanations (no answer letters/markdown) and 10s verbatim tick active")
