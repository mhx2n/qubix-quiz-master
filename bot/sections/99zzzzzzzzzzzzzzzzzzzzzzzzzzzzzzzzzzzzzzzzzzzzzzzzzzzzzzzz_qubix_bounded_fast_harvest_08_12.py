# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 145 (2026-08-12) — bounded fast harvest for large PDF/image ranges
#
# Section 144 exposed 12 async lanes, but every provider call still entered the
# role pool (OWNER=2 threads) and `_qxv_extract_sync` recursively performed its
# own batch + per-question retries.  A 242-question source therefore behaved
# like two serial workers making hundreds of requests.  This overlay changes
# only verbatim source harvesting: one direct request per six-question group,
# one grouped retry only when short, and a dedicated bounded worker pool.
# Buffer, ordering, tenant, explanation-link, posting and command flows remain.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a145
import contextlib as _cx145
from concurrent.futures import ThreadPoolExecutor as _Pool145
import re as _re145
import time as _t145


_QX145_GROUP = 8
_QX145_MAX_CHARS = 4200
_QX145_LANES = 12
_QX145_TIMEOUT = 35
_QX145_RETRY_TIMEOUT = 27
_QX145_TOTAL_BUDGET = 125.0
_QX145_POOL = _Pool145(max_workers=_QX145_LANES, thread_name_prefix="harvest")


def _qx145_log(message, level="info"):
    with _cx145.suppress(Exception):
        getattr(logger, level)("[S145] %s", message)  # type: ignore[name-defined]


def _qx145_groups(blocks):
    groups, current, size = [], [], 0
    for source in blocks or []:
        block = str(source or "").strip()
        if not block:
            continue
        if current and (len(current) >= _QX145_GROUP
                        or size + len(block) > _QX145_MAX_CHARS):
            groups.append(current)
            current, size = [], 0
        current.append(block)
        size += len(block)
    if current:
        groups.append(current)
    return groups


def _qx145_signature(row):
    signer = globals().get("_qx139_signature")
    if callable(signer):
        with _cx145.suppress(Exception):
            return signer(row)
    question = str((row or {}).get("question") or (row or {}).get("questions") or "")
    return _re145.sub(r"\W+", "", question.casefold())[:140]


def _qx145_finish_row(row):
    if not isinstance(row, dict):
        return None
    item = dict(row)
    cleaner = globals().get("_qx139_clean_row")
    if callable(cleaner):
        with _cx145.suppress(Exception):
            item = cleaner(item)
    closer = globals().get("_qx143_complete")
    explanation = str((item or {}).get("explanation") or "").strip()
    if callable(closer) and explanation:
        with _cx145.suppress(Exception):
            item["explanation"] = closer(explanation)
    return item


def _qx145_direct_extract(source_text, lang, timeout):
    """One provider request; deliberately bypass nested exhaustive harvests."""
    prompt_of = globals().get("_qxv_prompt")
    ai_raw = globals().get("_qxv_ai_raw")
    item_parser = globals().get("_qxv_items")
    row_builder = globals().get("_qxv_row")
    if not all(callable(fn) for fn in (prompt_of, ai_raw, item_parser, row_builder)):
        return []
    raw = ai_raw(prompt_of(source_text, lang), timeout=timeout)
    rows = []
    for payload in item_parser(raw) or []:
        with _cx145.suppress(Exception):
            row = _qx145_finish_row(row_builder(payload))
            if row:
                rows.append(row)
    return rows


async def _qx145_provider(source_text, lang, timeout):
    loop = _a145.get_running_loop()
    future = loop.run_in_executor(
        _QX145_POOL, _qx145_direct_extract, source_text, lang, timeout,
    )
    return await _a145.wait_for(future, timeout=float(timeout) + 3.0)


async def _qx145_group_rows(group, lang, semaphore):
    async with semaphore:
        merged, seen = [], set()

        def absorb(rows):
            for source_row in rows or []:
                row = _qx145_finish_row(source_row)
                signature = _qx145_signature(row)
                if row and signature and signature not in seen:
                    seen.add(signature)
                    merged.append(row)

        text = "\n\n".join(group)
        with _cx145.suppress(Exception):
            absorb(await _qx145_provider(text, lang, _QX145_TIMEOUT))

        # Exactly one compact retry.  Older extractors retried the group and then
        # every question individually, multiplying calls and causing 6–7 min runs.
        if len(merged) < len(group):
            retry_text = (
                "নিচের source-এ %dটি MCQ আছে। আগের উত্তরে বাদ পড়া প্রশ্নসহ "
                "প্রতিটি প্রশ্ন একবার করে, মোট %dটি quiz row দিন।\n\n%s"
                % (len(group), len(group), text)
            )
            with _cx145.suppress(Exception):
                absorb(await _qx145_provider(retry_text, lang, _QX145_RETRY_TIMEOUT))
        return merged


