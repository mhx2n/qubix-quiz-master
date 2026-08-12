# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 143 (2026-08-12) — complete, self-contained explanations
#
# Problem: explanations arrived cut mid-sentence ("… ১ নিউটন × ১ ম") because
#   a) the provider stopped mid-token, and b) poll trimming sliced by raw char
#      count and appended "...".
#
# Fix: every explanation is now closed on a sentence boundary, never longer than
# 250 words, always ending with "।" (Bangla) or "." (Latin). Truncated bodies are
# rewritten in batch by AI (worker-thread only, same call path as S141), and the
# poll trimmer now cuts on the last complete clause instead of mid-word.
# No provider, command, storage or progress flow is changed.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx143
import re as _re143

_QX143_MAX_WORDS = 250
_QX143_END = "।.!?"
_QX143_SENT_RX = _re143.compile(r"[^।.!?\n]+[।.!?]+|[^।.!?\n]+$")
_QX143_BN_RX = _re143.compile(r"[\u0980-\u09FF]")
# a tail that clearly stops mid-thought (dangling connector / lone unit / "...")
_QX143_DANGLE = _re143.compile(
    r"(?:\.\.\.|…|[=+\-×÷/·]|\b(?:এবং|বা|যা|যার|কারণ|তাই|সুতরাং|অর্থাৎ|থেকে|হলো|হল|is|are|the|of|and|or|to|for)\s*)$",
    _re143.IGNORECASE,
)


def _qx143_log(message, level="info"):
    with _cx143.suppress(Exception):
        getattr(logger, level)("[S143] %s", message)  # type: ignore[name-defined]


def _qx143_terminator(text):
    return "।" if _QX143_BN_RX.search(str(text or "")) else "."


def _qx143_sentences(text):
    return [s.strip() for s in _QX143_SENT_RX.findall(str(text or "")) if s.strip()]


def _qx143_looks_truncated(text):
    body = str(text or "").strip()
    if not body:
        return True
    if body[-1] not in _QX143_END:
        return True
    return bool(_QX143_DANGLE.search(body.rstrip(_QX143_END).strip()))


globals()["_qx143_looks_truncated"] = _qx143_looks_truncated


def _qx143_complete(text, budget=None):
    """Close the explanation on a sentence boundary and punctuate it."""
    body = _re143.sub(r"\s{2,}", " ", str(text or "").replace("\r", " ")).strip()
    if not body:
        return ""
    words = body.split(" ")
    if len(words) > _QX143_MAX_WORDS:
        body = " ".join(words[:_QX143_MAX_WORDS])
    sentences = _qx143_sentences(body)
    if not sentences:
        return ""
    end = _qx143_terminator(body)
    kept, out = [], ""
    for sentence in sentences:
        candidate = (out + " " + sentence).strip() if out else sentence
        if budget and len(candidate) > budget and kept:
            break
        out, _ = candidate, kept.append(sentence)
    if not out:
        # single oversized sentence — cut on a word boundary, never mid-word
        limit = budget or 400
        out = sentences[0][:limit]
        if len(sentences[0]) > limit and " " in out:
            out = out[: out.rfind(" ")]
    # drop a trailing clause that stops mid-thought when something remains
    while len(kept) > 1 and _QX143_DANGLE.search(kept[-1].rstrip(_QX143_END).strip()):
        kept.pop()
        out = " ".join(kept).strip()
    out = out.strip(" ,;:-–—")
    if not out:
        return ""
    if out[-1] not in _QX143_END:
        out = _QX143_DANGLE.sub("", out).strip(" ,;:-–—")
        if not out:
            return ""
        out += end
    return out


globals()["_qx143_complete"] = _qx143_complete


