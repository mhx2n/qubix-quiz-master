# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 135 (2026-08-10) — parallel AI, single-writer buffer pipeline
#
# Provider telemetry counts valid MCQs returned by the model.  Sections 130/131
# previously let every provider lane also scan/write the same SQLite buffer.
# Under load those writes could fail (and were suppressed by the old writer), so
# /model showed many Mistral quizzes while the final card reported Added: 0.
#
# Keep expensive model calls parallel, but validate/dedupe/write their results on
# the event-loop thread one completed lane at a time.  A write is counted only
# after the buffer row count really increases.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a135
import contextlib as _cx135
import re as _re135
import time as _t135


def _log135(message, level="info"):
    with _cx135.suppress(Exception):
        getattr(logger, level)("[S135] %s", message)  # type: ignore[name-defined]


_QX135_BATCH = 12
_QX135_LANES = 8
_QX135_LANE_TIMEOUT = 65.0
_QX135_BUDGET = 240.0
_QX135_TICK = 10.0


def _qx135_source_text(ocr_ctx):
    if isinstance(ocr_ctx, dict):
        return str(ocr_ctx.get("clean_text") or ocr_ctx.get("raw_markdown") or "").strip()
    return str(ocr_ctx or "").strip()


def _qx135_signature(payload):
    fingerprinter = globals().get("_fp_question")
    if callable(fingerprinter):
        with _cx135.suppress(Exception):
            return str(fingerprinter(payload) or "")
    question = str((payload or {}).get("questions") or (payload or {}).get("question") or "")
    return _re135.sub(r"\W+", "", question.casefold())[:180]


def _qx135_payload(raw, mode):
    if not isinstance(raw, dict):
        return None
    question = str(raw.get("question") or raw.get("questions") or "").strip()
    options = raw.get("options") if isinstance(raw.get("options"), list) else []
    if not options:
        option_reader = globals().get("_opts_59")
        if callable(option_reader):
            with _cx135.suppress(Exception):
                options = list(option_reader(raw) or [])
    options = [str(value or "").strip() for value in options if str(value or "").strip()][:4]
    try:
        answer = int(raw.get("answer") or 0)
    except Exception:
        answer = 0
    if not question or len(options) != 4 or not 1 <= answer <= 4:
        return None
    payload = {
        "questions": question,
        "answer": answer,
        "explanation": str(raw.get("explanation") or "").strip()[:700],
        "type": 1,
        "section": 1,
        "source": "gen_%s" % str(mode or "std"),
    }
    for index in range(5):
        payload["option%d" % (index + 1)] = options[index] if index < 4 else ""
    parity = globals().get("_enforce_option_parity")
    if callable(parity):
        with _cx135.suppress(Exception):
            payload = parity(payload) or payload
    cleaner = globals().get("_qx133_clean_expl")
    if callable(cleaner):
        with _cx135.suppress(Exception):
            payload["explanation"] = cleaner(payload.get("explanation") or "")
    return payload


def _qx135_existing(uid):
    signatures = set()
    ids = set()
    with _cx135.suppress(Exception):
        for row_id, payload in (buffer_list(int(uid), limit=99999) or []):  # type: ignore[name-defined]
            ids.add(int(row_id))
            signature = _qx135_signature(payload)
            if signature:
                signatures.add(signature)
    return signatures, ids


def _qx135_insert(uid, payload):
    """Return True only when buffer_add really persisted one new row."""
    before = int(buffer_count(int(uid)))  # type: ignore[name-defined]
    last_error = ""
    for attempt in range(3):
        try:
            buffer_add(int(uid), payload)  # type: ignore[name-defined]
            after = int(buffer_count(int(uid)))  # type: ignore[name-defined]
            if after > before:
                return True
            last_error = "buffer_add returned without persisting a row"
            break  # validator rejection is terminal; retrying cannot change it
        except Exception as error:
            last_error = str(error)[:180]
            if "lock" not in last_error.lower() and "busy" not in last_error.lower():
                break
            _t135.sleep(0.08 * (attempt + 1))
    _log135("buffer insert rejected/failed for uid=%s: %s" % (uid, last_error), "warning")
    return False


