# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 131 (2026-08-10) — generation throughput restore
#
# Why it got slow after section 130:
#   * only 4 concurrent provider lanes of 10 items  → a 100-item request needed
#     3 sequential rounds of the slowest lane;
#   * every lane ran TWO full buffer_list(limit=99999) scans (before-ids and the
#     off-subject reject pass) on the same SQLite file, so lanes queued behind
#     each other instead of running truly in parallel;
#   * a lane failure only surfaced after 110s, so one bad round burned ~2 min.
#
# Fix: wider lanes, bigger batches, ONE reject pass at the very end, shorter
# per-lane timeout, and continuous lane refill instead of round barriers.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a131
import contextlib as _cx131
import time as _t131


def _log131(message, level="info"):
    with _cx131.suppress(Exception):
        getattr(logger, level)("[S131] %s", message)  # type: ignore[name-defined]


_QX131_BATCH = 12         # items per provider request
_QX131_LANES = 8          # concurrent provider requests
_QX131_TICK = 10.0        # seconds between visible card updates
_QX131_LANE_TIMEOUT = 70.0
_QX131_BUDGET = 420.0

_qx131_batch_generate = globals().get("_qx129_batch_generate")
if not callable(_qx131_batch_generate):
    _qx131_batch_generate = globals().get("_qx124_prev_gen_buffer")
if not callable(_qx131_batch_generate):
    _qx131_batch_generate = globals().get("_generate_to_buffer_59")


if callable(_qx131_batch_generate):

    async def _generate_to_buffer_59(update, context, ocr_ctx, uid, count,
                                     mode="std"):  # noqa: F811
        try:
            wanted = max(1, min(500, int(count or 20)))
        except Exception:
            wanted = 20

        started = _t131.time()
        state = {"added": 0, "dup": 0, "done": False, "fail": 0}
        progress = globals().get("_qx129_progress")
        reject = globals().get("_qx129_remove_off_subject_calculus")
        buffer_ids = globals().get("_qx129_buffer_ids")

        if isinstance(ocr_ctx, dict):
            source_text = str(ocr_ctx.get("clean_text")
                              or ocr_ctx.get("raw_markdown") or "")
        else:
            source_text = str(ocr_ctx or "")

        # One snapshot only — taken before any lane starts, reused at the end.
        before = set()
        if callable(buffer_ids):
            with _cx131.suppress(Exception):
                before = buffer_ids(uid)

        async def paint():
            if callable(progress):
                with _cx131.suppress(Exception):
                    await progress(context, update, uid,
                                   min(int(state["added"]), wanted), wanted,
                                   mode, started)

        async def ticker():
            while not state["done"]:
                await _a131.sleep(_QX131_TICK)
                if state["done"]:
                    break
                await paint()

        async def lane(need):
            try:
                added, dup = await _a131.wait_for(
                    _qx131_batch_generate(update, context, ocr_ctx, uid, need, mode),
                    timeout=_QX131_LANE_TIMEOUT,
                )
            except Exception as error:
                state["fail"] += 1
                _log131("lane failed: %s" % str(error)[:140], "warning")
                return 0
            added = max(0, int(added or 0))
            state["added"] += added
            state["dup"] += max(0, int(dup or 0))
            return added

        await paint()
        tick_task = _a131.ensure_future(ticker())
        running = set()
        try:
            stalled = 0
            while True:
                if state["added"] >= wanted:
                    break
                if (_t131.time() - started) >= _QX131_BUDGET:
                    break

                # Continuous refill: start new lanes as soon as slots free up.
                pending_target = wanted - state["added"]
                while (len(running) < _QX131_LANES
                       and len(running) * _QX131_BATCH < pending_target + _QX131_BATCH
                       and state["added"] < wanted):
                    take = min(_QX131_BATCH, max(1, pending_target))
                    running.add(_a131.ensure_future(lane(take)))
                    pending_target -= take
                    if pending_target <= 0:
                        break

                if not running:
                    break
                done, running = await _a131.wait(
                    running, return_when=_a131.FIRST_COMPLETED)
                round_added = 0
                for task in done:
                    with _cx131.suppress(Exception):
                        round_added += int(task.result() or 0)
                await paint()
                if round_added <= 0:
                    stalled += 1
                    if stalled >= max(3, _QX131_LANES // 2):
                        break
                else:
                    stalled = 0
        finally:
            for task in running:
                task.cancel()
            if running:
                with _cx131.suppress(_a131.CancelledError, Exception):
                    await _a131.gather(*running, return_exceptions=True)
            state["done"] = True
            tick_task.cancel()
            with _cx131.suppress(_a131.CancelledError, Exception):
                await tick_task

        # Single off-subject sweep at the end instead of once per lane.
        if callable(reject):
            with _cx131.suppress(Exception):
                dropped = int(reject(uid, before, source_text) or 0)
                if dropped:
                    state["added"] = max(0, int(state["added"]) - dropped)

        _log131("gen done: %s/%s in %.1fs (dup=%s, lane_fail=%s)"
                % (state["added"], wanted, _t131.time() - started,
                   state["dup"], state["fail"]))
        return int(state["added"]), int(state["dup"])

    globals()["_generate_to_buffer_59"] = _generate_to_buffer_59
    _log131("throughput restore active: %s lanes x %s items, %ss lane timeout"
            % (_QX131_LANES, _QX131_BATCH, int(_QX131_LANE_TIMEOUT)))
