# Task 4: Retrieval and project article management

You are working in the DIDI Platform repository, a local React and Python app. Tasks 0–3 are finished, so researchers can code articles inside projects. This task lets them read coded passages together across articles, and it closes two gaps found while testing Task 3.

No researcher trial has happened yet. Luca chose on 2026-11-07 to keep building because no Ladin researcher is available right now. Don't describe Task 3 as trialled.

## Read first
1. `AGENTS.md`
2. `docs/coding/PRD.md`, especially Sections 1, 6, 8 and 9
3. `backend/app/services/library.py`, `backend/app/services/exports.py` and `frontend/src/pages/project/ReaderPage.tsx`

Check `git status` first. If Task 3 isn't merged, or the tree isn't clean, stop and ask Luca.

## Build
1. **Passages API:** list a project's segments across articles, filterable by code, variety, source, coder and status, and paginated. A code includes its subcodes unless the caller turns that off. Sort by newest article, then position in the article. Include counts for each filter, and the text just before and after each passage, cut from `full_text` by code point. Never show context for a stale passage, or if `full_text[start:end]` no longer equals the quote.
2. **Passages tab:** a code tree with counts, filters kept in the URL, and passage cards showing the code, coder, article, memo and context. **Mine** is the default for project members, as in the reader, and the page says when filters hide passages.
3. **Link to the article:** a passage opens its article with that passage selected and in view, under **All coders**, with a way back to the same filtered list.
4. **CSV:** download the passages matching the current filters, using the columns of the existing annotation export.
5. **Ladin caution:** when filtering by a Ladin variety, say that no Ladin speaker has reviewed the variety labels yet.
6. **Remove articles:** a lead can remove an article with no segments, after confirming, and can remove all articles nobody has started. An article with segments can't be removed, and the message says why. A segment save and a removal running at the same time must not leave a segment without its article.
7. **From corpus search to a project:** a lead can take the current search and filters to a project's **Add articles** page.
8. **Docs:** update `docs/coding/RESEARCHER_GUIDE.md`, the build order and later phases in `docs/coding/PRD.md`, the phase table in `docs/PRD.md` and the tracker in `AGENTS.md`.

## Tests
- **API:** every filter and count, subcodes on and off, a merged code following its target, context by code point on emoji and NFD text, stale passages and articles no longer in the corpus, project isolation, the CSV matching the filters, and the permissions for removal.
- **Concurrency:** a removal waits for a segment save still in progress, then refuses.
- **Browser:** filter passages, open one from another coder and see it selected, return to the same list, confirm markup in a quote displays literally, remove articles, go from search to **Add articles**, and make no third-party requests.

## Do not
- Add full-text search within passages, agreement statistics, assignments or QDPX coded segments.
- Change `full_text`, or add a migration unless it's really needed.
- Let a lead delete another coder's segments.
- Commit or push until Luca asks.

## Done when
All tests pass, and the Passages tab works on your own real articles in both themes and at phone width. Report what you built, how you checked it, and any departures from this prompt.
