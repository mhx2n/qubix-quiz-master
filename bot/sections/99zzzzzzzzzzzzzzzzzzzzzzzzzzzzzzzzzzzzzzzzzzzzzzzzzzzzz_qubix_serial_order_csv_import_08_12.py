# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 142 (2026-08-12) — source-serial ordering + CSV re-import
#
# 1) Image/PDF verbatim harvest still runs in parallel lanes (speed unchanged),
#    but rows are now flushed to the buffer strictly in printed order: chunk
#    order first, then the printed serial (১২। / 12. / (7) ) inside each chunk.
#    The serial itself is still stripped from the delivered question text.
# 2) Any CSV produced by this bot can be uploaded or forwarded back: rows are
#    parsed, buffered and the normal post-action card (channel post / export)
#    appears, exactly like a fresh generation.
#
# Every earlier flow, provider, gate and command stays untouched.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a142
import contextlib as _cx142
import csv as _csv142
import io as _io142
import os as _os142
import re as _re142
import tempfile as _tmp142
import time as _t142


def _qx142_log(message, level="info"):
    with _cx142.suppress(Exception):
        getattr(logger, level)("[S142] %s", message)  # type: ignore[name-defined]


# ═════════════════════════════════════════════════════════════════════════════
# 1) Printed-serial ordering
# ═════════════════════════════════════════════════════════════════════════════
_QX142_BN_DIGITS = {ord(c): str(i) for i, c in enumerate("০১২৩৪৫৬৭৮৯")}
_QX142_SERIAL = _re142.compile(
    r"^\s*[\(\[\{]?\s*(?:Q|No|প্রশ্ন)?\s*([0-9০-৯]{1,4})\s*"
    r"(?:[।|)\]\}:]|[.\-–—](?=\s))"
)


def _qx142_serial_of(row):
    """Return the printed serial of a harvested row, or None."""
    text = str((row or {}).get("question") or (row or {}).get("questions") or "")
    match = _QX142_SERIAL.match(text.strip())
    if not match:
        return None
    with _cx142.suppress(Exception):
        return int(match.group(1).translate(_QX142_BN_DIGITS))
    return None


def _qx142_order_rows(rows):
    """Stable sort by printed serial; unnumbered rows keep their position."""
    items = list(rows or [])
    numbered = [(index, row, _qx142_serial_of(row)) for index, row in enumerate(items)]
    if not any(serial is not None for (_i, _r, serial) in numbered):
        return items
    biggest = max([s for (_i, _r, s) in numbered if s is not None] or [0])
    keyed = []
    last_seen = 0
    for index, row, serial in numbered:
        if serial is None:
            # keep it right after the previous numbered question
            keyed.append(((last_seen + 0.5), index, row))
        else:
            last_seen = serial
            keyed.append((float(min(serial, biggest + 1)), index, row))
    keyed.sort(key=lambda entry: (entry[0], entry[1]))
    return [row for (_k, _i, row) in keyed]


_qx142_prev_harvest = globals().get("_qxv_harvest")


