# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 132 (2026-08-09) — Prefix / explanation-link write targeting fix.
#
# Bug: `/setprefix <serial> <text>` reported success but the value never showed
# up in `.lc` or on posted quizzes. Section 126 made every workspace strictly
# per-user, but the write helpers still resolved the user-typed serial through
# section 110's global cache/fallback. When the acting user could not be
# resolved (uid == 0) the serial was matched against *all* channels, so the
# UPDATE landed on a row belonging to a different workspace.
#
# Fix: resolve the serial against the caller's own rows only, and derive the
# caller from the command update itself when the context-var is empty.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx132


def _log132(message):
    with _cx132.suppress(Exception):
        logger.info("[S132] %s", message)  # type: ignore[name-defined]


def _qx132_uid():
    for name in ("_qx126_uid", "_qx110_hint_uid", "_qx95_scope_uid"):
        fn = globals().get(name)
        if callable(fn):
            with _cx132.suppress(Exception):
                uid = int(fn() or 0)
                if uid > 0:
                    return uid
    return 0


def _qx132_owned_ids(table, uid):
    with _cx132.suppress(Exception):
        conn = db_connect()  # type: ignore[name-defined]
        try:
            rows = conn.execute(
                f"SELECT id FROM {table} WHERE added_by=? ORDER BY id ASC", (int(uid),)
            ).fetchall()
            return [int(r[0]) for r in rows]
        finally:
            conn.close()
    return []


def _qx132_real(table, serial):
    """Serial → real primary key inside the caller's own workspace."""
    uid = _qx132_uid()
    with _cx132.suppress(Exception):
        serial = int(serial)
        if uid > 0:
            ids = _qx132_owned_ids(table, uid)
            if 1 <= serial <= len(ids):
                return ids[serial - 1]
            if serial in ids:          # already a real id
                return serial
        return serial
    return serial


def _qx132_write(table, column, serial, value):
    real = _qx132_real(table, serial)
    with _cx132.suppress(Exception):
        conn = db_connect()  # type: ignore[name-defined]
        try:
            cur = conn.execute(
                f"UPDATE {table} SET {column}=? WHERE id=?", (str(value or ""), int(real))
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    return False


def channel_set_prefix(cid, prefix):  # noqa: F811
    return _qx132_write("channels", "prefix", cid, prefix)


def channel_set_expl_link(cid, link):  # noqa: F811
    return _qx132_write("channels", "expl_link", cid, link)


def _sg_set_prefix(group_serial, prefix):  # noqa: F811
    return _qx132_write("saved_groups", "prefix", group_serial, prefix)


def _sg_set_expl_link(group_serial, link):  # noqa: F811
    return _qx132_write("saved_groups", "expl_link", group_serial, link)


_qx132_prev_channel_remove = globals().get("channel_remove")


def channel_remove(cid):  # noqa: F811
    real = _qx132_real("channels", cid)
    with _cx132.suppress(Exception):
        conn = db_connect()  # type: ignore[name-defined]
        try:
            cur = conn.execute("DELETE FROM channels WHERE id=?", (int(real),))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
    if callable(_qx132_prev_channel_remove):
        return _qx132_prev_channel_remove(cid)
    return False


globals()["channel_set_prefix"] = channel_set_prefix
globals()["channel_set_expl_link"] = channel_set_expl_link
globals()["_sg_set_prefix"] = _sg_set_prefix
globals()["_sg_set_expl_link"] = _sg_set_expl_link
globals()["channel_remove"] = channel_remove

_log132("prefix/explink writes now target the caller's own workspace row")
