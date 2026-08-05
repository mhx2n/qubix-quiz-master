# ──────────────────────────────────────────────────────────────────────────────
# Section 125 (2026-08-05) — Source-subject lock; stop math leaking into prose
#
# Section 88 appends a language instruction containing the literal token
# "$...$" to OCR text.  Section 123's broad math detector treated any dollar
# sign as proof that the SOURCE was mathematics, so biography/literature topics
# received the mathematics-generation prompt.  Keep every existing generation
# flow intact and replace only that classification decision.
#
# DO NOT import directly — exec'd in the shared namespace by bot/__main__.py.
# ──────────────────────────────────────────────────────────────────────────────

import contextlib as _cx125
import re as _re125


def _log125(message: str) -> None:
    with _cx125.suppress(Exception):
        logger.info("[S125] %s", message)  # type: ignore[name-defined]


_QX125_INSTRUCTION_MARKERS = (
    "\n\nFINAL QUIZ LANGUAGE:",
    "\n\nHARD OUTPUT RULES:",
    "\n\nCRITICAL OUTPUT INTEGRITY:",
)

_QX125_MATH_TOPIC = _re125.compile(
    r"(?:\b(?:math|mathematics|algebra|geometry|trigonometry|calculus|derivative|"
    r"differentiation|integration|limit|equation|polynomial|matrix|vector|"
    r"logarithm|arithmetic|mensuration|statistics|probability)\b|"
    r"গণিত|ম্যাথ|বীজগণিত|জ্যামিতি|ত্রিকোণমিতি|ক্যালকুলাস|অন্তরকরণ|সমাকলন|"
    r"লিমিট|সীমা নির্ণয়|সমীকরণ|বহুপদী|ম্যাট্রিক্স|ভেক্টর|লগারিদম|পরিমিতি|"
    r"পরিসংখ্যান|সম্ভাবনা)",
    _re125.IGNORECASE,
)

_QX125_STRONG_FORMULA = _re125.compile(
    r"(?:\\(?:frac|int|sqrt|sin|cos|tan|lim|log|sum)\b|"
    r"[√∫∑∞≤≥≠±×÷]|"
    r"(?:^|\s)(?:lim|sin|cos|tan|log)\s*[_({]|"
    r"[A-Za-z0-9০-৯)\]}]\s*\^\s*[-+A-Za-z0-9০-৯{(]|"
    r"[A-Za-z]\s*[²³⁴⁵⁶⁷⁸⁹]|"
    r"(?:[A-Za-z]|[0-9০-৯]+)\s*[+−*/×÷]\s*(?:[A-Za-z]|[0-9০-৯]+)\s*=|"
    r"(?:[A-Za-z]\s*)?\d*\s*[xX]\s*[²³^]|"
    r"\b(?:d[xy]/d[xy]|dy/dx|dx/dy)\b)",
    _re125.IGNORECASE | _re125.MULTILINE,
)

_QX125_EQUATION = _re125.compile(
    r"(?:^|[\s,(])(?:[A-Za-z][A-Za-z0-9_]*|[0-9০-৯]+(?:\.[0-9০-৯]+)?)\s*"
    r"=\s*[-+()A-Za-z0-9০-৯√]",
    _re125.MULTILINE,
)


def _qx125_source_only(value) -> str:
    """Remove instructions injected by older wrappers before classification."""
    text = str(value or "")
    cut = len(text)
    for marker in _QX125_INSTRUCTION_MARKERS:
        pos = text.find(marker)
        if pos >= 0:
            cut = min(cut, pos)
    return text[:cut].strip()


def _qx_is_mathy(text: str) -> bool:  # noqa: F811
    """True only when the user's source itself contains real math evidence."""
    source = _qx125_source_only(text)
    if not source:
        return False
    if _QX125_MATH_TOPIC.search(source):
        return True
    if _QX125_STRONG_FORMULA.search(source):
        return True
    # A plain '=' is useful evidence only as an actual compact equation.  Years,
    # biography dates, list serials and the language-lock's `$...$` are not math.
    return bool(_QX125_EQUATION.search(source))


globals()["_qx_is_mathy"] = _qx_is_mathy
globals()["_qx125_source_only"] = _qx125_source_only


_qx125_prev_prompt = globals().get("_make_fast_new_mcq_prompt_74")

if callable(_qx125_prev_prompt):
    def _make_fast_new_mcq_prompt_74(source_text, n, *, easy=0, medium=0, hard=0,
                                     avoid_text=""):  # noqa: F811
        prompt = str(_qx125_prev_prompt(
            source_text, n, easy=easy, medium=medium, hard=hard,
            avoid_text=avoid_text,
        ) or "")
        source = _qx125_source_only(source_text)
        if not _qx_is_mathy(source):
            prompt += (
                "\n\nSOURCE-SUBJECT LOCK (MANDATORY):\n"
                "- This source is NOT mathematics. Create questions only from the "
                "facts, people, works, terms and concepts actually present in this source.\n"
                "- Never invent equations, variables, limits, algebra, arithmetic puzzles, "
                "date-difference calculations, or hybrid math questions from names/years.\n"
                "- Do not combine a source fact with an unrelated mathematical problem."
            )
        return prompt

    globals()["_make_fast_new_mcq_prompt_74"] = _make_fast_new_mcq_prompt_74


_log125("source-only math classifier active; non-math topics are subject-locked")