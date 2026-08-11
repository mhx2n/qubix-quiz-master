# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 138 (2026-08-11) — live verbatim harvest, serial scrub, sticky explink
#
# 1) PDF/image verbatim harvest (.gen / .pdfpages) ran every OCR chunk inside a
#    single blocking call, so the card sat at "0 / N" until the whole run ended.
#    Now each chunk is harvested one at a time, stored immediately and the same
#    status card is edited live (count + percent + elapsed).
# 2) Printed serial numbers ("১২|", "২৩.", "08।", "2)") are stripped from the
#    question text, while trailing bracketed credits such as [আলীম স্যার] stay.
# 3) The owner's explanation link is now reserved inside Telegram's 200-char
#    explanation budget: only the body is trimmed, the link never disappears.
#
# Generation prompts, providers, lanes and every other flow stay untouched.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx138
import re as _re138
import time as _t138


def _log138(message, level="info"):
    with _cx138.suppress(Exception):
        getattr(logger, level)("[S138] %s", message)  # type: ignore[name-defined]


# ═════════════════════════════════════════════════════════════════════════════
# 1) Serial scrub — leading printed numbering only
# ═════════════════════════════════════════════════════════════════════════════
_QX138_SERIAL = _re138.compile(
    r"^\s*[\(\[\{]?\s*(?:Q|No|প্রশ্ন)?\s*[0-9০-৯]{1,4}\s*"
    r"(?:[।|)\]\}:]+|[.\-–—]+(?=\s))\s*"
)
_QX138_WRAP_STARS = _re138.compile(r"^\*+\s*(.+?)\s*\*+$", _re138.DOTALL)


def _qx138_strip_serial(value):
    text = str(value or "").strip()
    if not text:
        return text
    for _ in range(2):  # handles "০৮। ১২)" style double numbering
        stripped = _QX138_SERIAL.sub("", text, count=1).strip()
        if stripped and stripped != text:
            text = stripped
        else:
            break
    return text


def _qx138_clean_option(value):
    text = str(value or "").strip()
    if not text:
        return text
    match = _QX138_WRAP_STARS.match(text)
    if match and "*" not in match.group(1):
        text = match.group(1).strip()
    return _qx138_strip_serial(text)


_qx138_prev_sanitize_item = globals().get("_sanitize_item_for_poll")


def _sanitize_item_for_poll(item):  # noqa: F811
    payload = dict(item or {})
    if callable(_qx138_prev_sanitize_item):
        with _cx138.suppress(Exception):
            payload = dict(_qx138_prev_sanitize_item(payload) or payload)
    with _cx138.suppress(Exception):
        payload["questions"] = _qx138_strip_serial(payload.get("questions"))
    for index in range(1, 6):
        key = "option%d" % index
        if payload.get(key):
            with _cx138.suppress(Exception):
                payload[key] = _qx138_clean_option(payload.get(key))
    return payload


globals()["_sanitize_item_for_poll"] = _sanitize_item_for_poll

_qx138_prev_store_rows = globals().get("_qxz_store_rows")
if callable(_qx138_prev_store_rows):
    def _qxz_store_rows(uid, rows, mode="std"):  # noqa: F811
        cleaned = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            with _cx138.suppress(Exception):
                item["question"] = _qx138_strip_serial(
                    item.get("question") or item.get("questions")
                )
            with _cx138.suppress(Exception):
                options = item.get("options")
                if isinstance(options, (list, tuple)):
                    item["options"] = [_qx138_clean_option(o) for o in options]
            cleaned.append(item)
        return _qx138_prev_store_rows(uid, cleaned, mode)

    globals()["_qxz_store_rows"] = _qxz_store_rows


# ═════════════════════════════════════════════════════════════════════════════
# 2) Sticky explanation link — trim the body, never the link
# ═════════════════════════════════════════════════════════════════════════════
_QX138_EXPL_BUDGET = 195
_qx138_prev_trim_expl = globals().get("_trim_expl_for_poll")


def _trim_expl_for_poll(expl, link=""):  # noqa: F811
    body = str(expl or "")
    if callable(_qx138_prev_trim_expl):
        with _cx138.suppress(Exception):
            body = str(_qx138_prev_trim_expl(body, "") or "")
    tail = str(link or "").strip()
    body = body.strip()
    if tail and body.endswith(tail):
        body = body[: -len(tail)].strip()
    if not tail:
        return body[:_QX138_EXPL_BUDGET].strip()
    room = _QX138_EXPL_BUDGET - len(tail) - 1
    if room < 0:
        return tail[:_QX138_EXPL_BUDGET]
    if len(body) > room:
        body = body[: max(0, room - 3)].rstrip() + "..." if room >= 8 else ""
    return (body + "\n" + tail).strip() if body else tail


