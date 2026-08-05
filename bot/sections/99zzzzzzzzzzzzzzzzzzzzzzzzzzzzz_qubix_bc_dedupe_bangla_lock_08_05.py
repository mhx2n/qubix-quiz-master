# -*- coding: utf-8 -*-
# ══════════════════════════════════════════════════════════════════════════════
# SECTION 122 — BUFFER CARD BUTTON DEDUPE · HARD BANGLA LOCK (2026-08-05)
#
#   1. `.bc` / `/buffercount` card no longer shows two "Export CSV" buttons —
#      duplicate labels/callbacks are collapsed, keeping the working one.
#   2. Bangla lock: if the source page contains ANY Bengali characters, the
#      generated stems/options/explanations are forced to Bangla. Rows that
#      still come back in English are translated back to Bangla (numbers,
#      formulas and math symbols untouched) before they hit the buffer.
#
#   Layer-only: no earlier section is rewritten.
# ══════════════════════════════════════════════════════════════════════════════

import contextlib as _cx122
import json as _json122
import re as _re122


def _qx122_log(message, level="info"):
    with _cx122.suppress(Exception):
        getattr(_qx_log, level)("[QUBIX-122] " + str(message))  # type: ignore[name-defined]


# ─────────────────────────────────────────────────────────────────────────────
# 1) Buffer-count keyboard — one Export CSV only
# ─────────────────────────────────────────────────────────────────────────────
def _qx122_key(button):
    text = _re122.sub(r"\s+", " ", str(getattr(button, "text", "") or "")).strip().lower()
    text = _re122.sub(r"[^a-z\u0980-\u09FF ]", "", text).strip()
    return text


def _qx122_dedupe(markup):
    rows_in = getattr(markup, "inline_keyboard", None)
    if not rows_in:
        return markup
    seen, rows_out, changed = set(), [], False
    for row in rows_in:
        kept = []
        for button in row:
            key = _qx122_key(button)
            if key and key in seen:
                changed = True
                continue
            if key:
                seen.add(key)
            kept.append(button)
        if kept:
            rows_out.append(kept)
        elif row:
            changed = True
    if not changed:
        return markup
    with _cx122.suppress(Exception):
        return InlineKeyboardMarkup(rows_out)  # type: ignore[name-defined]
    return markup


_qx122_prev_bc_kb = globals().get("_qx121_bc_keyboard")

if callable(_qx122_prev_bc_kb):
    def _qx121_bc_keyboard(uid):  # noqa: F811
        markup = _qx122_prev_bc_kb(uid)
        cleaned = _qx122_dedupe(markup)
        return cleaned if cleaned is not None else markup

    globals()["_qx121_bc_keyboard"] = _qx121_bc_keyboard


# ─────────────────────────────────────────────────────────────────────────────
# 2) Hard Bangla lock
# ─────────────────────────────────────────────────────────────────────────────
_QX122_BN = _re122.compile(r"[\u0980-\u09FF]")

_qx122_prev_lang = globals().get("_generation_lang_88")


def _generation_lang_88(text=None, *args, **kwargs):  # noqa: F811
    body = str(text or "")
    if len(_QX122_BN.findall(body)) >= 2:
        return "bn"
    if callable(_qx122_prev_lang):
        with _cx122.suppress(Exception):
            return _qx122_prev_lang(text, *args, **kwargs)
    return "bn"


globals()["_generation_lang_88"] = _generation_lang_88


_qx122_prev_prompt = globals().get("_qxv_prompt")

if callable(_qx122_prev_prompt):
    def _qxv_prompt(chunk, lang):  # noqa: F811
        prompt = _qx122_prev_prompt(chunk, lang)
        if lang == "bn":
            prompt = prompt.replace(
                "SOURCE:",
                "8. ভাষা বাধ্যতামূলক: প্রশ্ন, চারটি অপশন ও ব্যাখ্যা সবকিছু বাংলায় লিখবে। "
                "OCR টেক্সট ইংরেজিতে থাকলেও বাংলায় অনুবাদ করে লিখবে। শুধু সংখ্যা, "
                "রাশিমালা, চলক ও গাণিতিক প্রতীক অপরিবর্তিত রাখবে। কোনো ইংরেজি বাক্য "
                "লিখবে না।\n\nSOURCE:",
                1,
            )
        return prompt

    globals()["_qxv_prompt"] = _qxv_prompt


