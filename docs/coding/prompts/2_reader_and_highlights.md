# Task 2: Article reader with highlights

You are working in the DIDI Platform repository, a React and FastAPI app. Tasks 0 and 1 are finished, so accounts, the codebook and the annotation API exist. This task builds the reader that shows coded passages inside the article. Selecting text to code it comes in Task 3, so this task is read-only for segments.

## Read first
1. `AGENTS.md`
2. `docs/coding/PRD.md`, especially Sections 3 and 8
3. `docs/coding/spike/`, a working proof of the position logic. It ran in a Streamlit component, so reuse the logic and not the wrapper
4. `frontend/src/`, and the annotation routes in `backend/app/`

Check `git status` first. If Task 1 isn't merged, or the tree isn't clean, stop and ask Luca.

## Build
1. **`segmentText(text, highlights)`:** a pure function, as in PRD Section 8, working in code points. Handle overlap, nesting, identical spans and touching segments.
2. **Reader component:** one container with `white-space: pre-wrap`, with spans carrying `data-start` and the raw text as React children. Never use `dangerouslySetInnerHTML`. Do not trim, reflow or edit the text; readability comes from CSS only.
3. **Highlight styles:** as in PRD Section 8, for both themes.
4. **Reader page:** replace the plain article page from Task 0, with metadata, the text and a list of visible segments grouped by code. Search results link here.
5. **Views:** the **Mine** / **All coders** toggle, defaulting to **Mine**.
6. **Stale segments:** list them beside the article without highlighting them.
7. **Clicking a highlight:** show the segment's code, coder, quote, memo and date, read-only.

## Tests
- **Vitest:** `segmentText`, including emoji, combining characters and every overlap case. Concatenated segments must always equal the input.
- **Playwright:** load real corpus articles covering non-NFC text, emoji, CRLF, Markdown characters and a roughly 4,000-word article. Find them by querying the DB, not by hardcoding IDs. Create segments through the API, then assert that the reader's text equals `full_text` exactly and each highlight's visible text equals its quote.
- **Markup safety:** text containing `<b>` or `<script>` displays literally, and nothing executes.
- **Network:** no external requests.

## Do not
- Add text selection or saving. That is Task 3.
- Change `full_text`.
- Commit or push until Luca asks.

## Done when
All tests pass. In a browser, create overlapping segments from two coders through the API, then check both themes: highlights are legible, overlaps can be told apart, and ownership is clear. Include screenshots in your report.

Report what you built, what you verified and how, and any departures from the PRD.
