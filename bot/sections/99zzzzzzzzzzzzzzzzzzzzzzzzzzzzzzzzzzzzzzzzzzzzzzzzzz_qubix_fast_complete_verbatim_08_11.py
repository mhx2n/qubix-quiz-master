# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 139 (2026-08-11) — fast, complete verbatim conversion + clean options
#
# The previous live-progress patch processed OCR chunks serially.  A 5-page
# range commonly contains 8–12 chunks, so even healthy 25–40 second provider
# calls accumulated into a 5–6 minute wait.  This overlay keeps every existing
# command/provider/storage flow, but runs a small bounded set concurrently.
#
# It also accepts deterministic OCR parses before asking AI, retries only a
# deficient chunk once, and strips presentation-only markdown/teacher credits
# from options.  Question credits such as [আলীম স্যার] remain untouched.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a139
import contextlib as _cx139
import re as _re139
import time as _t139


_QX139_WORKERS = 4
_QX139_CHUNK_TIMEOUT = 95
_QX139_RETRY_TIMEOUT = 75
_QX139_CREDIT = _re139.compile(
    r"\s*[\[【]\s*[^\]】\n]{0,60}?(?:স্যার|sir|teacher)\s*[\]】]\s*",
    _re139.IGNORECASE,
)
_QX139_EMPTY_WRAP = _re139.compile(r"\s*(?:\[\s*\]|【\s*】)\s*")
_QX139_MD = _re139.compile(r"(?<!\\)(?:\*\*|__|`+)")
_QX139_STAR_NOISE = _re139.compile(r"\*\s+\*(?:\s+\*)*")


def _qx139_log(message, level="info"):
    with _cx139.suppress(Exception):
        getattr(logger, level)("[S139] %s", message)  # type: ignore[name-defined]


def _qx139_clean_option(value):
    """Remove display markup and misplaced source credits, not math brackets."""
    text = str(value or "").strip()
    if not text:
        return text
    text = _QX139_MD.sub("", text)
    text = _QX139_STAR_NOISE.sub(" ", text)
    text = _QX139_EMPTY_WRAP.sub(" ", text)
    text = _QX139_CREDIT.sub(" ", text)
    text = _re139.sub(r"[ \t]+", " ", text).strip()
    return text


def _qx139_clean_row(row):
    if not isinstance(row, dict):
        return None
    clean = dict(row)
    options = clean.get("options")
    if isinstance(options, (list, tuple)):
        clean["options"] = [_qx139_clean_option(option) for option in options]
    for index in range(1, 6):
        key = "option%d" % index
        if key in clean:
            clean[key] = _qx139_clean_option(clean.get(key))
    return clean


_qx139_prev_sanitize = globals().get("_sanitize_item_for_poll")


def _sanitize_item_for_poll(item):  # noqa: F811
    payload = dict(item or {})
    if callable(_qx139_prev_sanitize):
        with _cx139.suppress(Exception):
            payload = dict(_qx139_prev_sanitize(payload) or payload)
    for index in range(1, 6):
        key = "option%d" % index
        if key in payload:
            payload[key] = _qx139_clean_option(payload.get(key))
    return payload


globals()["_sanitize_item_for_poll"] = _sanitize_item_for_poll


_qx139_prev_store = globals().get("_qxz_store_rows")
if callable(_qx139_prev_store):
    def _qxz_store_rows(uid, rows, mode="std"):  # noqa: F811
        cleaned = []
        for row in rows or []:
            item = _qx139_clean_row(row)
            if item is not None:
                cleaned.append(item)
        return _qx139_prev_store(uid, cleaned, mode)

    globals()["_qxz_store_rows"] = _qxz_store_rows


def _qx139_signature(row):
    question = str((row or {}).get("question") or (row or {}).get("questions") or "")
    return _re139.sub(r"\W+", "", question.casefold())[:140]


def _qx139_local_rows(chunk):
    """Use the already available deterministic OCR parser at zero API cost."""
    parser = globals().get("_extract_mcq_items_master")
    row_builder = globals().get("_qxv_row")
    if not (callable(parser) and callable(row_builder)):
        return []
    rows = []
    with _cx139.suppress(Exception):
        for item in parser(chunk) or []:
            options = [
                str(item.get("option%d" % index) or "").strip()
                for index in range(1, 5)
            ]
            answer = int(item.get("answer") or 0)
            # Do not guess an answer locally.  Unmarked items go through AI.
            if len([option for option in options if option]) != 4 or not (1 <= answer <= 4):
                continue
            candidate = {
                "question": item.get("questions") or item.get("question"),
                "options": options,
                "answer": answer,
                "explanation": item.get("explanation") or "",
            }
            row = row_builder(candidate)
            if row:
                rows.append(_qx139_clean_row(row))
    return rows


