# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 141 (2026-08-11) — junk-free explanations + preserved source tags
#
# 1) OCR sometimes drags unrelated page furniture into an explanation, e.g.
#    "[LOGO] লেকেন্ড টাইমারদের আপকামিং ব্যাচ 'প্রত্যাবর্তন ৫.০' ১৭ [LOGO] ...".
#    Such text is now dropped, and a fresh explanation is written by AI from the
#    question plus the correct option (batched, inside the worker thread only).
# 2) Source credits in brackets — [BUET], [DU], [GST], [MAT: 13-14],
#    [আলীম স্যার] — are preserved and placed neatly at the end of the question.
#
# No provider, command, storage or progress flow is changed.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx141
import json as _js141
import re as _re141


def _qx141_log(message, level="info"):
    with _cx141.suppress(Exception):
        getattr(logger, level)("[S141] %s", message)  # type: ignore[name-defined]


# ═════════════════════════════════════════════════════════════════════════════
# 1) Source tag handling on question stems
# ═════════════════════════════════════════════════════════════════════════════
_QX141_BRACKET = _re141.compile(r"[\[【]\s*([^\[\]【】\n]{1,60}?)\s*[\]】]")
_QX141_JUNK_TAG = _re141.compile(
    r"^(?:logo|img|image|photo|icon|qr|figure|fig|text|table|blank|"
    r"watermark|ad|advert)[\s:._-]*",
    _re141.IGNORECASE,
)
_QX141_TAGWORTHY = _re141.compile(
    r"(?:স্যার|ম্যাডাম|sir|madam|BUET|CUET|KUET|RUET|DU|RU|JU|CU|SUST|GST|MAT|"
    r"DAT|BUP|IUT|MBBS|BDS|MED|DENT|VET|AFMC|উত্তর\s*বোর্ড|বোর্ড|"
    r"[0-9০-৯]{2,4}\s*[-–]\s*[0-9০-৯]{2,4}|[0-9০-৯]{4})",
    _re141.IGNORECASE,
)


def _qx141_tag_kind(inner):
    body = str(inner or "").strip()
    if not body:
        return "drop"
    if _QX141_JUNK_TAG.match(body):
        return "drop"
    if _QX141_TAGWORTHY.search(body) or (len(body) <= 28 and body.upper() == body and body.isascii()):
        return "keep"
    return "inline"


def _qx141_fix_question(value):
    """Drop page furniture, keep exam/author credits, park them at the end."""
    text = str(value or "").strip()
    if not text:
        return text
    tags = []

    def replace(match):
        inner = match.group(1).strip()
        kind = _qx141_tag_kind(inner)
        if kind == "drop":
            return " "
        if kind == "keep":
            label = "[%s]" % inner
            if label not in tags:
                tags.append(label)
            return " "
        return match.group(0)

    body = _QX141_BRACKET.sub(replace, text)
    body = _re141.sub(r"[ \t]{2,}", " ", body).strip(" \t-–—")
    if not body:
        body = text.strip()
        tags = []
    if tags:
        body = "%s %s" % (body.rstrip(), " ".join(tags))
    return body.strip()


globals()["_qx141_fix_question"] = _qx141_fix_question


# ═════════════════════════════════════════════════════════════════════════════
# 2) Junk explanation detection
# ═════════════════════════════════════════════════════════════════════════════
_QX141_NOISE = _re141.compile(
    r"(?:\[\s*(?:logo|img|image|text|table|figure)[^\]]*\]|https?://|www\.|"
    r"ব্যাচ|কোচিং|ভর্তি\s*চলছে|আপকামিং|ক্যাম্পাস|হান্টার্স|টাইমার|"
    r"বিজ্ঞাপন|যোগাযোগ|মোবাইল|হটলাইন|ফেসবুক|facebook|telegram|whatsapp)",
    _re141.IGNORECASE,
)
_QX141_WORD = _re141.compile(r"[^\W\d_]{2,}", _re141.UNICODE)


def _qx141_tokens(text):
    return {w.casefold() for w in _QX141_WORD.findall(str(text or ""))}


def _qx141_is_junk_expl(expl, question="", options=()):
    body = str(expl or "").strip()
    if not body:
        return True
    if len(body) < 6:
        return True
    if _QX141_NOISE.search(body):
        return True
    if len(_QX141_BRACKET.findall(body)) >= 2:
        return True
    context = _qx141_tokens(question) | _qx141_tokens(" ".join(str(o or "") for o in options or ()))
    words = _qx141_tokens(body)
    if len(body) > 40 and words and context and not (words & context):
        return True
    return False


globals()["_qx141_is_junk_expl"] = _qx141_is_junk_expl


# ═════════════════════════════════════════════════════════════════════════════
# 3) AI rewrite for missing/junk explanations (sync, worker-thread only)
# ═════════════════════════════════════════════════════════════════════════════
def _qx141_opts(row):
    options = row.get("options")
    if isinstance(options, (list, tuple)):
        return [str(o or "").strip() for o in options]
    return [str(row.get("option%d" % i) or "").strip() for i in range(1, 5)]