def _qx122_needs_bn(row) -> bool:
    if not isinstance(row, dict):
        return False
    body = " ".join([
        str(row.get("question") or ""),
        " ".join(str(o) for o in (row.get("options") or [])),
        str(row.get("explanation") or ""),
    ])
    letters = len(_re122.findall(r"[A-Za-z]{3,}", body))
    return letters >= 2 and len(_QX122_BN.findall(body)) < 2


def _qx122_translate(rows):
    payload = []
    for index, row in enumerate(rows):
        payload.append({
            "i": index,
            "question": str(row.get("question") or ""),
            "options": [str(o) for o in (row.get("options") or [])],
            "explanation": str(row.get("explanation") or ""),
        })
    if not payload:
        return {}
    prompt = (
        "তুমি একজন বাংলা একাডেমিক অনুবাদক। নিচের JSON-এর প্রতিটি item-এর "
        "question, options ও explanation বাংলায় অনুবাদ করো।\n"
        "নিয়ম: সংখ্যা, চলক, একক, রাশিমালা ও গাণিতিক প্রতীক (√, ², ×10⁻⁴, sin, cos, "
        "lim, log) হুবহু রাখবে; অপশনের সংখ্যা ও ক্রম বদলাবে না; কোনো ব্যাখ্যা যোগ "
        "করবে না।\n"
        'STRICT JSON only: {"items":[{"i":0,"question":"..","options":["..","..","..",".."],'
        '"explanation":".."}]}\n\nINPUT:\n'
        + _json122.dumps({"items": payload}, ensure_ascii=False)
    )
    raw = ""
    caller = globals().get("_qxv_ai_raw")
    if callable(caller):
        with _cx122.suppress(Exception):
            raw = str(caller(prompt, 45) or "")
    if not raw:
        return {}
    items = []
    parser = globals().get("_qxv_items")
    if callable(parser):
        with _cx122.suppress(Exception):
            items = list(parser(raw) or [])
    if not items:
        with _cx122.suppress(Exception):
            items = list((_json122.loads(raw) or {}).get("items") or [])
    out = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        with _cx122.suppress(Exception):
            out[int(item.get("i"))] = item
    return out


def _qx122_apply(row, patch):
    if not isinstance(patch, dict):
        return row
    question = str(patch.get("question") or "").strip()
    explanation = str(patch.get("explanation") or "").strip()
    options = [str(o).strip() for o in (patch.get("options") or []) if str(o).strip()]
    old_options = list(row.get("options") or [])
    if question and _QX122_BN.search(question):
        row["question"] = question
    if explanation and _QX122_BN.search(explanation):
        row["explanation"] = explanation
    if len(options) == len(old_options) and any(_QX122_BN.search(o) for o in options):
        row["options"] = options
    return row


_qx122_prev_extract = globals().get("_qxv_extract_sync")

if callable(_qx122_prev_extract):
    def _qxv_extract_sync(source_text, lang="bn"):  # noqa: F811
        rows = _qx122_prev_extract(source_text, lang) or []
        if lang != "bn" or not rows:
            return rows
        pending = [i for i, row in enumerate(rows) if _qx122_needs_bn(row)]
        if not pending:
            return rows
        subset = [rows[i] for i in pending]
        patches = _qx122_translate(subset)
        for local, global_index in enumerate(pending):
            patch = patches.get(local)
            if patch:
                with _cx122.suppress(Exception):
                    rows[global_index] = _qx122_apply(rows[global_index], patch)
        _qx122_log(f"bangla lock applied on {len(pending)} row(s)")
        return rows

    globals()["_qxv_extract_sync"] = _qxv_extract_sync


_qx122_log("section 122 loaded")