async def _qxv_harvest(update, context, uid, source_text, status=None, label="source"):  # noqa: F811
    chunker = globals().get("_qxv_chunks")
    splitter = globals().get("_qxm_split_questions")
    storer = globals().get("_qxz_store_rows")
    extract = globals().get("_qx139_extract_chunk")
    signature_of = globals().get("_qx139_signature")
    card = globals().get("_qx138_card")
    if not (callable(chunker) and callable(storer) and callable(extract) and callable(signature_of)):
        if callable(_qx142_prev_harvest):
            return await _qx142_prev_harvest(update, context, uid, source_text, status, label)
        return 0, 0, 0

    chunks = list(chunker(source_text) or [])
    if not chunks:
        return 0, 0, 0

    expected_by_chunk = []
    for chunk in chunks:
        count = 0
        if callable(splitter):
            with _cx142.suppress(Exception):
                count = len(splitter(chunk) or [])
        expected_by_chunk.append(count)
    expected = sum(expected_by_chunk)

    lang = "bn"
    probe = globals().get("_generation_lang_88")
    if callable(probe):
        with _cx142.suppress(Exception):
            lang = str(probe(source_text) or "bn")

    workers = int(globals().get("_QX139_WORKERS") or 4)
    semaphore = _a142.Semaphore(max(1, min(workers, len(chunks))))
    started = _t142.time()

    async def indexed(position, chunk, chunk_expected):
        payload = ([], False)
        with _cx142.suppress(Exception):
            payload = await extract(uid, chunk, lang, chunk_expected, semaphore)
        return position, payload

    tasks = [
        _a142.create_task(indexed(position, chunk, chunk_expected))
        for position, (chunk, chunk_expected) in enumerate(zip(chunks, expected_by_chunk))
    ]

    results = {}
    found = added = dup = 0
    cursor = 0
    global_seen = set()
    if callable(card):
        await card(status, 0, expected, 0, started)

    async def flush_ready():
        nonlocal cursor, found, added, dup
        while cursor in results:
            rows, _retried = results.pop(cursor)
            cursor += 1
            fresh = []
            for row in _qx142_order_rows(rows):
                signature = signature_of(row)
                if signature and signature not in global_seen:
                    global_seen.add(signature)
                    fresh.append(row)
            if not fresh:
                continue
            found += len(fresh)
            with _cx142.suppress(Exception):
                chunk_added, chunk_dup = storer(int(uid), fresh, "src")
                added += int(chunk_added or 0)
                dup += int(chunk_dup or 0)
            if callable(card):
                await card(status, found, expected or found, added, started)

    try:
        for future in _a142.as_completed(tasks):
            index, payload = None, ([], False)
            with _cx142.suppress(Exception):
                index, payload = await future
            if index is None:
                continue
            results[int(index)] = payload
            await flush_ready()
        await flush_ready()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await _a142.gather(*tasks, return_exceptions=True)

    _qx142_log(
        "serial-ordered verbatim: expected=%s found=%s added=%s dup=%s chunks=%s seconds=%.1f"
        % (expected, found, added, dup, len(chunks), _t142.time() - started)
    )
    return int(added), int(dup), int(found)


globals()["_qxv_harvest"] = _qxv_harvest


# ═════════════════════════════════════════════════════════════════════════════
# 2) CSV upload / forward → buffer
# ═════════════════════════════════════════════════════════════════════════════
_QX142_Q_KEYS = ("questions", "question", "q", "প্রশ্ন")
_QX142_A_KEYS = ("answer", "ans", "correct", "উত্তর")
_QX142_E_KEYS = ("explanation", "expl", "solution", "ব্যাখ্যা")
_QX142_LETTERS = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "ক": 1, "খ": 2, "গ": 3, "ঘ": 4, "ঙ": 5}


def _qx142_pick(mapping, keys):
    for key in keys:
        for raw_key, value in (mapping or {}).items():
            if str(raw_key or "").strip().casefold() == key:
                return value
    return ""


def _qx142_answer_index(value, options):
    raw = str(value or "").strip()
    if not raw:
        return 0
    digits = raw.translate(_QX142_BN_DIGITS)
    with _cx142.suppress(Exception):
        number = int(_re142.sub(r"[^0-9]", "", digits) or 0)
        if 1 <= number <= len(options):
            return number
    letter = raw.strip("() .").casefold()[:1]
    if letter in _QX142_LETTERS and _QX142_LETTERS[letter] <= len(options):
        return _QX142_LETTERS[letter]
    flat = _re142.sub(r"\s+", " ", raw).casefold()
    for index, option in enumerate(options, start=1):
        if flat and flat == _re142.sub(r"\s+", " ", str(option)).casefold():
            return index
    return 0


def _qx142_rows_from_csv(text):
    body = str(text or "").lstrip("\ufeff")
    if not body.strip():
        return []
    sample = body[:4096]
    delimiter = ","
    with _cx142.suppress(Exception):
        delimiter = _csv142.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    rows = []
    reader = _csv142.DictReader(_io142.StringIO(body), delimiter=delimiter)
    for record in reader:
        if not isinstance(record, dict):
            continue
        question = str(_qx142_pick(record, _QX142_Q_KEYS) or "").strip()
        options = []
        for index in range(1, 8):
            value = ""
            for raw_key, raw_value in record.items():
                if str(raw_key or "").strip().casefold() in ("option%d" % index, "opt%d" % index):
                    value = raw_value
                    break
            value = str(value or "").strip()
            if value:
                options.append(value)
        options = options[:5]
        if not question or len(options) < 4:
            continue
        answer = _qx142_answer_index(_qx142_pick(record, _QX142_A_KEYS), options)
        if not answer:
            continue
        rows.append({
            "question": question,
            "options": options,
            "answer": answer,
            "explanation": str(_qx142_pick(record, _QX142_E_KEYS) or "").strip(),
        })
    return rows


