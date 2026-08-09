# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 130 (2026-08-09) — parallel batch generation + 10s live progress ticker
#
# Why: section 129 ran bounded batches strictly one-after-another, so a 50–100
# item request became 7–13 sequential provider round-trips (5+ minutes) and the
# visible counter only moved when a whole batch finished. Here the same proven
# batch generator runs several batches concurrently and a background ticker
# refreshes the existing status card every 10 seconds.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a130
import contextlib as _cx130
import time as _t130


def _log130(message, level="info"):
    with _cx130.suppress(Exception):
        getattr(logger, level)("[S130] %s", message)  # type: ignore[name-defined]


_QX130_BATCH = 10          # items per provider request
_QX130_PARALLEL = 4        # concurrent provider requests
_QX130_TICK = 10.0         # seconds between visible card updates
_QX130_BUDGET = 420.0      # hard wall-clock ceiling for one .gen request

_qx130_batch_generate = globals().get("_qx129_batch_generate")
if not callable(_qx130_batch_generate):
    _qx130_batch_generate = globals().get("_qx124_prev_gen_buffer")
if not callable(_qx130_batch_generate):
    _qx130_batch_generate = globals().get("_generate_to_buffer_59")


if callable(_qx130_batch_generate):

    async def _generate_to_buffer_59(update, context, ocr_ctx, uid, count,
                                     mode="std"):  # noqa: F811
        try:
            wanted = max(1, min(500, int(count or 20)))
        except Exception:
            wanted = 20

        started = _t130.time()
        state = {"added": 0, "dup": 0, "done": False}
        progress = globals().get("_qx129_progress")
        reject = globals().get("_qx129_remove_off_subject_calculus")
        buffer_ids = globals().get("_qx129_buffer_ids")
        source_text = ""
        if isinstance(ocr_ctx, dict):
            source_text = str(
                ocr_ctx.get("clean_text") or ocr_ctx.get("raw_markdown") or ""
            )
        else:
            source_text = str(ocr_ctx or "")

        async def paint():
            if callable(progress):
                with _cx130.suppress(Exception):
                    await progress(
                        context, update, uid,
                        min(int(state["added"]), wanted), wanted, mode, started,
                    )

        async def ticker():
            # Fixed 10-second cadence, independent of provider round-trip time.
            while not state["done"]:
                await _a130.sleep(_QX130_TICK)
                if state["done"]:
                    break
                await paint()

        async def one_batch(need):
            before = set()
            if callable(buffer_ids):
                with _cx130.suppress(Exception):
                    before = buffer_ids(uid)
            try:
                added, dup = await _a130.wait_for(
                    _qx130_batch_generate(update, context, ocr_ctx, uid, need, mode),
                    timeout=110.0,
                )
            except Exception as error:
                _log130("batch failed: %s" % str(error)[:160], "warning")
                return 0, 0
            rejected = 0
            if callable(reject):
                with _cx130.suppress(Exception):
                    rejected = int(reject(uid, before, source_text) or 0)
            added = max(0, int(added or 0) - rejected)
            state["added"] += added
            state["dup"] += int(dup or 0)
            return added, int(dup or 0)

        await paint()
        tick_task = _a130.ensure_future(ticker())
        try:
            stalled = 0
            while state["added"] < wanted and (_t130.time() - started) < _QX130_BUDGET:
                remaining = wanted - state["added"]
                lanes = max(1, min(_QX130_PARALLEL,
                                   (remaining + _QX130_BATCH - 1) // _QX130_BATCH))
                needs = []
                left = remaining
                for _ in range(lanes):
                    take = min(_QX130_BATCH, left)
                    if take <= 0:
                        break
                    needs.append(take)
                    left -= take
                results = await _a130.gather(
                    *[one_batch(need) for need in needs], return_exceptions=True
                )
                round_added = 0
                for result in results:
                    if isinstance(result, tuple):
                        round_added += int(result[0] or 0)
                await paint()
                if round_added <= 0:
                    stalled += 1
                    if stalled >= 2:
                        break
                else:
                    stalled = 0
        finally:
            state["done"] = True
            tick_task.cancel()
            # asyncio.CancelledError is a BaseException on current Python, so
            # suppress(Exception) does not consume it.  Letting it escape here
            # prevented the caller from replacing the 100% progress card with
            # the normal final Quiz Ready result.
            with _cx130.suppress(_a130.CancelledError, Exception):
                await tick_task

        return int(state["added"]), int(state["dup"])

    globals()["_generate_to_buffer_59"] = _generate_to_buffer_59
    _log130("parallel batch generation (%s x %s) with %ss progress ticker active"
            % (_QX130_PARALLEL, _QX130_BATCH, int(_QX130_TICK)))
