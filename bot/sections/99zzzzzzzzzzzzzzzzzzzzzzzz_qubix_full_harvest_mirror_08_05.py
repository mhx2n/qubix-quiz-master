# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 118 — FULL-PAGE HARVEST · LIVE MONGO MIRROR · CLEAN PROGRESS CARDS
#              (2026-08-05)
#
#   1. A question sheet with 10 printed MCQs produced only 1 quiz: the whole
#      page was sent to the model in one shot, so the answer was truncated at
#      the provider's output limit. The page is now split per printed question
#      number, converted in small batches and every missing question is retried
#      individually — so all questions of the page reach the buffer.
#   2. Everything the owner saves/changes is now mirrored to MongoDB rows
#      automatically (debounced live mirror) on top of manual /backup.
#   3. "Posting to Channel …" progress notices (sent OR edited in place) are
#      removed once the run finishes.
#   4. PDF page limit is announced professionally and every menu/card lists the
#      PDF commands for owner and student access.
#
# Loaded last by bot/__main__.py — do not import directly.
# ══════════════════════════════════════════════════════════════════════════════

import asyncio as _aM
import contextlib as _cxM
import re as _reM
import sqlite3 as _sqM
import threading as _thM
import time as _tM

import telegram as _tgM


def _qxm_log(message, level="info"):
    with _cxM.suppress(Exception):
        getattr(logger, level)("[QX118] %s", message)  # type: ignore[name-defined]


_QXM_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


# ═════════════════════════════════════════════════════════════════════════════
# 1) Full-page verbatim harvest — per-question splitting + individual retry
# ═════════════════════════════════════════════════════════════════════════════
_QXM_QNO = _reM.compile(
    r"(?m)^\s*(?:\*\*|__)?\s*(?:\(|\[)?\s*([0-9০-৯]{1,3})\s*(?:\)|\]|\.|।|:|-)\s+"
)


def _qxm_split_questions(text):
    """Split an OCR page into one block per printed question number."""
    raw = str(text or "").strip()
    if not raw:
        return []
    marks = []
    for match in _QXM_QNO.finditer(raw):
        token = match.group(1).translate(_QXM_BN_DIGITS)
        with _cxM.suppress(Exception):
            marks.append((match.start(), int(token)))
    # Keep only a rising (or restarting) question sequence, drop option/step noise.
    kept = []
    for position, number in marks:
        if not kept:
            if number <= 2:
                kept.append((position, number))
            continue
        if number == kept[-1][1] + 1 or number == 1:
            kept.append((position, number))
    if len(kept) < 2:
        return []
    blocks = []
    for index, (position, _number) in enumerate(kept):
        end = kept[index + 1][0] if index + 1 < len(kept) else len(raw)
        block = raw[position:end].strip()
        if len(block) >= 25:
            blocks.append(block)
    return blocks


def _qxm_batches(blocks, max_chars=1500, max_blocks=2):
    out, current, size = [], [], 0
    for block in blocks:
        if current and (len(current) >= max_blocks or size + len(block) > max_chars):
            out.append(current)
            current, size = [], 0
        current.append(block)
        size += len(block)
    if current:
        out.append(current)
    return out


def _qxm_signature(question):
    return _reM.sub(r"\W+", "", str(question or "").casefold())[:110]


def _qxm_rows_from_prompt(prompt, timeout=40):
    raw = globals()["_qxv_ai_raw"](prompt, timeout=timeout)
    if not raw:
        return []
    rows = []
    for item in globals()["_qxv_items"](raw):
        row = globals()["_qxv_row"](item)
        if row:
            rows.append(row)
    return rows


def _qxv_extract_sync(source_text, lang="bn"):  # noqa: F811
    """Harvest EVERY printed MCQ — small batches so nothing is truncated."""
    prompt_of = globals()["_qxv_prompt"]
    blocks = _qxm_split_questions(source_text)
    rows, seen = [], set()

    def _absorb(new_rows):
        gained = 0
        for row in new_rows or []:
            signature = _qxm_signature(row.get("question"))
            if not signature or signature in seen:
                continue
            seen.add(signature)
            rows.append(row)
            gained += 1
        return gained

    globals()["_QXZ_LENIENT"] = True
    try:
        if blocks:
            for batch in _qxm_batches(blocks):
                chunk = "\n\n".join(batch)
                gained = 0
                with _cxM.suppress(Exception):
                    gained = _absorb(_qxm_rows_from_prompt(prompt_of(chunk, lang)))
                if gained >= len(batch):
                    continue
                # Retry each question of this batch on its own — one short call
                # per question can never hit the output-token ceiling.
                for block in batch:
                    with _cxM.suppress(Exception):
                        _absorb(_qxm_rows_from_prompt(prompt_of(block, lang), timeout=30))
            _qxm_log(f"page harvest: {len(blocks)} printed question(s) → {len(rows)} quiz row(s)")
        else:
            for chunk in globals()["_qxv_chunks"](source_text):
                with _cxM.suppress(Exception):
                    _absorb(_qxm_rows_from_prompt(prompt_of(chunk, lang)))
    finally:
        globals()["_QXZ_LENIENT"] = False
    return rows