def _qx141_ai_explain(rows):
    caller = globals().get("_qxv_ai_raw")
    if not callable(caller) or not rows:
        return
    payload = []
    for index, row in rows:
        options = _qx141_opts(row)
        answer = int(row.get("answer") or 0)
        if not (1 <= answer <= len(options)):
            continue
        payload.append({
            "idx": index,
            "q": str(row.get("question") or row.get("questions") or "")[:400],
            "correct": options[answer - 1][:120],
        })
    if not payload:
        return
    prompt = (
        "Return STRICT JSON only. For each MCQ write a short factual explanation "
        "(max 2 sentences) justifying the given correct option, in the same language "
        "as the question. Never print the option letter, never mention the source, "
        "never add promotional or coaching text.\n"
        'JSON: {"items":[{"idx":0,"explanation":"..."}]}\n\n'
        "MCQS:\n%s" % _js141.dumps(payload, ensure_ascii=False)
    )
    raw = None
    with _cx141.suppress(Exception):
        raw = caller(prompt, timeout=40)
    if not raw:
        return
    data = None
    parser = globals().get("_extract_json_strict")
    if callable(parser):
        with _cx141.suppress(Exception):
            data = parser(raw)
    if not isinstance(data, dict):
        with _cx141.suppress(Exception):
            data = _js141.loads(raw)
    if not isinstance(data, dict):
        return
    by_index = {index: row for index, row in rows}
    purifier = globals().get("_qx140_pure_expl")
    for item in data.get("items") or []:
        with _cx141.suppress(Exception):
            row = by_index.get(int(item.get("idx")))
            text = str(item.get("explanation") or "").strip()
            if callable(purifier):
                text = str(purifier(text) or text)
            if row is not None and text and not _qx141_is_junk_expl(text, row.get("question"), _qx141_opts(row)):
                row["explanation"] = text


def _qx141_repair_rows(rows):
    """Fix question tags, drop junk explanations, then batch-fill by AI."""
    fixed, needy = [], []
    for row in rows or []:
        if not isinstance(row, dict):
            fixed.append(row)
            continue
        item = dict(row)
        with _cx141.suppress(Exception):
            stem = _qx141_fix_question(item.get("question") or item.get("questions"))
            if stem:
                if "question" in item or "questions" not in item:
                    item["question"] = stem
                if "questions" in item:
                    item["questions"] = stem
        with _cx141.suppress(Exception):
            if _qx141_is_junk_expl(item.get("explanation"), item.get("question") or item.get("questions"), _qx141_opts(item)):
                item["explanation"] = ""
                needy.append((len(fixed), item))
        fixed.append(item)
    if needy:
        with _cx141.suppress(Exception):
            _qx141_ai_explain(needy)
    return fixed


globals()["_qx141_repair_rows"] = _qx141_repair_rows


# a) verbatim AI extraction (already runs in a worker thread)
_qx141_prev_extract = globals().get("_qxv_extract_sync")
if callable(_qx141_prev_extract):
    def _qxv_extract_sync(source_text, lang="bn"):  # noqa: F811
        return _qx141_repair_rows(_qx141_prev_extract(source_text, lang) or [])

    globals()["_qxv_extract_sync"] = _qxv_extract_sync

# b) deterministic OCR parse path (also a worker thread)
_qx141_prev_local = globals().get("_qx139_local_rows")
if callable(_qx141_prev_local):
    def _qx139_local_rows(chunk):  # noqa: F811
        return _qx141_repair_rows(_qx141_prev_local(chunk) or [])

    globals()["_qx139_local_rows"] = _qx139_local_rows

# c) generation path — tags kept, junk explanations blanked (no blocking call)
_qx141_prev_norm = globals().get("_normalise_mcq_74")
if callable(_qx141_prev_norm):
    def _normalise_mcq_74(item):  # noqa: F811
        good = _qx141_prev_norm(item)
        if isinstance(good, dict):
            with _cx141.suppress(Exception):
                stem = _qx141_fix_question(good.get("questions") or good.get("question"))
                if stem:
                    if good.get("questions"):
                        good["questions"] = stem
                    if good.get("question"):
                        good["question"] = stem
            with _cx141.suppress(Exception):
                if _qx141_is_junk_expl(good.get("explanation"), good.get("questions") or good.get("question"), _qx141_opts(good)):
                    good["explanation"] = ""
        return good

    globals()["_normalise_mcq_74"] = _normalise_mcq_74

# d) poll payloads — last gate before Telegram
_qx141_prev_sanitize = globals().get("_sanitize_item_for_poll")


def _sanitize_item_for_poll(item):  # noqa: F811
    payload = dict(item or {})
    if callable(_qx141_prev_sanitize):
        with _cx141.suppress(Exception):
            payload = dict(_qx141_prev_sanitize(payload) or payload)
    with _cx141.suppress(Exception):
        stem = _qx141_fix_question(payload.get("questions") or payload.get("question"))
        if stem:
            payload["questions"] = stem
    with _cx141.suppress(Exception):
        if _qx141_is_junk_expl(payload.get("explanation"), payload.get("questions"), _qx141_opts(payload)):
            payload["explanation"] = ""
    return payload


globals()["_sanitize_item_for_poll"] = _sanitize_item_for_poll

_qx141_log("junk-free explanations with AI backfill and preserved source tags active")
