# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 129 (2026-08-09) — source fidelity, arbitrary page serials, live .gen
# progress.  Final-load overlay; existing buffer/post/role/tenant flows stay intact.
# ──────────────────────────────────────────────────────────────────────────────

import asyncio as _a129
import contextlib as _cx129
import re as _re129
import time as _t129


def _log129(message, level="info"):
    with _cx129.suppress(Exception):
        getattr(logger, level)("[S129] %s", message)  # type: ignore[name-defined]


# ── 1) OCR question splitting ─────────────────────────────────────────────────
# Question-bank pages commonly start at 11, 25, 51, etc.  The old splitter only
# accepted an initial 1/2 and consequently sent the entire page in one request.
_QX129_QNO = _re129.compile(
    r"(?m)^\s*(?:\*\*|__)?\s*(?:\(|\[)?\s*([0-9০-৯]{1,3})\s*(?:\)|\]|\.|।|:|-)\s+"
)
_QX129_BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _qxm_split_questions(text):  # noqa: F811
    """Split any consecutively numbered question-bank page, regardless of start."""
    raw = str(text or "").strip()
    if not raw:
        return []
    marks = []
    for match in _QX129_QNO.finditer(raw):
        with _cx129.suppress(Exception):
            marks.append((match.start(), int(match.group(1).translate(_QX129_BN_DIGITS))))
    if len(marks) < 2:
        return []

    # Pick the longest consecutive run. This rejects option numbers, formula
    # steps and page furniture while accepting pages beginning at any serial.
    runs = []
    current = []
    for mark in marks:
        if not current or mark[1] == current[-1][1] + 1:
            current.append(mark)
        elif mark[1] == 1:
            if current:
                runs.append(current)
            current = [mark]
        else:
            if len(current) >= 2:
                runs.append(current)
            current = [mark]
    if current:
        runs.append(current)
    # OCR can miss one serial or read a two-column page out of sequence. Keeping
    # only the longest run silently discarded every question in the other
    # valid runs. Merge all consecutive runs in document order instead.
    valid_runs = [run for run in runs if len(run) >= 2]
    if not valid_runs:
        return []
    kept = []
    seen_positions = set()
    for run in sorted(valid_runs, key=lambda value: value[0][0]):
        for mark in run:
            if mark[0] not in seen_positions:
                kept.append(mark)
                seen_positions.add(mark[0])
    kept.sort(key=lambda value: value[0])

    blocks = []
    for index, (position, _number) in enumerate(kept):
        end = kept[index + 1][0] if index + 1 < len(kept) else len(raw)
        block = raw[position:end].strip()
        if len(block) >= 20:
            blocks.append(block)
    return blocks


globals()["_qxm_split_questions"] = _qxm_split_questions


# ── 2) Exact source-subject lock ──────────────────────────────────────────────
# Physics/chemistry naturally contain √, equations and exponents. Those symbols
# prove that formulas exist, but do NOT license unrelated calculus questions.
_QX129_CALCULUS = _re129.compile(
    r"(?:\\(?:int|lim)\b|[∫]|\b(?:integral|integration|derivative|differentiat(?:e|ion)|"
    r"calculus|limit)\b|সমাকলন|অন্তরকরণ|অবকলন|ক্যালকুলাস|সীমা\s*নির্ণয়|লিমিট)",
    _re129.IGNORECASE,
)


def _qx129_source_only(value):
    cleaner = globals().get("_qx125_source_only")
    if callable(cleaner):
        with _cx129.suppress(Exception):
            return str(cleaner(value) or "")
    return str(value or "")


# Section 106's rescue used any scientific symbol as a reason to generate
# calculus. Restrict that rescue to actual calculus evidence.
globals()["_QX106_MATH"] = _QX129_CALCULUS

_qx129_prev_prompt = globals().get("_make_fast_new_mcq_prompt_74")
if callable(_qx129_prev_prompt):
    def _make_fast_new_mcq_prompt_74(source_text, n, *, easy=0, medium=0, hard=0,
                                     avoid_text=""):  # noqa: F811
        source = _qx129_source_only(source_text)
        prompt = str(_qx129_prev_prompt(
            source_text, n, easy=easy, medium=medium, hard=hard,
            avoid_text=avoid_text,
        ) or "")
        lock = (
            "\n\nFINAL SOURCE-FIDELITY LOCK (OVERRIDES CONFLICTING EARLIER RULES):\n"
            "- Identify the source subject and its explicitly present concepts first.\n"
            "- Every generated question must stay inside those exact concepts.\n"
            "- A formula, radical, exponent, variable or numerical calculation in a "
            "physics/chemistry source does not make the source calculus.\n"
            "- Never introduce an unrelated chapter merely to fill the requested count.\n"
        )
        if not _QX129_CALCULUS.search(source):
            lock += (
                "- The source contains no calculus evidence: integration, differentiation "
                "and limit questions are strictly forbidden.\n"
            )
        return prompt + lock

    globals()["_make_fast_new_mcq_prompt_74"] = _make_fast_new_mcq_prompt_74

