# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 144 (2026-08-12) — turbo + complete verbatim harvest
#
# Problems this fixes (nothing else in the bot changes):
#   1) 70 detected → only 47 delivered.  Chunks were page-sized, so one weak
#      provider reply silently dropped a whole block of questions and the OCR
#      text itself was capped at 12 chunks.
#   2) 5+ minutes per run.  Only 4 lanes of very large requests, so the slowest
#      request decided the total time.
#   3) The 10-second live card stopped working: section 142 replaced
#      `_qxv_harvest` after the ticker wrapper had been installed, so the wrapper
#      was gone.
#
# Approach: split the source into individual printed questions, send small
# question groups over many lanes, reconcile every missing printed serial with a
# focused single-question retry, flush strictly in printed order, and always run
# our own 10s ticker inside the harvest itself.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a144
import contextlib as _cx144
import re as _re144
import time as _t144


_QX144_GROUP = 4           # printed questions per provider request
_QX144_MAX_CHARS = 2600    # …but never send a huge blob
_QX144_LANES = 12          # concurrent provider requests
_QX144_TICK = 10.0         # live card refresh
_QX144_TIMEOUT = 55
_QX144_RETRY_TIMEOUT = 40
_QX144_SINGLE_TIMEOUT = 30
_QX144_BN = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_QX144_SERIAL = _re144.compile(
    r"^\s*(?:\*\*|__)?\s*[\(\[\{]?\s*([0-9০-৯]{1,4})\s*(?:[।|)\]\}:.\-–—])"
)


def _qx144_log(message, level="info"):
    with _cx144.suppress(Exception):
        getattr(logger, level)("[S144] %s", message)  # type: ignore[name-defined]


# The OCR text itself must not be truncated any more.
with _cx144.suppress(Exception):
    if int(globals().get("QXV_MAX_CHUNKS") or 0) < 80:
        globals()["QXV_MAX_CHUNKS"] = 80


def _qx144_serial_of_text(text):
    match = _QX144_SERIAL.match(str(text or "").strip())
    if not match:
        return None
    with _cx144.suppress(Exception):
        return int(match.group(1).translate(_QX144_BN))
    return None


def _qx144_serial_of_row(row):
    return _qx144_serial_of_text(
        str((row or {}).get("question") or (row or {}).get("questions") or "")
    )


def _qx144_groups(blocks):
    """Group consecutive printed questions into small, order-preserving batches."""
    groups, current, size = [], [], 0
    for block in blocks:
        text = str(block or "").strip()
        if not text:
            continue
        if current and (len(current) >= _QX144_GROUP or size + len(text) > _QX144_MAX_CHARS):
            groups.append(current)
            current, size = [], 0
        current.append(text)
        size += len(text)
    if current:
        groups.append(current)
    return groups


def _qx144_order(rows):
    orderer = globals().get("_qx142_order_rows")
    if callable(orderer):
        with _cx144.suppress(Exception):
            return list(orderer(rows) or [])
    return list(rows or [])


def _qx144_extract_sync(text, lang):
    extractor = globals().get("_qxv_extract_sync")
    return list(extractor(text, lang) or []) if callable(extractor) else []


def _qx144_local(text):
    local = globals().get("_qx139_local_rows")
    return list(local(text) or []) if callable(local) else []


async def _qx144_blocking(uid, fn, *args, timeout):
    runner = globals().get("_run_blocking")
    role_of = globals().get("_role_of")
    if not callable(runner):
        return []
    role = "USER"
    if callable(role_of):
        with _cx144.suppress(Exception):
            role = role_of(int(uid))
    return await runner(role, fn, *args, timeout=timeout)


def _qx144_signature(row):
    signer = globals().get("_qx139_signature")
    if callable(signer):
        with _cx144.suppress(Exception):
            return signer(row)
    question = str((row or {}).get("question") or (row or {}).get("questions") or "")
    return _re144.sub(r"\W+", "", question.casefold())[:140]


def _qx144_clean(row):
    cleaner = globals().get("_qx139_clean_row")
    if callable(cleaner):
        with _cx144.suppress(Exception):
            return cleaner(row)
    return row


async def _qx144_group_rows(uid, group, lang, semaphore):
    """Return rows for one small group, reconciling every missing serial."""
    async with semaphore:
        text = "\n\n".join(group)
        merged, seen = [], set()

        def absorb(rows):
            for source_row in rows or []:
                row = _qx144_clean(source_row)
                signature = _qx144_signature(row)
                if row and signature and signature not in seen:
                    seen.add(signature)
                    merged.append(row)

        with _cx144.suppress(Exception):
            absorb(await _qx144_blocking(uid, _qx144_local, text, timeout=15) or [])

        if len(merged) < len(group):
            with _cx144.suppress(Exception):
                absorb(await _qx144_blocking(
                    uid, _qx144_extract_sync, text, lang, timeout=_QX144_TIMEOUT) or [])

        if len(merged) < len(group):
            with _cx144.suppress(Exception):
                absorb(await _qx144_blocking(
                    uid, _qx144_extract_sync, text, lang,
                    timeout=_QX144_RETRY_TIMEOUT) or [])

        # Still short → ask for the exact printed serials that are missing.
        if len(merged) < len(group):
            have = {_qx144_serial_of_row(row) for row in merged}
            have.discard(None)
            for block in group:
                serial = _qx144_serial_of_text(block)
                if serial is not None and serial in have:
                    continue
                with _cx144.suppress(Exception):
                    absorb(await _qx144_blocking(
                        uid, _qx144_extract_sync, block, lang,
                        timeout=_QX144_SINGLE_TIMEOUT) or [])
                if len(merged) >= len(group):
                    break
        return merged