def _qx142_decode(blob):
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        with _cx142.suppress(Exception):
            return bytes(blob or b"").decode(encoding)
    return ""


def _qx142_is_csv(document):
    name = str(getattr(document, "file_name", "") or "").lower()
    mime = str(getattr(document, "mime_type", "") or "").lower()
    return name.endswith(".csv") or "csv" in mime or name.endswith(".tsv")


def _qx142_box(title, body, emoji="📥"):
    boxer = globals().get("ui_box_html")
    if callable(boxer):
        with _cx142.suppress(Exception):
            return boxer(title, body, emoji=emoji)
    return "%s %s\n%s" % (emoji, title, body)


async def qx142_import_csv(update, context):
    message = getattr(update, "effective_message", None)
    user = getattr(update, "effective_user", None)
    document = getattr(message, "document", None) if message is not None else None
    if message is None or user is None or document is None or not _qx142_is_csv(document):
        return None

    gate = globals().get("_qxz_may_run") or globals().get("_qx99_may_run")
    uid = int(user.id)
    if callable(gate):
        allowed = True
        with _cx142.suppress(Exception):
            allowed = bool(gate(uid))
        if not allowed:
            return None

    status = None
    with _cx142.suppress(Exception):
        status = await message.reply_text(
            _qx142_box("CSV → Quiz", "ফাইল পড়া হচ্ছে…", "📥"),
            parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
        )

    text = ""
    path = ""
    try:
        handle = await context.bot.get_file(document.file_id)
        path = _os142.path.join(_tmp142.gettempdir(), "qx142_%s.csv" % uuid.uuid4().hex[:10])  # type: ignore[name-defined]
        await handle.download_to_drive(custom_path=path)
        with open(path, "rb") as stream:
            text = _qx142_decode(stream.read())
    except Exception as error:
        _qx142_log("csv download failed: %s" % error, "warning")
    finally:
        with _cx142.suppress(Exception):
            if path:
                _os142.remove(path)

    rows = []
    with _cx142.suppress(Exception):
        rows = _qx142_rows_from_csv(text)

    if not rows:
        with _cx142.suppress(Exception):
            body = (
                "কোনো বৈধ প্রশ্ন পাওয়া যায়নি।\n\n"
                "কলাম দরকার: <code>questions, option1..option4, answer</code>"
                " (ঐচ্ছিক <code>explanation</code>)।\n"
                "বটের export করা CSV সরাসরি কাজ করবে।"
            )
            if status is not None:
                await status.edit_text(_qx142_box("CSV → Quiz", body, "⚠️"), parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
            else:
                await message.reply_text(_qx142_box("CSV → Quiz", body, "⚠️"), parse_mode=ParseMode.HTML)  # type: ignore[name-defined]
        raise ApplicationHandlerStop  # type: ignore[name-defined]

    storer = globals().get("_qxz_store_rows")
    added = dup = 0
    if callable(storer):
        with _cx142.suppress(Exception):
            chunk_added, chunk_dup = storer(uid, rows, "csv")
            added, dup = int(chunk_added or 0), int(chunk_dup or 0)

    with _cx142.suppress(Exception):
        if status is not None:
            await status.delete()

    total = 0
    with _cx142.suppress(Exception):
        total = int(buffer_count(uid) or 0)  # type: ignore[name-defined]

    card = globals().get("_send_pb_action_card")
    if callable(card):
        with _cx142.suppress(Exception):
            await card(context, message.chat_id, uid, added)
    else:
        with _cx142.suppress(Exception):
            await message.reply_text(
                _qx142_box(
                    "CSV → Quiz",
                    "যোগ হয়েছে: <b>%d</b>\nDuplicate: <b>%d</b>\nBuffer: <b>%d</b>" % (added, dup, total),
                    "✅",
                ),
                parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
            )

    _qx142_log("csv import: rows=%s added=%s dup=%s uid=%s" % (len(rows), added, dup, uid))
    raise ApplicationHandlerStop  # type: ignore[name-defined]


_qx142_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx142_prev_build_app() if callable(_qx142_prev_build_app) else None
    if app is None:
        return app
    with _cx142.suppress(Exception):
        app.add_handler(
            MessageHandler(filters.Document.ALL, qx142_import_csv),  # type: ignore[name-defined]
            group=-3300,
        )
    _qx142_log("csv import handler wired")
    return app


_qx142_log("serial ordering + csv import active")
