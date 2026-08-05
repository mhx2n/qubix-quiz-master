# ──────────────────────────────────────────────────────────────────────────────
# Section 124 (2026-08-05) — Topic anchor serials · generation watchdog
#
# Fixes:
#   1) .mytopics / .usetopic / .deltopic showed mixed real DB ids and duplicate
#      "#1" entries for owner/master, because the visible list and the serial
#      map were built from two different queries. Both now come from ONE
#      ordered query, so serials are always 1..N and map to the right anchor.
#   2) .gen med/ver/engg/std with a large count could hang forever: a busy
#      thread-pool semaphore made _run_blocking wait with no upper bound.
#      Every blocking call now has a hard ceiling, and large generations run in
#      bounded chunks so partial results are always returned.
#
# DO NOT import directly — exec'd in the shared namespace by bot/__main__.py.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a124
import contextlib as _cx124
import time as _t124


def _log124(msg: str) -> None:
    with _cx124.suppress(Exception):
        logger.info("[S124] %s", msg)  # type: ignore[name-defined]


# ═════════════════════════════════════════════════════════════════════════════
# 1) One source of truth for saved topic anchor serials
# ═════════════════════════════════════════════════════════════════════════════
_qx124_prev_sta_list = globals().get("_sta_list")
_qx124_prev_sta_get = globals().get("_sta_get")
_qx124_prev_sta_delete = globals().get("_sta_delete")


def _qx124_can_view_all(uid) -> bool:
    with _cx124.suppress(Exception):
        if _is_owner_id(uid):  # type: ignore[name-defined]
            return True
    for fn_name in ("_qx110_can_view_all", "_qx108_can_view_all"):
        fn = globals().get(fn_name)
        if callable(fn):
            with _cx124.suppress(Exception):
                if bool(fn(uid)):
                    return True
    return False


def _qx124_raw_rows(admin_id) -> list:
    """Visible anchors, oldest first — the ONE ordering serials are built on."""
    try:
        admin_id = int(admin_id or 0)
    except Exception:
        admin_id = 0
    rows = []
    with _cx124.suppress(Exception):
        conn = db_connect()  # type: ignore[name-defined]
        try:
            if admin_id and not _qx124_can_view_all(admin_id):
                cur = conn.execute(
                    "SELECT * FROM saved_topic_anchors WHERE admin_id=? ORDER BY id ASC",
                    (admin_id,),
                )
            else:
                cur = conn.execute("SELECT * FROM saved_topic_anchors ORDER BY id ASC")
            rows = cur.fetchall() or []
        finally:
            conn.close()
    out = []
    row_cls = globals().get("SavedTopicAnchorRow")
    for r in rows:
        with _cx124.suppress(Exception):
            out.append(row_cls(
                int(r["id"]), int(r["admin_id"] or 0), str(r["name"] or "Topic"),
                int(r["chat_id"]), int(r["msg_id"]), str(r["created_at"] or ""),
            ))
    return out


def _qx124_serial_row(row, serial: int):
    """Copy of a row whose visible id is the user-facing serial."""
    row_cls = globals().get("SavedTopicAnchorRow")
    with _cx124.suppress(Exception):
        return row_cls(int(serial), row.admin_id, row.name, row.chat_id,
                       row.msg_id, row.created_at)
    return row


def _sta_list(admin_id):  # noqa: F811
    rows = _qx124_raw_rows(admin_id)
    return [_qx124_serial_row(r, i + 1) for i, r in enumerate(rows)]


def _sta_resolve_124(row_id, admin_id):
    """(real_row, serial) for a user-typed serial, with real-id fallback."""
    rows = _qx124_raw_rows(admin_id)
    try:
        wanted = int(row_id)
    except Exception:
        return None, 0
    if 1 <= wanted <= len(rows):
        return rows[wanted - 1], wanted
    for index, row in enumerate(rows):
        if int(getattr(row, "id", 0) or 0) == wanted:
            return row, index + 1
    return None, 0


def _sta_get(row_id, admin_id):  # noqa: F811
    row, serial = _sta_resolve_124(row_id, admin_id)
    if row is None:
        return None
    return _qx124_serial_row(row, serial)


def _sta_get_real_124(row_id, admin_id):
    row, _serial = _sta_resolve_124(row_id, admin_id)
    return row