# ═════════════════════════════════════════════════════════════════════════════
# 1) AI rewrite for truncated bodies (batched, worker-thread only)
# ═════════════════════════════════════════════════════════════════════════════
def _qx143_repair_rows(rows):
    fixed, needy = [], []
    for row in rows or []:
        if not isinstance(row, dict):
            fixed.append(row)
            continue
        item = dict(row)
        with _cx143.suppress(Exception):
            body = _qx143_complete(item.get("explanation"))
            if body and not _qx143_looks_truncated(body):
                item["explanation"] = body
            else:
                item["explanation"] = ""
                needy.append((len(fixed), item))
        fixed.append(item)
    if needy:
        writer = globals().get("_qx141_ai_explain")
        if callable(writer):
            with _cx143.suppress(Exception):
                writer(needy)
        for _, item in needy:
            with _cx143.suppress(Exception):
                item["explanation"] = _qx143_complete(item.get("explanation"))
    return fixed


globals()["_qx143_repair_rows"] = _qx143_repair_rows

# a) verbatim AI extraction
_qx143_prev_extract = globals().get("_qxv_extract_sync")
if callable(_qx143_prev_extract):
    def _qxv_extract_sync(source_text, lang="bn"):  # noqa: F811
        return _qx143_repair_rows(_qx143_prev_extract(source_text, lang) or [])

    globals()["_qxv_extract_sync"] = _qxv_extract_sync

# b) deterministic OCR parse path
_qx143_prev_local = globals().get("_qx139_local_rows")
if callable(_qx143_prev_local):
    def _qx139_local_rows(chunk):  # noqa: F811
        return _qx143_repair_rows(_qx143_prev_local(chunk) or [])

    globals()["_qx139_local_rows"] = _qx139_local_rows


# ═════════════════════════════════════════════════════════════════════════════
# 2) Generation path — close the sentence, no blocking call
# ═════════════════════════════════════════════════════════════════════════════
_qx143_prev_norm = globals().get("_normalise_mcq_74")
if callable(_qx143_prev_norm):
    def _normalise_mcq_74(item):  # noqa: F811
        good = _qx143_prev_norm(item)
        if isinstance(good, dict):
            for key in ("explanation", "expl", "why", "reason", "solution"):
                value = good.get(key)
                if isinstance(value, str) and value.strip():
                    with _cx143.suppress(Exception):
                        good[key] = _qx143_complete(value)
        return good

    globals()["_normalise_mcq_74"] = _normalise_mcq_74


# ═════════════════════════════════════════════════════════════════════════════
# 3) Poll payloads and poll trimming — cut on clauses, keep the owner link
# ═════════════════════════════════════════════════════════════════════════════
_qx143_prev_sanitize = globals().get("_sanitize_item_for_poll")


def _sanitize_item_for_poll(item):  # noqa: F811
    payload = dict(item or {})
    if callable(_qx143_prev_sanitize):
        with _cx143.suppress(Exception):
            payload = dict(_qx143_prev_sanitize(payload) or payload)
    with _cx143.suppress(Exception):
        body = payload.get("explanation")
        if isinstance(body, str) and body.strip():
            payload["explanation"] = _qx143_complete(body)
    return payload


globals()["_sanitize_item_for_poll"] = _sanitize_item_for_poll

_QX143_BUDGET = 195
_qx143_prev_trim = globals().get("_trim_expl_for_poll")


def _trim_expl_for_poll(expl, link=""):  # noqa: F811
    body = str(expl or "")
    tail = str(link or "").strip()
    if callable(_qx143_prev_trim):
        with _cx143.suppress(Exception):
            body = str(_qx143_prev_trim(body, "") or body)
    body = body.strip()
    if tail and body.endswith(tail):
        body = body[: -len(tail)].strip()
    room = _QX143_BUDGET - (len(tail) + 1 if tail else 0)
    if room < 12:
        return tail[:_QX143_BUDGET] if tail else body[:_QX143_BUDGET]
    body = _qx143_complete(body, budget=room)
    if len(body) > room:
        body = _qx143_complete(body[:room], budget=room)
    if not tail:
        return body
    return (body + "\n" + tail).strip() if body else tail


globals()["_trim_expl_for_poll"] = _trim_expl_for_poll

_qx143_log("complete-explanation pass active (sentence-safe, <=250 words)")
