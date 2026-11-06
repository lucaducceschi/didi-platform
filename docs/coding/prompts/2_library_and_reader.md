# Task 2: Project library, reader and highlights

You are working in the DIDI Platform repository, a local React and Python app. Tasks 0 and 1 are finished, so accounts, projects, codebooks and the annotation API exist. This task lets researchers fill a project with articles, see who has worked on what, and read articles with coded passages highlighted. Selecting text to code it comes in Task 3, so this task is read-only for segments.

## Read first
1. `AGENTS.md`
2. `docs/coding/PRD.md`, especially Sections 1, 4 and 8
3. `docs/coding/spike/`, a working proof of the position logic. It ran in a Streamlit component, so reuse the logic and not the wrapper
4. `/Users/luca/Gits/speech-workbench/frontend/src/components/library/AlignedLibraryView.tsx`, as a reference for the library idea. Do not change that repo.
5. The frontend code and annotation routes from Tasks 0 and 1

Check `git status` first. If Task 1 isn't merged, or the tree isn't clean, stop and ask Luca.

## Build
1. **Add articles:** corpus search with filters, where a lead adds selected results or all matches to the project. Adding all matches must state the count first, and be safe with thousands of articles.
2. **Project library:** the project's articles, paginated and filterable by variety, source and status, showing each coder's status and segment count. Show plainly when a filter hides articles.
3. **Splitting function:** a pure function that splits text at code-point highlight boundaries, handling overlap, nesting, identical spans and touching segments.
4. **Reader:** rendered as in PRD Section 8, with metadata and a list of visible segments grouped by code. Do not trim, reflow or edit the text; readability comes from CSS only.
5. **Views:** the **Mine** / **All coders** toggle, defaulting to **Mine**.
6. **Stale segments:** list them beside the article without highlighting them.
7. **Clicking a highlight:** show the segment's code, coder, quote, memo and date, read-only.

## Tests
- **Unit:** the splitting function, including emoji, combining characters and every overlap case. Concatenated pieces must always equal the input.
- **Browser (Playwright):** load real corpus articles covering non-NFC text, emoji, CRLF, Markdown characters and a roughly 4,000-word article. Find them by querying the DB, not by hardcoding IDs. Create segments through the API, then assert that the reader's text equals `full_text` exactly and each highlight's visible text equals its quote.
- **Library:** counts and statuses are correct for several coders, and a member of another project can't load them.
- **Markup safety:** text containing `<b>` or `<script>` displays literally, and nothing executes.
- **Network:** no third-party requests.

## Do not
- Add text selection or saving. That is Task 3.
- Add assignments.
- Change `full_text`.
- Commit or push until Luca asks.

## Done when
All tests pass. In a browser, add articles in all three languages to a project, create overlapping segments from two coders through the API, and check the library and reader in both themes: highlights are legible, overlaps can be told apart, and ownership is clear. Include screenshots in your report.

Report what you built, what you verified and how, and any departures from the PRD.