globals()["_qxv_extract_sync"] = _qxv_extract_sync
globals()["_qxm_split_questions"] = _qxm_split_questions
_qxm_log("full-page harvest installed (per-question batching + retry)")


# ═════════════════════════════════════════════════════════════════════════════
# 2) Live MongoDB mirror — every save the owner makes becomes cloud rows
# ═════════════════════════════════════════════════════════════════════════════
QXM_MIRROR_DEBOUNCE = 45.0     # seconds of quiet before a mirror push
QXM_MIRROR_MIN_GAP = 150.0     # never push more often than this
_QXM_STATE = {"dirty": 0.0, "last": 0.0, "running": False}
_QXM_LOCK = _thM.Lock()
_QXM_WRITE = _reM.compile(
    r"^\s*(insert|update|delete|replace|create|drop|alter)\b", _reM.I
)


def _qxm_mark_dirty():
    with _QXM_LOCK:
        _QXM_STATE["dirty"] = _tM.time()


class _QxmConnection(_sqM.Connection):
    """SQLite connection that flags the mirror whenever data is written."""

    def execute(self, sql, *args, **kwargs):
        if _QXM_WRITE.match(str(sql or "")):
            _qxm_mark_dirty()
        return super().execute(sql, *args, **kwargs)

    def executemany(self, sql, *args, **kwargs):
        if _QXM_WRITE.match(str(sql or "")):
            _qxm_mark_dirty()
        return super().executemany(sql, *args, **kwargs)

    def executescript(self, sql, *args, **kwargs):
        _qxm_mark_dirty()
        return super().executescript(sql, *args, **kwargs)

    def cursor(self, factory=None):
        cursor = super().cursor(factory) if factory is not None else super().cursor()
        return _QxmCursorProxy(cursor)

    def commit(self):
        return super().commit()


class _QxmCursorProxy:
    """Thin proxy so cursor writes also flag the mirror."""

    __slots__ = ("_cursor",)

    def __init__(self, cursor):
        object.__setattr__(self, "_cursor", cursor)

    def execute(self, sql, *args, **kwargs):
        if _QXM_WRITE.match(str(sql or "")):
            _qxm_mark_dirty()
        return self._cursor.execute(sql, *args, **kwargs)

    def executemany(self, sql, *args, **kwargs):
        if _QXM_WRITE.match(str(sql or "")):
            _qxm_mark_dirty()
        return self._cursor.executemany(sql, *args, **kwargs)

    def executescript(self, sql, *args, **kwargs):
        _qxm_mark_dirty()
        return self._cursor.executescript(sql, *args, **kwargs)

    def __iter__(self):
        return iter(self._cursor)

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __setattr__(self, name, value):
        setattr(self._cursor, name, value)


_qxm_prev_db_connect = globals().get("db_connect")


class _QxmConnectionProxy:
    """Mark writes for Mongo mirroring without replacing DB reliability layers.

    The previous implementation opened a brand-new raw sqlite connection here.
    That silently bypassed the process-wide transaction lock installed by the
    reliability section and allowed ensure_user/score callbacks to collide with
    other writers.  This proxy delegates to the already-hardened connection.
    """

    __slots__ = ("_connection",)

    def __init__(self, connection):
        object.__setattr__(self, "_connection", connection)

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def __setattr__(self, name, value):
        if name == "_connection":
            object.__setattr__(self, name, value)
            return
        setattr(self._connection, name, value)

    def cursor(self, *args, **kwargs):
        return _QxmCursorProxy(self._connection.cursor(*args, **kwargs))

    def execute(self, sql, *args, **kwargs):
        if _QXM_WRITE.match(str(sql or "")):
            _qxm_mark_dirty()
        return self._connection.execute(sql, *args, **kwargs)

    def executemany(self, sql, *args, **kwargs):
        if _QXM_WRITE.match(str(sql or "")):
            _qxm_mark_dirty()
        return self._connection.executemany(sql, *args, **kwargs)

    def executescript(self, sql, *args, **kwargs):
        _qxm_mark_dirty()
        return self._connection.executescript(sql, *args, **kwargs)

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(self, *exc):
        return self._connection.__exit__(*exc)


