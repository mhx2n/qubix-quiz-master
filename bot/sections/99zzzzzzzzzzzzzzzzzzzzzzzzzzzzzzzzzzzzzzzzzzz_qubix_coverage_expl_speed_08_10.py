# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 133 (2026-08-10) — full-source coverage + clean explanations + speed
#
# Symptoms this fixes:
#   1) /model showed "Mistral quiz 500+" while only ~100 landed in the buffer:
#      every lane got the WHOLE page text, so all lanes wrote near-identical
#      MCQs and the dedupe pass threw most of them away. Wasted tokens = slow.
#   2) Coverage was uneven — one line produced 20-30 quizzes while whole
#      paragraphs/table rows were never touched.
#   3) Explanations leaked meta wording: "উৎস অনুযায়ী", "উৎস থেকে পাই",
#      "According to the source" etc.
#
# Fix: deterministic source segmentation with round-robin assignment per lane
# (each provider call sees a different slice of the same page, in order, so the
# text is swept start→end), plus wider lanes now that lanes no longer collide,
# plus a meta-phrase scrubber on every normalised MCQ explanation.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx133
import hashlib as _hs133
import re as _re133
import threading as _th133


def _log133(message, level="info"):
    with _cx133.suppress(Exception):
        getattr(logger, level)("[S133] %s", message)  # type: ignore[name-defined]


# ── 1. wider lanes (dedupe pressure is gone once slices differ) ───────────────
with _cx133.suppress(Exception):
    globals()["_QX131_LANES"] = 10
    globals()["_QX131_BATCH"] = 12
    globals()["_QX131_LANE_TIMEOUT"] = 60.0


# ── 2. explanation meta-phrase scrub ─────────────────────────────────────────
_QX133_META = [
    r"^\s*উৎস\s*থেকে\s*(পাই|জানা\s*যায়|পাওয়া\s*যায়|বোঝা\s*যায়)\s*[,:।\-–—]?\s*",
    r"^\s*উৎস\s*(অনুযায়ী|অনুসারে|মতে|থেকে)\s*[,:।\-–—]?\s*",
    r"^\s*উৎসে\s*(বলা|উল্লেখ|দেওয়া|দেয়া)\s*(আছে|হয়েছে)\s*(যে)?\s*[,:।\-–—]?\s*",
    r"^\s*উৎস\s*থেকে\s*(পাই|জানা\s*যায়|পাওয়া\s*যায়)\s*[,:।\-–—]?\s*",
    r"^\s*(প্রদত্ত|উপরোক্ত|প্রশ্নের)?\s*(সোর্স|সূত্র|টেক্সট|পাঠ্য|অনুচ্ছেদ)\s*(অনুযায়ী|অনুসারে|মতে|থেকে)\s*[,:।\-–—]?\s*",
    r"^\s*(as\s+per|according\s+to|based\s+on)\s+the\s+(source|text|passage|given\s+text)\s*[,:.\-–—]?\s*",
    r"^\s*(the\s+)?source\s+(says|states|mentions)\s*(that)?\s*[,:.\-–—]?\s*",
    r"^\s*ছবি(তে)?\s*(দেওয়া|দেয়া|উল্লেখ)?\s*(আছে|অনুযায়ী)\s*[,:।\-–—]?\s*",
]
_QX133_META_RX = [_re133.compile(p, _re133.IGNORECASE) for p in _QX133_META]
_QX133_INLINE_RX = _re133.compile(
    r"(উৎস|সোর্স)\s*(অনুযায়ী|অনুসারে|মতে|থেকে)\s*[,:।]?\s*", _re133.IGNORECASE)


def _qx133_clean_expl(text):
    out = str(text or "").strip()
    if not out:
        return out
    for _ in range(4):
        before = out
        for rx in _QX133_META_RX:
            out = rx.sub("", out).strip()
        if out == before:
            break
    out = _QX133_INLINE_RX.sub("", out).strip()
    out = _re133.sub(r"\s{2,}", " ", out).strip(" ,;:।-–—")
    if out and out[-1] not in "।.!?":
        out += "।" if _re133.search(r"[\u0980-\u09FF]", out) else "."
    return out


globals()["_qx133_clean_expl"] = _qx133_clean_expl