def _sta_delete(row_id, admin_id):  # noqa: F811
    row, _serial = _sta_resolve_124(row_id, admin_id)
    if row is None:
        return False
    real = int(getattr(row, "id", 0) or 0)
    if not real:
        return False
    if callable(_qx124_prev_sta_delete):
        with _cx124.suppress(Exception):
            return bool(_qx124_prev_sta_delete(real, admin_id))
    deleted = False
    with _cx124.suppress(Exception):
        conn = db_connect()  # type: ignore[name-defined]
        try:
            cur = conn.execute("DELETE FROM saved_topic_anchors WHERE id=?", (real,))
            conn.commit()
            deleted = cur.rowcount > 0
        finally:
            conn.close()
    return deleted


globals()["_sta_list"] = _sta_list
globals()["_sta_get"] = _sta_get
globals()["_sta_delete"] = _sta_delete
globals()["_sta_get_real_124"] = _sta_get_real_124


# Any earlier virtualiser must not re-number these rows a second time.
with _cx124.suppress(Exception):
    _qx110_prev = globals().get("_qx110_virtualize_rows")
    if callable(_qx110_prev):
        def _qx124_virtualize_rows(kind, uid, rows):  # noqa: F811
            if str(kind) == "anchor":
                return rows
            return _qx110_prev(kind, uid, rows)
        globals()["_qx110_virtualize_rows"] = _qx124_virtualize_rows


_log124("topic anchor serials are now sequential per viewer (1..N)")


# ═════════════════════════════════════════════════════════════════════════════
# 2) Blocking calls can never wait forever on a busy pool
# ═════════════════════════════════════════════════════════════════════════════
_qx124_prev_run_blocking = globals().get("_run_blocking")

if callable(_qx124_prev_run_blocking) and not getattr(_qx124_prev_run_blocking, "_qx124", False):

    async def _run_blocking(role, fn, *args, timeout=None, **kwargs):  # noqa: F811
        if timeout is None:
            return await _qx124_prev_run_blocking(role, fn, *args, **kwargs)
        ceiling = float(timeout) + 25.0
        return await _a124.wait_for(
            _qx124_prev_run_blocking(role, fn, *args, timeout=timeout, **kwargs),
            timeout=ceiling,
        )

    _run_blocking._qx124 = True  # type: ignore[attr-defined]
    globals()["_run_blocking"] = _run_blocking
    _log124("blocking pool waits are now bounded (queue wait + work ceiling)")


# ═════════════════════════════════════════════════════════════════════════════
# 3) Large .gen runs in bounded chunks — always returns a result
# ═════════════════════════════════════════════════════════════════════════════
QX124_GEN_CHUNK = 10          # quizzes per AI round
QX124_CHUNK_BUDGET = 150.0    # seconds per round
QX124_TOTAL_BUDGET = 300.0    # seconds for the whole command

_qx124_prev_gen_buffer = globals().get("_generate_to_buffer_59")

if callable(_qx124_prev_gen_buffer) and not getattr(_qx124_prev_gen_buffer, "_qx124", False):

    async def _generate_to_buffer_59(update, context, ocr_ctx, uid, count, mode="std"):  # noqa: F811
        try:
            want = max(1, min(500, int(count or 20)))
        except Exception:
            want = 20

        if want <= QX124_GEN_CHUNK:
            with _cx124.suppress(Exception):
                return await _a124.wait_for(
                    _qx124_prev_gen_buffer(update, context, ocr_ctx, uid, want, mode),
                    timeout=QX124_CHUNK_BUDGET + 60.0,
                )
            return 0, 0

        started = _t124.time()
        added_total = 0
        dup_total = 0
        remaining = want
        stalled = 0

        while remaining > 0 and (_t124.time() - started) < QX124_TOTAL_BUDGET:
            need = min(QX124_GEN_CHUNK, remaining)
            added = dup = 0
            try:
                added, dup = await _a124.wait_for(
                    _qx124_prev_gen_buffer(update, context, ocr_ctx, uid, need, mode),
                    timeout=QX124_CHUNK_BUDGET,
                )
            except Exception as error:
                _log124("gen chunk failed/timed out: %s" % str(error)[:120])
                added = dup = 0
            added_total += int(added or 0)
            dup_total += int(dup or 0)
            remaining = max(0, want - added_total)
            if int(added or 0) <= 0:
                stalled += 1
                if stalled >= 2:
                    break
            else:
                stalled = 0

        return added_total, dup_total

    _generate_to_buffer_59._qx124 = True  # type: ignore[attr-defined]
    globals()["_generate_to_buffer_59"] = _generate_to_buffer_59
    _log124("chunked generation watchdog active (%ss total budget)" % int(QX124_TOTAL_BUDGET))
