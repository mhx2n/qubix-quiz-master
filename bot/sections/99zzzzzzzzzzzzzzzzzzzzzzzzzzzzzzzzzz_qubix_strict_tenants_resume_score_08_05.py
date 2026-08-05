# -*- coding: utf-8 -*-
# SECTION 126 — strict workspace ownership + resumed batch final score.
# Loaded last by bot/__main__.py; do not import directly.

import contextlib as _cx126
import time as _t126


def _qx126_log(message):
    with _cx126.suppress(Exception):
        logger.info("[S126] %s", message)


def _qx126_uid(explicit=None):
    if explicit is not None:
        with _cx126.suppress(Exception):
            value = int(explicit)
            if value:
                return value
    acting = globals().get("_QX_ACTING_OWNER")
    if acting is not None:
        with _cx126.suppress(Exception):
            return int(acting.get() or 0)
    return 0


# Every workspace is private, including the main owner's workspace.  There is
# deliberately no owner "view all" exception in user-facing list/get helpers.
def _qx126_channel_rows(uid):
    conn = db_connect()
    try:
        return conn.execute(
            "SELECT id,channel_chat_id,title,prefix,expl_link,added_by "
            "FROM channels WHERE added_by=? ORDER BY id ASC", (int(uid),),
        ).fetchall()
    finally:
        conn.close()


def channel_list_for_user(requester_id):  # noqa: F811
    rows = _qx126_channel_rows(requester_id)
    return [ChannelRow(
        id=index, channel_chat_id=int(row["channel_chat_id"]),
        title=str(row["title"] or ""), prefix=str(row["prefix"] or ""),
        expl_link=str(row["expl_link"] or ""), added_by=int(row["added_by"] or 0),
    ) for index, row in enumerate(rows, start=1)]


def channel_get_by_id_for_user(requester_id, channel_id):  # noqa: F811
    rows = _qx126_channel_rows(requester_id)
    try:
        serial = int(channel_id)
    except Exception:
        return None
    if not 1 <= serial <= len(rows):
        return None
    row = rows[serial - 1]
    return ChannelRow(
        id=int(row["id"]), channel_chat_id=int(row["channel_chat_id"]),
        title=str(row["title"] or ""), prefix=str(row["prefix"] or ""),
        expl_link=str(row["expl_link"] or ""), added_by=int(row["added_by"] or 0),
    )


def _qx126_group_rows(uid):
    conn = db_connect()
    try:
        return conn.execute(
            "SELECT * FROM saved_groups WHERE added_by=? ORDER BY id ASC", (int(uid),),
        ).fetchall()
    finally:
        conn.close()


def _sg_list(requester_id):  # noqa: F811
    rows = _qx126_group_rows(requester_id)
    return [SavedGroupRow(
        index, int(row["group_chat_id"]), str(row["title"] or ""),
        int(row["added_by"] or 0), row["created_at"],
    ) for index, row in enumerate(rows, start=1)]


def _sg_get(serial, requester_id):  # noqa: F811
    rows = _qx126_group_rows(requester_id)
    try:
        wanted = int(serial)
    except Exception:
        return None
    if not 1 <= wanted <= len(rows):
        return None
    row = rows[wanted - 1]
    return SavedGroupRow(
        int(row["id"]), int(row["group_chat_id"]), str(row["title"] or ""),
        int(row["added_by"] or 0), row["created_at"],
    )


_QX126_TOPIC_MAP = {}  # (uid, visible serial) -> (real id, group id, timestamp)


def _qx126_topic_rows(group_id, uid):
    conn = db_connect()
    try:
        return conn.execute(
            "SELECT * FROM group_topics WHERE group_id=? AND added_by=? ORDER BY id ASC",
            (int(group_id), int(uid)),
        ).fetchall()
    finally:
        conn.close()


def _gt_list(group_id, requester_id=None):  # noqa: F811
    uid = _qx126_uid(requester_id)
    if uid <= 0:
        return []
    rows = _qx126_topic_rows(group_id, uid)
    out = []
    for serial, row in enumerate(rows, start=1):
        _QX126_TOPIC_MAP[(uid, serial)] = (int(row["id"]), int(group_id), _t126.time())
        out.append(GroupTopicRow(
            serial, int(row["group_id"]), str(row["topic_name"] or ""),
            row["thread_id"], int(row["added_by"] or 0), row["created_at"],
        ))
    return out