def db_connect():  # noqa: F811
    if not callable(_qxm_prev_db_connect):
        raise RuntimeError("database connection factory is unavailable")
    conn = _qxm_prev_db_connect()
    if isinstance(conn, _QxmConnectionProxy):
        return conn
    with _cxM.suppress(Exception):
        # The Python transaction lock owns contention/backoff.  A short SQLite
        # wait avoids pinning Telegram workers when an external process holds DB.
        conn.execute("PRAGMA busy_timeout=200;")
        conn.execute("PRAGMA foreign_keys=ON;")
    return _QxmConnectionProxy(conn)


if callable(_qxm_prev_db_connect):
    globals()["db_connect"] = db_connect


def _qxm_push_mirror():
    backup = globals().get("mongo_backup_now")
    if not callable(backup):
        return
    with _cxM.suppress(Exception):
        ok_n, fail_n, _summary = backup("live-mirror")
        _qxm_log(f"live mirror pushed: ok={ok_n} fail={fail_n}")


async def _qxm_mirror_loop():
    while True:
        await _aM.sleep(15)
        with _cxM.suppress(Exception):
            now = _tM.time()
            with _QXM_LOCK:
                dirty = float(_QXM_STATE["dirty"] or 0.0)
                last = float(_QXM_STATE["last"] or 0.0)
                busy = bool(_QXM_STATE["running"])
            if busy or dirty <= 0.0:
                continue
            if (now - dirty) < QXM_MIRROR_DEBOUNCE:
                continue
            if last and (now - last) < QXM_MIRROR_MIN_GAP:
                continue
            with _QXM_LOCK:
                _QXM_STATE["running"] = True
                _QXM_STATE["dirty"] = 0.0
            try:
                await _aM.get_event_loop().run_in_executor(None, _qxm_push_mirror)
            finally:
                with _QXM_LOCK:
                    _QXM_STATE["running"] = False
                    _QXM_STATE["last"] = _tM.time()


# ═════════════════════════════════════════════════════════════════════════════
# 3) Progress notices never linger (covers send_message AND edit_message_text)
# ═════════════════════════════════════════════════════════════════════════════
_QXM_PROGRESS = (
    "Posting to Channel", "Posting to Topic", "Posting to Group",
    "Publishing", "পোস্ট হচ্ছে", "publish হচ্ছে",
)
_QXM_DONE = (
    "Posting Complete", "Posted", "Stop Requested", "Posting Failed",
    "Score", "Buffer Empty", "Channel Not Found",
)
_QXM_TRACK = {}


def _qxm_has(body, markers):
    text = str(body or "")
    return any(marker in text for marker in markers)


async def _qxm_retire(bot, chat_key, force=False):
    entry = _QXM_TRACK.get(chat_key)
    if not entry:
        return
    message_id, stamp = entry
    if not force and (_tM.monotonic() - stamp) < 6.0:
        return
    _QXM_TRACK.pop(chat_key, None)
    with _cxM.suppress(Exception):
        await bot.delete_message(chat_id=chat_key, message_id=int(message_id))


_qxm_prev_send = _tgM.Bot.send_message


async def _qxm_send_message(self, *args, **kwargs):
    chat_id = kwargs.get("chat_id", args[0] if args else None)
    text = kwargs.get("text", args[1] if len(args) > 1 else None)
    message = await _qxm_prev_send(self, *args, **kwargs)
    with _cxM.suppress(Exception):
        key = str(chat_id)
        if _qxm_has(text, _QXM_PROGRESS):
            _QXM_TRACK[key] = (getattr(message, "message_id", 0), _tM.monotonic())
        elif _qxm_has(text, _QXM_DONE):
            await _qxm_retire(self, key, force=True)
        else:
            # Any later card in the same chat sweeps a stale progress notice.
            await _qxm_retire(self, key)
    return message


if not getattr(_tgM.Bot.send_message, "_qxm", False):
    _qxm_send_message._qxm = True  # type: ignore[attr-defined]
    _tgM.Bot.send_message = _qxm_send_message


_qxm_prev_edit = _tgM.Bot.edit_message_text


async def _qxm_edit_message_text(self, *args, **kwargs):
    result = await _qxm_prev_edit(self, *args, **kwargs)
    with _cxM.suppress(Exception):
        chat_id = kwargs.get("chat_id", args[1] if len(args) > 1 else None)
        text = kwargs.get("text", args[0] if args else None)
        message_id = kwargs.get("message_id", args[2] if len(args) > 2 else None)
        if message_id is None and hasattr(result, "message_id"):
            message_id = getattr(result, "message_id", None)
        if chat_id is None and hasattr(result, "chat_id"):
            chat_id = getattr(result, "chat_id", None)
        if chat_id is not None and message_id is not None and _qxm_has(text, _QXM_PROGRESS):
            _QXM_TRACK[str(chat_id)] = (int(message_id), _tM.monotonic())
    return result