# The zero-result rescue previously hard-coded limits/derivatives/integration.
globals()["_QXZ_MATH_HINT"] = (
    "Generate only from the exact subject and concepts present in SOURCE. Scientific "
    "notation and equations must be preserved, but never introduce calculus, algebra, "
    "chemistry, physics, or another chapter unless that concept is explicitly in SOURCE. "
    "Use exactly 4 complete options and make the explanation agree with the answer."
)


# The previous final math validator could run eight additional provider cascades
# after the normal generator had already retried. A five-question request could
# therefore occupy a worker for several minutes even after the UI timed out.
# Keep the same prompt/provider/normaliser path, but allow at most two bounded
# passes and return verified partial output instead of starting another cascade.
def _generate_quizzes_from_ocr_sync(ocr_ctx, desired, user_id):  # noqa: F811
    source = ""
    if isinstance(ocr_ctx, dict):
        source = str(ocr_ctx.get("clean_text") or ocr_ctx.get("raw_markdown") or "").strip()
    else:
        source = str(ocr_ctx or "").strip()
    if not source:
        raise RuntimeError("No readable OCR text found on this page.")
    try:
        wanted = max(1, min(200, int(desired or 1)))
    except Exception:
        wanted = 1
    batcher = globals().get("_generate_batch_fast_74")
    if not callable(batcher):
        raise RuntimeError("Quiz generator is unavailable.")

    rows = []
    seen = set()
    avoid = ""
    avoid_builder = globals().get("_source_avoid_text_74")
    if callable(avoid_builder):
        with _cx129.suppress(Exception):
            avoid = str(avoid_builder(ocr_ctx) or "")
    passes = 0
    while len(rows) < wanted and passes < 2:
        passes += 1
        need = min(8, wanted - len(rows))
        recent = "\n".join("- " + str(row.get("question") or "")[:140] for row in rows[-12:])
        generated = []
        with _cx129.suppress(Exception):
            generated = list(batcher(
                source, need, avoid_text=(avoid + "\n" + recent).strip(),
            ) or [])
        if not generated:
            continue
        for item in generated:
            if not isinstance(item, dict):
                continue
            question = str(item.get("question") or item.get("questions") or "").strip()
            options = item.get("options") if isinstance(item.get("options"), list) else []
            options = [str(option or "").strip() for option in options if str(option or "").strip()][:4]
            try:
                answer = int(item.get("answer") or 0)
            except Exception:
                answer = 0
            if not question or len(options) != 4 or not 1 <= answer <= 4:
                continue
            signature = _re129.sub(r"\W+", "", question.casefold())[:120]
            if not signature or signature in seen:
                continue
            # Provider output is checked here as well as before buffer insertion.
            if not _QX129_CALCULUS.search(source) and _QX129_CALCULUS.search(
                question + " " + str(item.get("explanation") or "")
            ):
                continue
            seen.add(signature)
            clean = dict(item)
            clean["question"] = question
            clean["options"] = options
            clean["answer"] = answer
            rows.append(clean)
            if len(rows) >= wanted:
                break
    if not rows:
        raise RuntimeError("Active AI providers returned no source-faithful quiz.")
    return rows[:wanted]


globals()["_generate_quizzes_from_ocr_sync"] = _generate_quizzes_from_ocr_sync


# ── 3) Live progress on the one existing generation card ─────────────────────
async def _qx129_progress(context, update, uid, done, wanted, mode, started):
    cards = globals().get("_QX95_LAST_GEN_CARD") or {}
    message = getattr(update, "effective_message", None)
    chat_id = int(getattr(message, "chat_id", 0) or 0)
    message_id = cards.get((chat_id, int(uid or 0)))
    if not chat_id or not message_id:
        return
    elapsed = max(0, int(_t129.time() - started))
    body = (
        f"Standard: <b>{str(mode or 'std').upper()}</b>\n"
        f"তৈরি হয়েছে: <b>{int(done)}</b> / <b>{int(wanted)}</b>\n"
        f"সময়: <code>{elapsed}s</code>\n\n"
        "🧠 Source মিলিয়ে quiz তৈরি ও যাচাই হচ্ছে…"
    )
    boxer = globals().get("ui_box_html")
    text = boxer("Generating Quiz", body, emoji="⏳") if callable(boxer) else body
    with _cx129.suppress(Exception):
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=int(message_id), text=text,
            parse_mode=ParseMode.HTML, disable_web_page_preview=True,  # type: ignore[name-defined]
        )


def _qx129_buffer_ids(uid):
    ids = set()
    with _cx129.suppress(Exception):
        for row_id, _payload in (buffer_list(int(uid), limit=99999) or []):  # type: ignore[name-defined]
            ids.add(int(row_id))
    return ids