async def _qx135_generate_lane(generator, ocr_ctx, need, uid):
    loop = _a135.get_running_loop()
    return await _a135.wait_for(
        loop.run_in_executor(None, generator, ocr_ctx, need, uid),
        timeout=_QX135_LANE_TIMEOUT,
    )


_qx135_generator = globals().get("_generate_quizzes_from_ocr_sync")

if callable(_qx135_generator):

    async def _generate_to_buffer_59(update, context, ocr_ctx, uid, count,
                                     mode="std"):  # noqa: F811
        try:
            wanted = max(1, min(500, int(count or 20)))
        except Exception:
            wanted = 20
        source_text = _qx135_source_text(ocr_ctx)
        if not source_text:
            return 0, 0

        started = _t135.time()
        state = {"added": 0, "dup": 0, "done": False, "failed": 0}
        progress = globals().get("_qx129_progress")
        reject = globals().get("_qx129_remove_off_subject_calculus")
        signatures, before_ids = _qx135_existing(uid)

        async def paint():
            if callable(progress):
                with _cx135.suppress(Exception):
                    await progress(context, update, uid, min(state["added"], wanted),
                                   wanted, mode, started)

        async def ticker():
            while not state["done"]:
                await _a135.sleep(_QX135_TICK)
                if not state["done"]:
                    await paint()

        def accept(rows):
            for raw in rows or []:
                if state["added"] >= wanted:
                    break
                payload = _qx135_payload(raw, mode)
                if not payload:
                    continue
                signature = _qx135_signature(payload)
                if not signature or signature in signatures:
                    state["dup"] += 1
                    continue
                if int(buffer_count(int(uid))) >= int(MAX_BUFFERED_QUESTIONS):  # type: ignore[name-defined]
                    break
                if not explain_mode_on(int(uid)):  # type: ignore[name-defined]
                    payload["explanation"] = ""
                if _qx135_insert(uid, payload):
                    signatures.add(signature)
                    state["added"] += 1
                else:
                    state["failed"] += 1

        await paint()
        ticker_task = _a135.create_task(ticker())
        globals()["_active_gen_mode_57"] = mode or "std"
        pending = set()
        stalled = 0
        try:
            while state["added"] < wanted and (_t135.time() - started) < _QX135_BUDGET:
                remaining = wanted - state["added"]
                while len(pending) < _QX135_LANES and remaining > 0:
                    need = min(_QX135_BATCH, remaining)
                    pending.add(_a135.create_task(
                        _qx135_generate_lane(_qx135_generator, ocr_ctx, need, int(uid))))
                    remaining -= need
                if not pending:
                    break
                done, pending = await _a135.wait(pending, return_when=_a135.FIRST_COMPLETED)
                landed = 0
                for task in done:
                    try:
                        rows = task.result() or []
                    except Exception as error:
                        state["failed"] += 1
                        _log135("provider lane failed: %s" % str(error)[:160], "warning")
                        rows = []
                    before_added = state["added"]
                    accept(rows)
                    landed += state["added"] - before_added
                await paint()
                if landed <= 0:
                    stalled += 1
                    if stalled >= _QX135_LANES:
                        break
                else:
                    stalled = 0
        finally:
            for task in pending:
                task.cancel()
            if pending:
                with _cx135.suppress(_a135.CancelledError, Exception):
                    await _a135.gather(*pending, return_exceptions=True)
            globals()["_active_gen_mode_57"] = None
            state["done"] = True
            ticker_task.cancel()
            with _cx135.suppress(_a135.CancelledError, Exception):
                await ticker_task

        # One final subject guard, after all writes; never scan once per lane.
        if callable(reject):
            with _cx135.suppress(Exception):
                dropped = int(reject(uid, before_ids, source_text) or 0)
                state["added"] = max(0, state["added"] - dropped)

        _log135("atomic gen done: %s/%s in %.1fs (dup=%s, rejected=%s)" % (
            state["added"], wanted, _t135.time() - started,
            state["dup"], state["failed"],
        ))
        return int(state["added"]), int(state["dup"])

    globals()["_generate_to_buffer_59"] = _generate_to_buffer_59
    _log135("single-writer buffer pipeline active (%s parallel AI lanes)" % _QX135_LANES)