_qx144_prev_harvest = globals().get("_qxv_harvest")


async def _qx144_turbo_harvest(update, context, uid, source_text, status, label, state):
    splitter = globals().get("_qxm_split_questions")
    storer = globals().get("_qxz_store_rows")
    card = globals().get("_qx138_card")
    if not (callable(splitter) and callable(storer)):
        return None

    blocks = []
    with _cx144.suppress(Exception):
        blocks = list(splitter(source_text) or [])
    if len(blocks) < 2:
        return None

    groups = _qx144_groups(blocks)
    if not groups:
        return None

    lang = "bn"
    probe = globals().get("_generation_lang_88")
    if callable(probe):
        with _cx144.suppress(Exception):
            lang = str(probe(source_text) or "bn")

    expected = sum(len(group) for group in groups)
    state.update({"expected": expected, "found": 0, "added": 0})
    semaphore = _a144.Semaphore(max(1, min(_QX144_LANES, len(groups))))
    started = state["started"]

    async def indexed(position, group):
        rows = []
        with _cx144.suppress(Exception):
            rows = await _qx144_group_rows(uid, group, lang, semaphore)
        return position, rows

    tasks = [
        _a144.create_task(indexed(position, group))
        for position, group in enumerate(groups)
    ]

    results, cursor = {}, 0
    dup = 0
    global_seen = set()
    if callable(card):
        with _cx144.suppress(Exception):
            await card(status, 0, expected, 0, started)

    async def flush_ready():
        nonlocal cursor, dup
        while cursor in results:
            rows = results.pop(cursor)
            cursor += 1
            fresh = []
            for row in _qx144_order(rows):
                signature = _qx144_signature(row)
                if signature and signature not in global_seen:
                    global_seen.add(signature)
                    fresh.append(row)
            if not fresh:
                continue
            state["found"] = int(state["found"]) + len(fresh)
            with _cx144.suppress(Exception):
                chunk_added, chunk_dup = storer(int(uid), fresh, "src")
                state["added"] = int(state["added"]) + int(chunk_added or 0)
                dup += int(chunk_dup or 0)
            if callable(card):
                with _cx144.suppress(Exception):
                    await card(status, state["found"],
                               state["expected"] or state["found"],
                               state["added"], started)

    try:
        for future in _a144.as_completed(tasks):
            position, rows = None, []
            with _cx144.suppress(Exception):
                position, rows = await future
            if position is None:
                continue
            results[int(position)] = rows
            await flush_ready()
        await flush_ready()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            with _cx144.suppress(Exception):
                await _a144.gather(*tasks, return_exceptions=True)

    _qx144_log(
        "turbo verbatim: expected=%s found=%s added=%s dup=%s groups=%s lanes=%s seconds=%.1f"
        % (expected, state["found"], state["added"], dup, len(groups),
           _QX144_LANES, _t144.time() - started)
    )
    return int(state["added"]), int(dup), int(state["found"])


async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):  # noqa: F811
    state = {"expected": 0, "found": 0, "added": 0, "started": _t144.time(), "done": False}
    card = globals().get("_qx138_card")

    async def ticker():
        while not state["done"]:
            await _a144.sleep(_QX144_TICK)
            if state["done"] or not callable(card):
                continue
            with _cx144.suppress(Exception):
                await card(status, int(state["found"]),
                           int(state["expected"]) or int(state["found"]),
                           int(state["added"]), state["started"])

    tick_task = None
    with _cx144.suppress(Exception):
        tick_task = _a144.create_task(ticker())
    try:
        outcome = await _qx144_turbo_harvest(
            update, context, uid, source_text, status, label, state)
        if outcome is not None:
            return outcome
        if callable(_qx144_prev_harvest):
            return await _qx144_prev_harvest(update, context, uid, source_text, status, label)
        return 0, 0, 0
    finally:
        state["done"] = True
        if tick_task is not None and not tick_task.done():
            tick_task.cancel()
            with _cx144.suppress(Exception):
                await _a144.gather(tick_task, return_exceptions=True)


globals()["_qxv_harvest"] = _qxv_harvest
_qx144_log("turbo full harvest active: %s lanes x %s questions, 10s live card"
           % (_QX144_LANES, _QX144_GROUP))
