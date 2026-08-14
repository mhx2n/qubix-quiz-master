# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 147 (2026-08-14) — keep 5-option MCQs intact end-to-end
#
# Question banks (SUST/HSTU/admission) often print FIVE options (a–e / ক–ঙ).
# Every delivery layer already supports them — buffer stores option1..option5,
# quiz_to_poll_parts keeps up to 10, Telegram quizzes allow 2–10 — but five
# intake gates silently destroyed the 5th option:
#   1. _qxv_prompt told the AI "exactly 4 options, answer 1-4", so the model
#      itself dropped the 5th option while digitising the page.
#   2. _qxv_row truncated options[:4] and clamped the answer to 4.
#   3. _qxz_finalise trimmed >4 options back to 4.
#   4. _QXV_LETTERS had no e/ঙ/v mapping, so a printed "উত্তর: (e)" could
#      never resolve to option 5.
#   5. _qx135_payload (.gen → buffer) rejected anything but exactly 4 options
#      and always wrote option5="".
# This overlay widens only those gates to 4–5 options (correct-swap trim above
# 5). Harvest lanes, retries, live cards, cancel button, CSV import/export,
# posting, practice, scoring and tenant isolation stay byte-identical.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx147
import re as _re147

_QX147_MAX_OPTIONS = 5  # buffer/CSV schema holds option1..option5


def _qx147_log(message, *args):
    with _cx147.suppress(Exception):
        text = str(message)
        if args:
            try:
                text = text % args
            except Exception:
                text = "%s %s" % (text, " ".join(str(a) for a in args))
        logger.info("[S147] %s", text)  # type: ignore[name-defined]


# ── 1) answer letters: e / ঙ / v must resolve to option 5 ────────────────────
_letters147 = globals().get("_QXV_LETTERS")
if isinstance(_letters147, dict):
    _letters147.update({"e": 5, "ঙ": 5, "v": 5})


def _qx147_trim(options, answer):
    """Keep at most 5 options, never losing the correct one."""
    options = list(options or [])
    if len(options) <= _QX147_MAX_OPTIONS:
        return options, answer
    correct = options[answer - 1] if 1 <= answer <= len(options) else None
    trimmed = options[:_QX147_MAX_OPTIONS]
    if correct is not None and correct not in trimmed:
        trimmed[_QX147_MAX_OPTIONS - 1] = correct
    if correct is not None and correct in trimmed:
        answer = trimmed.index(correct) + 1
    else:
        answer = 1
    return trimmed, answer


# ── 2) extraction prompt: copy ALL printed options, answer 1-5 ───────────────
def _qxv_prompt(chunk, lang):  # noqa: F811
    language = (
        "Question, options and explanation must be natural Bangla (keep English technical terms)."
        if lang == "bn"
        else "Question, options and explanation must be in English."
    )
    return (
        "You are an exam digitiser. Return STRICT JSON only, no markdown.\n"
        "TASK: extract EVERY multiple-choice question from the source, in printed order.\n"
        "RULES:\n"
        "1. Copy the question stem and ALL printed options exactly as printed (fix only OCR "
        "noise). Remove A/B/C/D/E or ক/খ/গ/ঘ/ঙ labels from option text.\n"
        "2. The options array must contain EVERY printed option — usually 4, but MANY questions "
        "print 5 (a–e / ক–ঙ). NEVER drop, merge or invent options: 5 printed options → exactly "
        "5 entries, 4 printed → exactly 4. Only when the page prints fewer than 4 options, add "
        "plausible distractors to reach 4.\n"
        "3. If the page already marks the correct answer (tick/bold/উত্তর), use that answer. "
        "Otherwise solve it yourself; never guess randomly.\n"
        "4. explanation: 1-3 short sentences justifying ONLY the correct option. NEVER mention "
        "option letters, 'correct answer is', 'উত্তর', 'ব্যাখ্যা' or restate the option text.\n"
        "5. Keep numbers/units complete (5.04, not 04 or 5); keep math notation as plain text.\n"
        f"6. {language}\n"
        "7. answer is an integer 1-5 pointing at the correct option (use 5 when the 5th printed "
        "option is correct).\n"
        'FORMAT: {"items":[{"question":"...","options":["..","..","..",".."],"answer":2,'
        '"explanation":"..."}]} — the options array has 4 OR 5 entries, exactly as printed.\n\n'
        "SOURCE:\n" + str(chunk or "")
    )


globals()["_qxv_prompt"] = _qxv_prompt


# ── 3) row builder: keep up to 5 options, resolve the answer BEFORE trimming ─
def _qxv_row(item):  # noqa: F811
    if not isinstance(item, dict):
        return None
    question = str(item.get("question") or item.get("questions") or "").strip()
    raw_options = item.get("options")
    if isinstance(raw_options, dict):
        raw_options = list(raw_options.values())
    if not raw_options:
        raw_options = [item.get("option%d" % i) for i in range(1, 7)]
    cleaner = globals().get("_qx107_clean_math_text")
    options = []
    for option in (raw_options or []):
        text = str(option or "").strip()
        if not text:
            continue
        if callable(cleaner):
            with _cx147.suppress(Exception):
                text = str(cleaner(text, option=True) or text).strip()
        if text:
            options.append(text)
    if not question or len(options) < 2:
        return None
    resolver = globals().get("_qxv_answer_index")
    answer = 0
    if callable(resolver):
        with _cx147.suppress(Exception):
            answer = int(resolver(item, options) or 0)
    if not answer:
        answer = 1
    options, answer = _qx147_trim(options, answer)
    row = {
        "question": question,
        "options": options,
        "answer": max(1, min(len(options), int(answer))),
        "explanation": str(item.get("explanation") or item.get("solution") or "").strip(),
    }
    finaliser = globals().get("_qxz_finalise")
    if callable(finaliser):
        with _cx147.suppress(Exception):
            return finaliser(dict(row), allow_repair=True)
    return row


