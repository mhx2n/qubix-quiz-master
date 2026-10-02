# -*- coding: utf-8 -*-
# ──────────────────────────────────────────────────────────────────────────────
# Section 150 (2026-10-02) — stop math renderers from eating plain English words
#
# Several LaTeX→Unicode engines (sections 55/66/68/79) accept macros WITHOUT a
# backslash, so ordinary words in CSV / quiz text were rewritten:
#   "to" → "→", "in" → "∈", "therefore" → "∴", "because" → "∵", "le" → "≤" ...
# This overlay guards every such renderer IN PLACE (code swap, so even
# references captured by earlier sections are covered): bare collision words
# are shielded with private placeholders before conversion and restored after.
# Real LaTeX (\in, \to, \therefore ...) still converts. Nothing else changes.
# ──────────────────────────────────────────────────────────────────────────────

import re as _re150
import types as _types150
import contextlib as _cx150

_QX150_WORDS = (
    "in", "to", "therefore", "because", "le", "ge", "ne", "ni", "mu", "nu",
    "pi", "eta", "xi", "ll", "gg", "int", "sum", "prod", "cup", "cap", "dot",
    "bar", "hat", "vec", "sim", "deg", "degree", "circ", "times", "div",
    "dots", "ldots", "cdots", "vdots", "quad", "qquad", "iff", "implies",
    "exists", "forall", "angle", "triangle", "parallel", "star", "prime",
    "ast", "perp", "ell", "subset", "supset", "notin", "approx", "equiv",
    "left", "right", "text", "overline", "underline", "tilde", "partial",
    "emptyset", "propto", "infinity", "to", "mp", "pm", "cdot", "neq", "leq",
    "geq", "limits", "rightarrow", "leftarrow", "nabla", "hbar", "frac",
    "sqrt", "widehat", "chi", "tau", "rho", "phi", "psi", "beta", "delta",
    "gamma", "sigma", "omega", "theta", "alpha", "lambda", "kappa", "zeta",
    "epsilon", "iota", "upsilon", "infty", "bf", "it", "rm",
)
_QX150_RE = _re150.compile(
    r"(?<![\\A-Za-z])(" + "|".join(sorted(set(_QX150_WORDS), key=len, reverse=True)) + r")(?![A-Za-z])"
)
_QX150_MATHY = _re150.compile(r"[=^_+×÷/<>≤≥√]|\d\s*[a-z]\b|\b[a-z]\s*\d")


def _qx150_protect(text):
    tokens = []

    def _sub(m):
        word = m.group(1)
        # Keep Greek/operator conversion for genuinely math-looking text where
        # upstream scrubbers dropped the backslash (e.g. "sin theta = 0.5").
        # Collision English words are ALWAYS protected.
        if word not in _QX150_ALWAYS:
            start, end = m.start(), m.end()
            window = text[max(0, start - 12):end + 12]
            if _QX150_MATHY.search(window):
                return word
        if len(tokens) >= 2000:
            return word
        tokens.append(word)
        return "\ue150" + chr(0xE200 + len(tokens) - 1)

    return _QX150_RE.sub(_sub, text), tokens


_QX150_ALWAYS = {
    "in", "to", "therefore", "because", "le", "ge", "ne", "ni", "ll", "gg",
    "int", "sum", "prod", "cup", "cap", "dot", "bar", "hat", "sim", "deg",
    "degree", "times", "div", "dots", "quad", "iff", "implies", "exists",
    "angle", "triangle", "parallel", "star", "prime", "ast", "subset",
    "left", "right", "text", "overline", "underline", "tilde", "partial",
    "infinity", "limits", "it", "bf", "rm", "beta", "delta", "gamma", "sigma",
    "omega", "alpha", "lambda", "chi", "eta", "nu", "mu", "pi", "xi",
}


def _qx150_restore(text, tokens):
    if not tokens or not isinstance(text, str):
        return text

    def _back(m):
        i = ord(m.group(1)) - 0xE200
        return tokens[i] if 0 <= i < len(tokens) else ""

    return _re150.sub("\ue150([\ue200-\ue9ff])", _back, text)


_QX150_ORIG = globals().setdefault("_QX150_ORIG", {})


def _qx150_call(key, args, kwargs):
    orig = _QX150_ORIG[key]
    if not args or not isinstance(args[0], str) or not args[0]:
        return orig(*args, **kwargs)
    try:
        guarded, tokens = _qx150_protect(args[0])
    except Exception:
        return orig(*args, **kwargs)
    if not tokens:
        return orig(*args, **kwargs)
    out = orig(guarded, *args[1:], **kwargs)
    return _qx150_restore(out, tokens)


_QX150_TARGETS = {
    "mathify_79", "_tg_plain_text", "_math_to_visible_68",
    "_light_latex_to_visible_66", "_advanced_latex_to_visible_67",
    "_unicode_math_65", "_qx107_clean_math_text",
}


def _qx150_install():
    done = 0
    seen = set()
    for value in list(globals().values()):
        if not isinstance(value, _types150.FunctionType):
            continue
        if value.__name__ not in _QX150_TARGETS or id(value) in seen:
            continue
        seen.add(id(value))
        if value.__code__.co_freevars or getattr(value, "_qx150_guarded", False):
            continue
        key = "%s_%d" % (value.__name__, id(value))
        copy = _types150.FunctionType(
            value.__code__, value.__globals__, value.__name__,
            value.__defaults__, value.__closure__,
        )
        copy.__kwdefaults__ = value.__kwdefaults__
        _QX150_ORIG[key] = copy
        src = "def _qx150_w(*args, **kwargs):\n    return _qx150_call(%r, args, kwargs)\n" % key
        scratch = {}
        exec(compile(src, "<qx150>", "exec"), value.__globals__, scratch)
        with _cx150.suppress(Exception):
            value.__code__ = scratch["_qx150_w"].__code__
            value.__defaults__ = None
            value.__kwdefaults__ = None
            value._qx150_guarded = True
            done += 1
    return done


_qx150_n = _qx150_install()
with _cx150.suppress(Exception):
    logger.info("[S150] plain-word math guard active on %d renderer(s)", _qx150_n)  # type: ignore[name-defined]