def _qx129_remove_off_subject_calculus(uid, before_ids, source_text):
    """Hard guard: reject newly generated calculus absent from the source."""
    source = _qx129_source_only(source_text)
    if _QX129_CALCULUS.search(source):
        return 0
    rejected = []
    with _cx129.suppress(Exception):
        for row_id, payload in (buffer_list(int(uid), limit=99999) or []):  # type: ignore[name-defined]
            if int(row_id) in before_ids:
                continue
            candidate = " ".join((
                str((payload or {}).get("questions") or ""),
                str((payload or {}).get("explanation") or ""),
            ))
            if _QX129_CALCULUS.search(candidate):
                rejected.append(int(row_id))
    if rejected:
        with _cx129.suppress(Exception):
            buffer_remove_ids(int(uid), rejected)  # type: ignore[name-defined]
        _log129("rejected %s off-subject calculus row(s) for uid=%s" % (len(rejected), uid))
    return len(rejected)


# Use the proven pre-watchdog generator one bounded batch at a time. This makes
# real completed counts observable and prevents one 100-item call from appearing
# frozen. The final qx95 result card still replaces this card exactly as before.
_qx129_batch_generate = globals().get("_qx124_prev_gen_buffer")
if not callable(_qx129_batch_generate):
    _qx129_batch_generate = globals().get("_generate_to_buffer_59")

if callable(_qx129_batch_generate):
    async def _generate_to_buffer_59(update, context, ocr_ctx, uid, count,
                                     mode="std"):  # noqa: F811
        try:
            wanted = max(1, min(500, int(count or 20)))
        except Exception:
            wanted = 20
        started = _t129.time()
        added_total = 0
        dup_total = 0
        stalled = 0
        await _qx129_progress(context, update, uid, 0, wanted, mode, started)

        # Small batches improve provider latency and let every successful round
        # update the visible count. Stop safely after repeated zero-result rounds.
        while added_total < wanted and (_t129.time() - started) < 300:
            need = min(8, wanted - added_total)
            before_ids = _qx129_buffer_ids(uid)
            try:
                added, dup = await _a129.wait_for(
                    _qx129_batch_generate(update, context, ocr_ctx, uid, need, mode),
                    timeout=105.0,
                )
            except Exception as error:
                _log129("generation batch failed: %s" % str(error)[:160], "warning")
                added = dup = 0
            rejected = _qx129_remove_off_subject_calculus(
                uid, before_ids,
                (ocr_ctx or {}).get("clean_text") or (ocr_ctx or {}).get("raw_markdown")
                if isinstance(ocr_ctx, dict) else ocr_ctx,
            )
            added = max(0, int(added or 0) - int(rejected or 0))
            added_total += int(added or 0)
            dup_total += int(dup or 0)
            await _qx129_progress(
                context, update, uid, min(added_total, wanted), wanted, mode, started,
            )
            if int(added or 0) <= 0:
                stalled += 1
                if stalled >= 2:
                    break
            else:
                stalled = 0
        return added_total, dup_total

    globals()["_generate_to_buffer_59"] = _generate_to_buffer_59


# Printed-question harvest has an exact target after OCR splitting. Show it on
# the existing status card before conversion and the actual result afterward.
_qx129_prev_harvest = globals().get("_qxv_harvest")
if callable(_qx129_prev_harvest):
    async def _qxv_harvest(update, context, uid, source_text, status=None,
                           label="source"):  # noqa: F811
        expected = len(_qxm_split_questions(source_text))
        if status is not None and expected:
            with _cx129.suppress(Exception):
                await status.edit_text(
                    ui_box_html(
                        "Converting Questions",
                        f"শনাক্ত হয়েছে: <b>{expected}</b>\nতৈরি হয়েছে: <b>0</b> / <b>{expected}</b>\n\n"
                        "Source-এর প্রশ্ন ও সমাধান যাচাই হচ্ছে…",
                        emoji="🧠",
                    ),
                    parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                )
        added, dup, found = await _qx129_prev_harvest(
            update, context, uid, source_text, status, label,
        )
        if status is not None:
            target = expected or int(found or 0)
            with _cx129.suppress(Exception):
                await status.edit_text(
                    ui_box_html(
                        "Finalising Questions",
                        f"তৈরি হয়েছে: <b>{int(found or 0)}</b> / <b>{target}</b>\n"
                        f"Buffer-এ যোগ: <b>{int(added or 0)}</b>",
                        emoji="✅",
                    ),
                    parse_mode=ParseMode.HTML,  # type: ignore[name-defined]
                )
        return added, dup, found

    globals()["_qxv_harvest"] = _qxv_harvest


_log129("source-fidelity lock, arbitrary serial harvest and live generation progress active")