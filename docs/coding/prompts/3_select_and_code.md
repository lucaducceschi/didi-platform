# Task 3: Select text and code it

You are working in the DIDI Platform repository, a local React and Python app. Tasks 0–2 are finished, so accounts, projects, codebooks, the library and a read-only reader exist. This task lets researchers select text and code it directly, and it completes the phase.

## Read first
1. `AGENTS.md`
2. `docs/coding/PRD.md`, especially Sections 1, 4, 8, 10 and 13
3. `docs/coding/spike/`, for how selection offsets are converted and tested
4. The reader code from Task 2

Check `git status` first. If Task 2 isn't merged, or the tree isn't clean, stop and ask Luca.

## Build
1. **Offset conversion:** one function that converts a browser selection to code points. Ignore collapsed selections, and selections that begin or end outside the reader.
2. **Coding panel:** as in PRD Section 8, show the trimmed quote, a searchable code picker with definitions, a "new code" field and a memo field. The quote shown comes from the server's response once saved.
3. **Save:** the highlight appears without a page reload and without losing scroll position, and the panel clears. Repeating an identical segment shows a clear message, not an error. If the chosen code was merged in the meantime, tell the coder which code it was saved under.
4. **Editing:** clicking your own highlight lets you change its code, edit its memo or delete it, with confirmation for deleting. A stale revision shows a conflict message and reloads the segment. Other coders' highlights stay read-only.
5. **Progress:** opening an article and coding marks it in progress for that researcher, and they can mark it done or reopen it. The library reflects this.
6. **Presence:** the banner in PRD Section 8, with a heartbeat. It never blocks anyone, and it clears after the timeout when a tab closes.
7. **Streamlit:** remove the old annotation form, its codebook CSV button and its `article_annotations` code, with a note pointing to the new app. Keep the MAXQDA article export and the rest of the demo. Do not drop the old table.
8. **Docs:** add `docs/coding/RESEARCHER_GUIDE.md`, written for researchers with no technical background. Update the status tracker in `AGENTS.md` and the phase table in `docs/PRD.md`.

## Tests
Add unit tests for offset conversion, and Playwright tests with real mouse drags as well as scripted selections:
- For non-NFC, emoji, CRLF, Markdown-character and long articles, `full_text[start:end]` equals the selected text after trimming.
- A selection across existing highlights saves the right positions.
- A selection that begins outside the reader is ignored.
- After a reload, the highlight covers exactly the same passage.
- Two logged-in coders save on the same article at once, with neither losing work, and each sees the other in the presence banner.
- A merge in one session while another has that code selected saves to the merged code.
- The same segment edited in two tabs gives one success and one conflict message.

## Do not
- Add assignments, retrieval across articles, agreement statistics or QDPX coded segments. They are later phases.
- Change `full_text`.
- Add external scripts or fonts, or any hosting or cloud code.
- Commit or push until Luca asks.

## Done when
Every acceptance criterion in PRD Section 13 is met and shown in your report, criterion by criterion, with how you checked it. Test on Chromium, Firefox and WebKit through Playwright, and report any browser where positions differ. Report how it behaves on a tablet, without building for it.

Also give Luca a 5-minute checklist so a Ladin-speaking researcher can try it on real articles, because the phase isn't finished until a real researcher has used it.
