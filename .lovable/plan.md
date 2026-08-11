# Fast, complete PDF/image quiz conversion

## What will change
- Convert OCR question chunks concurrently with a bounded worker pool instead of waiting for each AI chunk one-by-one, while keeping the existing live progress card.
- Use deterministic OCR-parsed MCQs first and AI only for unresolved questions, reducing latency and avoiding unnecessary provider calls.
- Reconcile every detected question before completion: retry only missing chunks/items once, and report actual accepted/duplicate/invalid counts instead of silently returning fewer quizzes.
- Clean presentation artifacts from option text (`**`, empty `[]`, option-label brackets) without removing meaningful math brackets or trailing teacher credits from question stems.

## Safety and compatibility
- Preserve the current `.gen`, `/pdfpages`, buffer, tenant isolation, explanation-link, provider selection, and posting flows.
- Keep bounded concurrency to avoid rate-limit spikes and retain existing fallback behavior when a provider fails.
- Validate the fix with parser/cleanup tests against the uploaded Bengali biology PDF and Python syntax checks.

## Technical details
- Add a final late-loaded section that overrides the current `_qxv_harvest` and poll sanitation hooks.
- Reuse existing `_qxv_chunks`, `_qxv_extract_sync`, `_qxz_store_rows`, `_qxm_split_questions`, and status-card helpers rather than changing older sections.