async def _qx145_fast_harvest(update, context, uid, source_text, status, label, state):
    splitter = globals().get("_qxm_split_questions")
    storer = globals().get("_qxz_store_rows")
    orderer = globals().get("_qx142_order_rows")
    card = globals().get("_qx138_card")
    if not (callable(splitter) and callable(storer)):
        return None

    blocks = []
    with _cx145.suppress(Exception):
        blocks = list(splitter(source_text) or [])
    if len(blocks) < 2:
        return None
    groups = _qx145_groups(blocks)
    if not groups:
        return None

    lang = "bn"
    probe = globals().get("_generation_lang_88")
    if callable(probe):
        with _cx145.suppress(Exception):
            lang = str(probe(source_text) or "bn")

    expected = len(blocks)
    state.update({"expected": expected, "found": 0, "added": 0})
    semaphore = _a145.Semaphore(min(_QX145_LANES, len(groups)))
    started = state["started"]

    async def indexed(position, group):
        rows = []
        with _cx145.suppress(Exception):
            rows = await _qx145_group_rows(group, lang, semaphore)
        return position, rows

    tasks = {
        _a145.create_task(indexed(position, group))
        for position, group in enumerate(groups)
    }
    results, cursor, dup = {}, 0, 0
    global_seen, completed_seen = set(), set()

    if callable(card):
        with _cx145.suppress(Exception):
            await card(status, 0, expected, 0, started)

    async def flush_ready():
        nonlocal cursor, dup
        while cursor in results:
            rows = results.pop(cursor)
            cursor += 1
            ordered = list(orderer(rows) or []) if callable(orderer) else list(rows or [])
            fresh = []
            for row in ordered:
                signature = _qx145_signature(row)
                if signature and signature not in global_seen:
                    global_seen.add(signature)
                    fresh.append(row)
            if fresh:
                with _cx145.suppress(Exception):
                    chunk_added, chunk_dup = storer(int(uid), fresh, "src")
                    state["added"] = int(state["added"]) + int(chunk_added or 0)
                    dup += int(chunk_dup or 0)

    deadline = started + _QX145_TOTAL_BUDGET
    try:
        while tasks:
            remaining = deadline - _t145.time()
            if remaining <= 0:
                break
            done, tasks = await _a145.wait(
                tasks, timeout=remaining, return_when=_a145.FIRST_COMPLETED,
            )
            if not done:
                break
            for task in done:
                position, rows = await task
                results[int(position)] = rows
                for row in rows or []:
                    signature = _qx145_signature(row)
                    if signature:
                        completed_seen.add(signature)
            state["found"] = min(expected, len(completed_seen))
            await flush_ready()
            if callable(card):
                with _cx145.suppress(Exception):
                    await card(status, state["found"], expected,
                               state["added"], started)
        await flush_ready()
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            with _cx145.suppress(Exception):
                await _a145.gather(*tasks, return_exceptions=True)

    found = len(global_seen)
    state["found"] = found
    _qx145_log(
        "bounded harvest: expected=%s found=%s added=%s dup=%s groups=%s "
        "lanes=%s seconds=%.1f"
        % (expected, found, state["added"], dup, len(groups),
           _QX145_LANES, _t145.time() - started)
    )
    return int(state["added"]), int(dup), int(found)


_qx145_prev_harvest = globals().get("_qxv_harvest")


async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):  # noqa: F811
    state = {"expected": 0, "found": 0, "added": 0,
             "started": _t145.time(), "done": False}
    card = globals().get("_qx138_card")

    async def ticker():
        while not state["done"]:
            await _a145.sleep(10.0)
            if state["done"] or not callable(card):
                continue
            with _cx145.suppress(Exception):
                await card(status, int(state["found"]),
                           int(state["expected"]) or int(state["found"]),
                           int(state["added"]), state["started"])

    tick_task = _a145.create_task(ticker())
    try:
        outcome = await _qx145_fast_harvest(
            update, context, uid, source_text, status, label, state,
        )
        if outcome is not None:
            return outcome
        if callable(_qx145_prev_harvest):
            return await _qx145_prev_harvest(
                update, context, uid, source_text, status, label,
            )
        return 0, 0, 0
    finally:
        state["done"] = True
        tick_task.cancel()
        with _cx145.suppress(_a145.CancelledError, Exception):
            await tick_task


globals()["_qxv_harvest"] = _qxv_harvest
_qx145_log("bounded fast harvest active: 12 lanes x 8 questions, one grouped retry")