def _qx139_extract_once(chunk, lang):
    extractor = globals().get("_qxv_extract_sync")
    return list(extractor(chunk, lang) or []) if callable(extractor) else []


async def _qx139_run_blocking(uid, fn, *args, timeout):
    runner = globals().get("_run_blocking")
    if not callable(runner):
        return []
    return await runner(
        _role_of(int(uid)), fn, *args, timeout=timeout,  # type: ignore[name-defined]
    )


async def _qx139_extract_chunk(uid, chunk, lang, expected, semaphore):
    async with semaphore:
        local = []
        with _cx139.suppress(Exception):
            local = await _qx139_run_blocking(
                uid, _qx139_local_rows, chunk, timeout=20,
            ) or []
        merged = []
        seen = set()

        def absorb(rows):
            for source_row in rows or []:
                row = _qx139_clean_row(source_row)
                signature = _qx139_signature(row)
                if row and signature and signature not in seen:
                    seen.add(signature)
                    merged.append(row)

        absorb(local)
        # A complete deterministic parse is both faster and more faithful.
        if expected and len(merged) >= expected:
            return merged, False

        ai_rows = []
        with _cx139.suppress(Exception):
            ai_rows = await _qx139_run_blocking(
                uid, _qx139_extract_once, chunk, lang,
                timeout=_QX139_CHUNK_TIMEOUT,
            ) or []
        absorb(ai_rows)

        # One focused retry only when the provider returned fewer than OCR saw.
        retried = False
        if expected and len(merged) < expected:
            retried = True
            retry_rows = []
            with _cx139.suppress(Exception):
                retry_rows = await _qx139_run_blocking(
                    uid, _qx139_extract_once, chunk, lang,
                    timeout=_QX139_RETRY_TIMEOUT,
                ) or []
            absorb(retry_rows)
        return merged, retried


_qx139_prev_harvest = globals().get("_qxv_harvest")


async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):  # noqa: F811
    chunker = globals().get("_qxv_chunks")
    splitter = globals().get("_qxm_split_questions")
    storer = globals().get("_qxz_store_rows")
    card = globals().get("_qx138_card")
    if not (callable(chunker) and callable(storer)):
        if callable(_qx139_prev_harvest):
            return await _qx139_prev_harvest(update, context, uid, source_text, status, label)
        return 0, 0, 0

    chunks = list(chunker(source_text) or [])
    if not chunks:
        return 0, 0, 0

    expected_by_chunk = []
    for chunk in chunks:
        count = 0
        if callable(splitter):
            with _cx139.suppress(Exception):
                count = len(splitter(chunk) or [])
        expected_by_chunk.append(count)
    expected = sum(expected_by_chunk)

    lang = "bn"
    probe = globals().get("_generation_lang_88")
    if callable(probe):
        with _cx139.suppress(Exception):
            lang = str(probe(source_text) or "bn")

    started = _t139.time()
    semaphore = _a139.Semaphore(min(_QX139_WORKERS, len(chunks)))
    tasks = [
        _a139.create_task(_qx139_extract_chunk(uid, chunk, lang, chunk_expected, semaphore))
        for chunk, chunk_expected in zip(chunks, expected_by_chunk)
    ]
    found = added = dup = retries = 0
    global_seen = set()
    if callable(card):
        await card(status, 0, expected, 0, started)

    try:
        for task in _a139.as_completed(tasks):
            rows, retried = await task
            retries += int(bool(retried))
            fresh = []
            for row in rows or []:
                signature = _qx139_signature(row)
                if signature and signature not in global_seen:
                    global_seen.add(signature)
                    fresh.append(row)
            found += len(fresh)
            if fresh:
                chunk_added, chunk_dup = storer(int(uid), fresh, "src")
                added += int(chunk_added or 0)
                dup += int(chunk_dup or 0)
            if callable(card):
                await card(status, found, expected or found, added, started)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await _a139.gather(*tasks, return_exceptions=True)

    missing = max(0, expected - found)
    _qx139_log(
        "parallel verbatim done: expected=%s found=%s added=%s dup=%s missing=%s "
        "chunks=%s retries=%s seconds=%.1f"
        % (expected, found, added, dup, missing, len(chunks), retries, _t139.time() - started)
    )
    return int(added), int(dup), int(found)


globals()["_qxv_harvest"] = _qxv_harvest
_qx139_log("fast complete verbatim conversion and option cleanup active")