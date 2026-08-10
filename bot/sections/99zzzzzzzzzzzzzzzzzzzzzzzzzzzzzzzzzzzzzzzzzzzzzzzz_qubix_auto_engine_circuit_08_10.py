# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 137 (2026-08-10) — auto-engine circuit breaker + friendly health text
#
# Why "TimeoutError" kept showing and generation crawled:
#   Section 132 gives the default provider chain a 20s deadline on EVERY batch
#   before falling back to Mistral. When the default chain is rate-limited for a
#   whole run, each of the ~5-10 batches burns those 20s first, so a 50-item
#   .gen needs minutes even though Mistral answers in seconds. The panel then
#   showed the raw exception name ("TimeoutError"), which looks like a crash.
#
# Fix:
#   * Consecutive default-chain failures open a circuit breaker: for the next
#     10 minutes auto mode calls Mistral FIRST (no 20s tax), while one cheap
#     probe every ~2 minutes re-tests the default chain and closes the breaker
#     as soon as it works again.
#   * Health notes are rewritten in plain Bangla — no raw TimeoutError text.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx137
import time as _t137


def _log137(message, level="info"):
    with _cx137.suppress(Exception):
        getattr(logger, level)("[S137] %s", message)  # type: ignore[name-defined]


_QX137_OPEN_FAILS = 2        # consecutive default failures that open the breaker
_QX137_COOLDOWN = 600.0      # breaker stays open this long
_QX137_PROBE_EVERY = 120.0   # re-test the default chain this often while open
_QX137_STATE = {"fails": 0, "opened": 0.0, "probed": 0.0}

_qx137_prev_note = globals().get("_qx132_note")
_qx137_default_batch = globals().get("_qx132_prev_batch")
_qx137_mistral_batch = globals().get("_qx132_mistral_batch")
_qx137_pool = globals().get("_QX132_POOL")
_qx137_deadline = float(globals().get("_QX132_DEADLINE") or 20.0)


def _qx137_friendly(text):
    low = str(text or "").lower()
    if not low or low == "ok":
        return "ok"
    if "timeout" in low or "empty in" in low or "deadline" in low:
        return "ধীর সাড়া — Mistral-এ পাঠানো হয়েছে"
    if "429" in low or "rate" in low or "quota" in low or "limit" in low:
        return "সাময়িক লিমিট — Mistral-এ পাঠানো হয়েছে"
    if "no valid mcq" in low or "json" in low:
        return "উত্তর পড়া যায়নি — আবার চেষ্টা হয়েছে"
    if "key" in low:
        return "API key সমস্যা"
    return "সাময়িক সমস্যা — বিকল্প ইঞ্জিন ব্যবহার হয়েছে"


if callable(_qx137_prev_note):

    def _qx132_note(engine, ok, ms, items=0, error=""):  # noqa: F811
        if engine == "default":
            if ok:
                _QX137_STATE["fails"] = 0
                _QX137_STATE["opened"] = 0.0
            else:
                _QX137_STATE["fails"] = int(_QX137_STATE["fails"]) + 1
                if _QX137_STATE["fails"] >= _QX137_OPEN_FAILS and not _QX137_STATE["opened"]:
                    _QX137_STATE["opened"] = _t137.time()
                    _QX137_STATE["probed"] = _t137.time()
                    _log137("default chain unhealthy — Mistral-first for %ds" % int(_QX137_COOLDOWN))
        return _qx137_prev_note(engine, ok, ms, items=items,
                               error=("" if ok else _qx137_friendly(error)))

    globals()["_qx132_note"] = _qx132_note


def _qx137_breaker_open():
    opened = float(_QX137_STATE.get("opened") or 0.0)
    if not opened:
        return False
    if (_t137.time() - opened) > _QX137_COOLDOWN:
        _QX137_STATE.update({"opened": 0.0, "fails": 0})
        return False
    return True


def _qx137_should_probe():
    if (_t137.time() - float(_QX137_STATE.get("probed") or 0.0)) < _QX137_PROBE_EVERY:
        return False
    _QX137_STATE["probed"] = _t137.time()
    return True


if callable(_qx137_default_batch) and callable(_qx137_mistral_batch) and _qx137_pool is not None:

    def _generate_batch_fast_74(source_text, need, *, easy=0, medium=0, hard=0,
                                avoid_text=""):  # noqa: F811
        engine = "auto"
        getter = globals().get("_qx132_engine")
        if callable(getter):
            with _cx137.suppress(Exception):
                engine = str(getter() or "auto")

        def mistral():
            with _cx137.suppress(Exception):
                return list(_qx137_mistral_batch(source_text, need, easy=easy, medium=medium,
                                                 hard=hard, avoid_text=avoid_text) or [])
            return []

        def default(timeout):
            started = _t137.time()
            future = _qx137_pool.submit(_qx137_default_batch, source_text, need,
                                        easy=easy, medium=medium, hard=hard,
                                        avoid_text=avoid_text)
            items, error = [], ""
            try:
                items = list(future.result(timeout=timeout) or [])
            except Exception as exc:
                error = type(exc).__name__ if not str(exc) else str(exc)[:120]
            note = globals().get("_qx132_note")
            if callable(note):
                with _cx137.suppress(Exception):
                    note("default", bool(items), (_t137.time() - started) * 1000,
                         items=len(items), error=error or "empty in %ds" % int(timeout))
            return items

        if engine == "mistral":
            got = mistral()
            return got if got else default(_qx137_deadline * 3)

        if engine == "default":
            return default(_qx137_deadline * 3)

        # Auto mode.
        if _qx137_breaker_open():
            # Skip the 20s tax; Mistral leads while default recovers quietly.
            got = mistral()
            if got:
                if _qx137_should_probe():
                    probe = default(_qx137_deadline)
                    if probe:
                        _log137("default chain healthy again — auto order restored")
                return got
            return default(_qx137_deadline * 2)

        got = default(_qx137_deadline)
        if got:
            return got
        return mistral() or default(_qx137_deadline * 2)

    globals()["_generate_batch_fast_74"] = _generate_batch_fast_74
    _log137("auto-engine circuit breaker active (%d fails -> Mistral-first for %dm)"
            % (_QX137_OPEN_FAILS, int(_QX137_COOLDOWN / 60)))