if not getattr(_tgM.Bot.edit_message_text, "_qxm", False):
    _qxm_edit_message_text._qxm = True  # type: ignore[attr-defined]
    _tgM.Bot.edit_message_text = _qxm_edit_message_text

_qxm_log("progress-notice cleanup installed")


# ═════════════════════════════════════════════════════════════════════════════
# 4) PDF limits announced + PDF commands present in every menu / card
# ═════════════════════════════════════════════════════════════════════════════
QXM_PDF_MAX = int(globals().get("QXZ_PDF_MAX_PAGES") or 20)

_QXM_PDF_NOTE = (
    "\n\n<b>📄 PDF থেকে quiz — নিয়ম ও সীমা</b>\n"
    f"• একবারে সর্বোচ্চ <b>{QXM_PDF_MAX}</b> পৃষ্ঠা পড়া যাবে\n"
    "• <code>.gen 1-5</code> → ঐ পৃষ্ঠাগুলোর সব প্রশ্ন buffer-এ; পরে "
    "<code>.gen 6-10</code> দিলে পরেরগুলো যোগ হবে\n"
    "• <code>/pdfpages 3-7 20</code> → নির্দিষ্ট পৃষ্ঠা থেকে quiz\n"
    "• <code>.gen</code> (প্রশ্নের ছবি/PDF-এ reply) → পাতায় থাকা প্রতিটি প্রশ্ন quiz-এ\n"
    "• PDF যত বড়, সময় তত বেশি — একবারে ছোট রেঞ্জ দিলে সবচেয়ে নির্ভুল ফল আসে"
)

_QXM_MENU_ROWS = [
    ("pdfpages", f"PDF-এর নির্দিষ্ট পৃষ্ঠা থেকে quiz (সর্বোচ্চ {QXM_PDF_MAX} পৃষ্ঠা)"),
]

for _qxm_menu_name in (
    "QX97_USER_MENU_COMMANDS", "QX94_USER_MENU_COMMANDS",
    "QX94_OWNER_MENU_COMMANDS", "QX112_STUDENT_MENU_COMMANDS",
    "QX98_USER_MENU_COMMANDS",
):
    with _cxM.suppress(Exception):
        menu = globals().get(_qxm_menu_name)
        if isinstance(menu, list):
            existing = {str(row[0]) for row in menu if row}
            for name, description in _QXM_MENU_ROWS:
                if name not in existing:
                    menu.append((name, description))
            globals()[_qxm_menu_name] = menu[:99]

for _qxm_set_name in (
    "QX_WORKSPACE_COMMANDS", "QX113_STUDENT_COMMANDS",
    "QX112_STUDENT_COMMANDS", "QX111_STUDENT_COMMANDS",
):
    with _cxM.suppress(Exception):
        bucket = globals().get(_qxm_set_name)
        if isinstance(bucket, set):
            bucket |= {"pdfpages", "pdfpage", "gen"}

for _qxm_card_name in (
    "QX112_STUDENT_COMMANDS_CARD", "QX115_STUDENT_HELP_CARD",
    "QX95_USER_COMMANDS_CARD", "QX94_USER_COMMANDS_CARD",
    "QX93_COMMANDS_CARD", "QX94_OWNER_CARD",
):
    with _cxM.suppress(Exception):
        card = globals().get(_qxm_card_name)
        if isinstance(card, str) and card and "PDF থেকে quiz — নিয়ম ও সীমা" not in card:
            globals()[_qxm_card_name] = card + _QXM_PDF_NOTE


# ═════════════════════════════════════════════════════════════════════════════
# 5) Wiring — start the live mirror loop
# ═════════════════════════════════════════════════════════════════════════════
_qxm_prev_build_app = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qxm_prev_build_app() if callable(_qxm_prev_build_app) else None
    if app is None:
        return app
    captured = getattr(app, "post_init", None)

    async def _qxm_post_init(application):
        with _cxM.suppress(Exception):
            _aM.create_task(_qxm_mirror_loop())
            _qxm_log("live MongoDB mirror loop started")
        if callable(captured):
            with _cxM.suppress(Exception):
                await captured(application)

    with _cxM.suppress(Exception):
        app.post_init = _qxm_post_init
    return app


_qxm_log("section 118 loaded")