_qx133_prev_norm = globals().get("_normalise_mcq_74")
if callable(_qx133_prev_norm):

    def _normalise_mcq_74(item):  # noqa: F811
        good = _qx133_prev_norm(item)
        if isinstance(good, dict):
            for key in ("explanation", "expl", "why", "reason"):
                if isinstance(good.get(key), str) and good.get(key).strip():
                    with _cx133.suppress(Exception):
                        good[key] = _qx133_clean_expl(good[key])
        return good

    globals()["_normalise_mcq_74"] = _normalise_mcq_74
    _log133("explanation meta-phrase scrub active")


# ── 3. deterministic source segmentation (start → end sweep) ─────────────────
_QX133_MIN_SEG = 420      # chars — smaller slices starve the model
_QX133_MAX_SEG = 1500
_QX133_LOCK = _th133.Lock()
_QX133_CURSOR = {}


def _qx133_key(text):
    return _hs133.md5(str(text or "").encode("utf-8", "ignore")).hexdigest()[:16]


def _qx133_units(text):
    raw = str(text or "")
    units = [u.strip() for u in _re133.split(r"\n\s*\n|\n(?=[|\d১-৯])|\n", raw)]
    return [u for u in units if len(u) >= 12]


def _qx133_segments(text):
    raw = str(text or "")
    if len(raw) <= _QX133_MAX_SEG:
        return [raw]
    segments, buf = [], ""
    for unit in _qx133_units(raw):
        if len(unit) > _QX133_MAX_SEG:
            for start in range(0, len(unit), _QX133_MAX_SEG):
                piece = unit[start:start + _QX133_MAX_SEG]
                if buf:
                    segments.append(buf)
                    buf = ""
                segments.append(piece)
            continue
        if len(buf) + len(unit) + 1 <= _QX133_MAX_SEG:
            buf = (buf + "\n" + unit).strip()
        else:
            if len(buf) >= _QX133_MIN_SEG:
                segments.append(buf)
                buf = unit
            else:
                buf = (buf + "\n" + unit).strip()
    if buf:
        if segments and len(buf) < _QX133_MIN_SEG:
            segments[-1] = segments[-1] + "\n" + buf
        else:
            segments.append(buf)
    return segments or [raw]


def _qx133_slice(text):
    """Next segment for this source, round-robin, thread safe."""
    segments = _qx133_segments(text)
    if len(segments) <= 1:
        return str(text or ""), 1, 1
    key = _qx133_key(text)
    with _QX133_LOCK:
        index = int(_QX133_CURSOR.get(key, 0)) % len(segments)
        _QX133_CURSOR[key] = index + 1
        if len(_QX133_CURSOR) > 400:
            _QX133_CURSOR.clear()
            _QX133_CURSOR[key] = index + 1
    body = segments[index]
    # small overlap so a fact split across the seam is still answerable
    if index + 1 < len(segments):
        body = body + "\n" + segments[index + 1][:180]
    return body, index + 1, len(segments)


globals()["_qx133_slice"] = _qx133_slice


_qx133_prev_batch = globals().get("_generate_batch_fast_74")
if callable(_qx133_prev_batch):

    def _generate_batch_fast_74(source_text, need, *, easy=0, medium=0, hard=0,
                                avoid_text=""):  # noqa: F811
        body, part, total = source_text, 1, 1
        with _cx133.suppress(Exception):
            body, part, total = _qx133_slice(source_text)
        if total > 1:
            header = (
                "নিচের অংশ %d/%d — শুধুমাত্র এই অংশের তথ্য থেকেই প্রশ্ন করুন, "
                "এই অংশের সব বাক্য/টেবিল-সারি যেন প্রশ্নে উঠে আসে, "
                "একই বাক্য থেকে বারবার প্রশ্ন করবেন না।\n"
                "(Use ONLY this part; cover every line/table row of it once, "
                "never repeat the same fact.)\n\n" % (part, total)
            )
            body = header + body
        return _qx133_prev_batch(body, need, easy=easy, medium=medium, hard=hard,
                                 avoid_text=avoid_text)

    globals()["_generate_batch_fast_74"] = _generate_batch_fast_74
    _log133("source segmentation wired: each lane gets a distinct slice")


_log133("section 133 loaded (coverage + clean explanation + lane widening)")