globals()["_qxv_row"] = _qxv_row


# ── 4) final gate: pad <4 (repair), trim >5 keeping the correct option ───────
def _qxz_finalise(row, *, allow_repair=False):  # noqa: F811
    if not isinstance(row, dict):
        return None
    options = [str(o or "").strip() for o in (row.get("options") or []) if str(o or "").strip()]
    unique, seen = [], set()
    for option in options:
        key = _re147.sub(r"\s+", "", option).casefold()
        if key and key not in seen:
            seen.add(key)
            unique.append(option)
    row["options"] = unique
    if len(unique) < 4:
        if not allow_repair:
            return None
        padder = globals().get("_qxz_pad_options")
        if not callable(padder):
            return None
        with _cx147.suppress(Exception):
            row = padder(row)
        if not isinstance(row, dict):
            return None
        unique = list(row.get("options") or [])
    answer = int(row.get("answer") or 1)
    if len(unique) > _QX147_MAX_OPTIONS:
        trimmed, answer = _qx147_trim(unique, answer)
        row["options"] = trimmed
        row["answer"] = answer
    elif not (1 <= answer <= len(unique)):
        row["answer"] = 1
    reconciler = globals().get("_qxz_reconcile_answer")
    if callable(reconciler):
        with _cx147.suppress(Exception):
            return reconciler(row)
    return row


globals()["_qxz_finalise"] = _qxz_finalise


# ── 5) deterministic local parse: recover the 5-option rows it used to skip ──
_qx147_prev_local = globals().get("_qx139_local_rows")


def _qx147_signature(row):
    signer = globals().get("_qx139_signature")
    if callable(signer):
        with _cx147.suppress(Exception):
            return str(signer(row) or "")
    question = str((row or {}).get("question") or (row or {}).get("questions") or "")
    return _re147.sub(r"\W+", "", question.casefold())[:140]


def _qx139_local_rows(chunk):  # noqa: F811
    rows = []
    if callable(_qx147_prev_local):
        with _cx147.suppress(Exception):
            rows = list(_qx147_prev_local(chunk) or [])
    # The legacy parser only accepted exactly-4-option items; add the 5-option
    # ones it skipped so they never reach the AI unnecessarily. Strictly
    # additive: previous rows and their order stay untouched.
    parser = globals().get("_extract_mcq_items_master")
    row_builder = globals().get("_qxv_row")
    if not (callable(parser) and callable(row_builder)):
        return rows
    seen = set()
    for row in rows:
        signature = _qx147_signature(row)
        if signature:
            seen.add(signature)
    extra = []
    with _cx147.suppress(Exception):
        for item in parser(chunk) or []:
            options = [str((item or {}).get("option%d" % i) or "").strip() for i in range(1, 7)]
            options = [o for o in options if o]
            if len(options) < 5:
                continue  # 4-option items were already handled above
            answer = 0
            with _cx147.suppress(Exception):
                answer = int((item or {}).get("answer") or 0)
            candidate = {
                "question": (item or {}).get("questions") or (item or {}).get("question"),
                "options": options,
                "answer": answer,
                "explanation": (item or {}).get("explanation") or "",
            }
            row = None
            with _cx147.suppress(Exception):
                row = row_builder(candidate)
            if not row:
                continue
            cleaner = globals().get("_qx139_clean_row")
            if callable(cleaner):
                with _cx147.suppress(Exception):
                    row = cleaner(row)
            if not row:
                continue
            signature = _qx147_signature(row)
            if signature and signature in seen:
                continue
            if signature:
                seen.add(signature)
            extra.append(row)
    if extra:
        repairer = globals().get("_qx143_repair_rows")
        if callable(repairer):
            with _cx147.suppress(Exception):
                extra = list(repairer(extra) or extra)
        rows = rows + extra
    return rows


globals()["_qx139_local_rows"] = _qx139_local_rows


# ── 6) .gen → buffer payload: accept 4–5 options instead of exactly 4 ────────
def _qx135_payload(raw, mode):  # noqa: F811
    if not isinstance(raw, dict):
        return None
    question = str(raw.get("question") or raw.get("questions") or "").strip()
    options = raw.get("options") if isinstance(raw.get("options"), list) else []
    if not options:
        option_reader = globals().get("_opts_59")
        if callable(option_reader):
            with _cx147.suppress(Exception):
                options = list(option_reader(raw) or [])
    options = [str(value or "").strip() for value in options if str(value or "").strip()]
    try:
        answer = int(raw.get("answer") or 0)
    except Exception:
        answer = 0
    options, answer = _qx147_trim(options, answer)
    if not question or len(options) < 4 or not 1 <= answer <= len(options):
        return None
    payload = {
        "questions": question,
        "answer": answer,
        "explanation": str(raw.get("explanation") or "").strip()[:700],
        "type": 1,
        "section": 1,
        "source": "gen_%s" % str(mode or "std"),
    }
    for index in range(5):
        payload["option%d" % (index + 1)] = options[index] if index < len(options) else ""
    parity = globals().get("_enforce_option_parity")
    if callable(parity):
        with _cx147.suppress(Exception):
            payload = parity(payload) or payload
    cleaner = globals().get("_qx133_clean_expl")
    if callable(cleaner):
        with _cx147.suppress(Exception):
            payload["explanation"] = cleaner(payload.get("explanation") or "")
    return payload


globals()["_qx135_payload"] = _qx135_payload

_qx147_log("5-option fidelity active: prompt/row/finalise/local/gen gates keep a–e (ক–ঙ)")