def _gt_get(topic_id, requester_id=None):  # noqa: F811
    uid = _qx126_uid(requester_id)
    try:
        serial = int(topic_id)
    except Exception:
        return None
    mapped = _QX126_TOPIC_MAP.get((uid, serial))
    if not mapped or (_t126.time() - mapped[2]) > 1800:
        return None
    conn = db_connect()
    try:
        row = conn.execute(
            "SELECT * FROM group_topics WHERE id=? AND group_id=? AND added_by=?",
            (mapped[0], mapped[1], uid),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return GroupTopicRow(
        int(row["id"]), int(row["group_id"]), str(row["topic_name"] or ""),
        row["thread_id"], int(row["added_by"] or 0), row["created_at"],
    )


def _qx126_anchor_rows(uid):
    conn = db_connect()
    try:
        return conn.execute(
            "SELECT * FROM saved_topic_anchors WHERE admin_id=? ORDER BY id ASC", (int(uid),),
        ).fetchall()
    finally:
        conn.close()


def _sta_list(admin_id):  # noqa: F811
    rows = _qx126_anchor_rows(admin_id)
    return [SavedTopicAnchorRow(
        index, int(row["admin_id"] or 0), str(row["name"] or "Topic"),
        int(row["chat_id"]), int(row["msg_id"]), str(row["created_at"] or ""),
    ) for index, row in enumerate(rows, start=1)]


def _qx126_anchor_real(row_id, admin_id):
    rows = _qx126_anchor_rows(admin_id)
    try:
        serial = int(row_id)
    except Exception:
        return None
    return rows[serial - 1] if 1 <= serial <= len(rows) else None


def _sta_get(row_id, admin_id):  # noqa: F811
    row = _qx126_anchor_real(row_id, admin_id)
    if not row:
        return None
    return SavedTopicAnchorRow(
        int(row_id), int(row["admin_id"] or 0), str(row["name"] or "Topic"),
        int(row["chat_id"]), int(row["msg_id"]), str(row["created_at"] or ""),
    )


def _sta_delete(row_id, admin_id):  # noqa: F811
    row = _qx126_anchor_real(row_id, admin_id)
    if not row:
        return False
    conn = db_connect()
    try:
        cur = conn.execute(
            "DELETE FROM saved_topic_anchors WHERE id=? AND admin_id=?",
            (int(row["id"]), int(admin_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


globals()["channel_list_for_user"] = channel_list_for_user
globals()["channel_get_by_id_for_user"] = channel_get_by_id_for_user
globals()["_sg_list"] = _sg_list
globals()["_sg_get"] = _sg_get
globals()["_gt_list"] = _gt_list
globals()["_gt_get"] = _gt_get
globals()["_sta_list"] = _sta_list
globals()["_sta_get"] = _sta_get
globals()["_sta_delete"] = _sta_delete


# Preserve the original first quiz and interim score message for a stopped run.
_qx126_prev_post = globals().get("_post_buffer_to_chat")
_qx126_prev_score = globals().get("_send_score_msg")


if callable(_qx126_prev_post):
    async def _post_buffer_to_chat(context, admin_id, chat_id, items, thread_id=None,  # noqa: F811
                                   group_prefix="", group_expl_link=""):
        result = await _qx126_prev_post(
            context, admin_id, chat_id, items, thread_id, group_prefix, group_expl_link,
        )
        ok, fail, first_id = result
        job = globals().get("_QXZ_RESUME", {}).get(int(admin_id or 0))
        if isinstance(job, dict):
            job["first_quiz_id"] = first_id
            job["posted"] = int(ok or 0)
            job["total"] = len(list(items or []))
            job["score_message_id"] = None
            context.__dict__["_qx126_stopped_job"] = job
        return result

    globals()["_post_buffer_to_chat"] = _post_buffer_to_chat


if callable(_qx126_prev_score):
    async def _send_score_msg(context, admin_id, chat_id, ok_count, first_post_msg_id, thread_id=None):  # noqa: F811
        job = context.__dict__.get("_qx126_stopped_job")
        before = None
        with _cx126.suppress(Exception):
            before = await context.bot.get_chat(chat_id)
        result = await _qx126_prev_score(
            context, admin_id, chat_id, ok_count, first_post_msg_id, thread_id=thread_id,
        )
        # The normal sender currently returns no Message. Resolve the immediately
        # following message id from the first poll; Telegram message ids are
        # contiguous within a chat for bot-created batch output.
        if isinstance(job, dict):
            job["first_quiz_id"] = job.get("first_quiz_id") or first_post_msg_id
            with _cx126.suppress(Exception):
                job["score_message_id"] = int(first_post_msg_id) + int(ok_count or 0)
            context.__dict__.pop("_qx126_stopped_job", None)
        return result

    globals()["_send_score_msg"] = _send_score_msg


_qx126_prev_resume = globals().get("qx99_cmd_resumequiz")


async def qx99_cmd_resumequiz(update, context):  # noqa: F811
    uid = 0
    with _cx126.suppress(Exception):
        uid = int(globals()["_qx99_uid"](update))
    jobs = globals().get("_QXZ_RESUME", {})
    job = jobs.pop(uid, None) if isinstance(jobs, dict) else None
    if not isinstance(job, dict) or not job.get("rows"):
        if callable(_qx126_prev_resume):
            return await _qx126_prev_resume(update, context)
        raise ApplicationHandlerStop

    globals().get("_QX99_STOP", set()).discard(uid)
    with _cx126.suppress(Exception):
        globals()["_stop_clear_81"](uid)
    old_score = job.get("score_message_id")
    if old_score:
        with _cx126.suppress(Exception):
            await context.bot.delete_message(chat_id=int(job["chat_id"]), message_id=int(old_score))

    message = getattr(update, "effective_message", None)
    status = None
    if message is not None:
        with _cx126.suppress(Exception):
            status = await message.reply_text(
                ui_box_html("Resuming Run", f"বাকি <b>{len(job['rows'])}</b>টি quiz পাঠানো হচ্ছে…", emoji="▶️"),
                parse_mode=ParseMode.HTML,
            )
    ok = fail = 0
    poster = globals().get("_post_buffer_to_chat")
    if callable(poster):
        ok, fail, _ignored = await poster(
            context, uid, job.get("chat_id"), list(job.get("rows") or []),
            job.get("thread_id"), job.get("prefix") or "", job.get("link") or "",
        )
    total = int(job.get("posted") or 0) + int(ok or 0)
    first_id = job.get("first_quiz_id") or _ignored
    if total > 0 and first_id and callable(globals().get("_send_score_msg")):
        await globals()["_send_score_msg"](
            context, uid, int(job["chat_id"]), total, int(first_id),
            thread_id=job.get("thread_id"),
        )
    if status is not None:
        with _cx126.suppress(Exception):
            await status.delete()
    if message is not None:
        with _cx126.suppress(Exception):
            await message.reply_text(
                ui_box_html(
                    "Resume Complete",
                    f"✅ সম্পূর্ণ ব্যাচে পাঠানো: <b>{total}</b>\n⚠️ ব্যর্থ: <b>{int(fail or 0)}</b>",
                    emoji="✅",
                ), parse_mode=ParseMode.HTML,
            )
    raise ApplicationHandlerStop


globals()["qx99_cmd_resumequiz"] = qx99_cmd_resumequiz
globals()["cmd_resumequiz_81"] = qx99_cmd_resumequiz

_qx126_prev_build = globals().get("build_app")


def build_app():  # noqa: F811
    app = _qx126_prev_build() if callable(_qx126_prev_build) else None
    register = globals().get("_register_dual_command")
    if app is not None and callable(register):
        with _cx126.suppress(Exception):
            register(app, "resumequiz", qx99_cmd_resumequiz, group=-9000)
    return app


_qx126_log("strict per-owner resources and resumed-batch final scoreboard active")