globals()["_trim_expl_for_poll"] = _trim_expl_for_poll


# ═════════════════════════════════════════════════════════════════════════════
# 3) Live verbatim harvest — chunk by chunk, same status card
# ═════════════════════════════════════════════════════════════════════════════
_qx138_prev_harvest = globals().get("_qxv_harvest")


def _qx138_elapsed(started):
    seconds = max(0, int(_t138.time() - float(started or 0)))
    minutes, rest = divmod(seconds, 60)
    return "%dm %02ds" % (minutes, rest) if minutes else "%ds" % rest


async def _qx138_card(status, found, expected, added, started, title="Converting Questions"):
    if status is None:
        return
    target = max(1, int(expected or 0) or int(found or 0) or 1)
    percent = max(0, min(100, round((int(found or 0) / target) * 100)))
    body = (
        "শনাক্ত হয়েছে: <b>%d</b>\n"
        "তৈরি হয়েছে: <b>%d</b> / <b>%d</b>\n"
        "Progress: <b>%d%%</b>\n"
        "Buffer-এ যোগ: <b>%d</b>\n"
        "সময়: <code>%s</code>\n\n"
        "Source-এর প্রশ্ন ও সমাধান হুবহু যাচাই হচ্ছে…"
        % (int(expected or 0), int(found or 0), int(expected or 0) or int(found or 0),
           percent, int(added or 0), _qx138_elapsed(started))
    )
    boxer = globals().get("ui_box_html")
    text = boxer(title, body, emoji="🧠") if callable(boxer) else body
    with _cx138.suppress(Exception):
        await status.edit_text(text, parse_mode=ParseMode.HTML)  # type: ignore[name-defined]


def _qx138_chunk_sync(chunk_text, lang="bn"):
    extractor = globals().get("_qxv_extract_sync")
    if not callable(extractor):
        return []
    return extractor(chunk_text, lang) or []


async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):  # noqa: F811
    chunker = globals().get("_qxv_chunks")
    splitter = globals().get("_qxm_split_questions")
    storer = globals().get("_qxz_store_rows")
    runner = globals().get("_run_blocking")
    if not (callable(chunker) and callable(storer) and callable(runner)):
        if callable(_qx138_prev_harvest):
            return await _qx138_prev_harvest(update, context, uid, source_text, status, label)
        return 0, 0, 0

    chunks = []
    with _cx138.suppress(Exception):
        chunks = list(chunker(source_text) or [])
    if not chunks:
        if callable(_qx138_prev_harvest):
            return await _qx138_prev_harvest(update, context, uid, source_text, status, label)
        return 0, 0, 0

    expected = 0
    if callable(splitter):
        with _cx138.suppress(Exception):
            expected = len(splitter(source_text) or [])

    lang = "bn"
    lang_probe = globals().get("_generation_lang_88")
    if callable(lang_probe):
        with _cx138.suppress(Exception):
            lang = str(lang_probe(source_text) or "bn")

    started = _t138.time()
    seen = set()
    found = added = dup = 0
    await _qx138_card(status, 0, expected, 0, started)

    for chunk in chunks:
        rows = []
        with _cx138.suppress(Exception):
            rows = await runner(
                _role_of(int(uid)), _qx138_chunk_sync, chunk, lang, timeout=300,  # type: ignore[name-defined]
            ) or []
        fresh = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            question = str(row.get("question") or row.get("questions") or "")
            signature = _re138.sub(r"\W+", "", question.casefold())[:110]
            if not signature or signature in seen:
                continue
            seen.add(signature)
            fresh.append(row)
        if fresh:
            found += len(fresh)
            with _cx138.suppress(Exception):
                chunk_added, chunk_dup = storer(int(uid), fresh, "src")
                added += int(chunk_added or 0)
                dup += int(chunk_dup or 0)
        await _qx138_card(status, found, expected or found, added, started)

    if status is not None:
        boxer = globals().get("ui_box_html")
        body = (
            "তৈরি হয়েছে: <b>%d</b> / <b>%d</b>\n"
            "Buffer-এ যোগ: <b>%d</b>\n"
            "সময়: <code>%s</code>"
            % (found, expected or found, added, _qx138_elapsed(started))
        )
        text = boxer("Finalising Questions", body, emoji="✅") if callable(boxer) else body
        with _cx138.suppress(Exception):
            await status.edit_text(text, parse_mode=ParseMode.HTML)  # type: ignore[name-defined]

    _log138("verbatim harvest live: found=%s added=%s dup=%s chunks=%s" % (found, added, dup, len(chunks)))
    return int(added), int(dup), int(found)


globals()["_qxv_harvest"] = _qxv_harvest

_log138("live verbatim progress, serial scrub and sticky explanation link active")