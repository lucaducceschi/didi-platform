# Annotation Database Schema

This describes the PostgreSQL database behind the annotation workbench. The migrations in [`backend/alembic/versions/`](../../backend/alembic/versions/) define it exactly. The corpus itself stays in a separate read-only SQLite file, so `article_id` values refer to that file rather than to a table here.

## Tables

| Table | One row per | Key columns and rules |
|---|---|---|
| `users` | Person | `username` unique ignoring case; `password_hash` (Argon2); `is_admin`; `active`. Deactivated users keep their work |
| `sessions` | Login | `token_hash` (the browser holds the token, the database only its SHA-256); `expires_at` |
| `login_attempts` | Username and IP address with recent failures | Used to limit failed logins |
| `projects` | Study | `name` unique ignoring case; `archived` makes it read-only; `revision` |
| `project_members` | Person in a project | `role` is `lead` or `coder`. A project keeps at least one lead |
| `project_articles` | Article in a project | Segments can only be made on these articles |
| `article_progress` | Person's status on an article | `in_progress` or `done`; no row means not started |
| `codes` | Code in a project's codebook | See below |
| `annotations` | Coded passage | See below |
| `presence` | Person with an article open | `last_seen` |
| `activity_log` | Codebook or project change | Append only; `details` holds structured information |

## Codes

- A code belongs to one project. `parent_id` makes the tree, and active names are unique among siblings, ignoring case.
- `merged_into` marks a code merged into another. It stays in the table as a record but is hidden from the codebook, and its name becomes free again.
- `revision` increases with every change. An update sending an old revision is refused.

## Annotations

- `start_pos` and `end_pos` are 0-based Unicode code points with an **exclusive end**, so in Python `full_text[start_pos:end_pos] == quote`.
- `quote` is always taken from the corpus text by the server, after trimming whitespace from both ends.
- `text_sha256` is the SHA-256 of the UTF-8 `full_text` when the segment was made.
- `status` is `active`, or `stale` when a corpus update left the passage impossible to place. Stale segments are kept and never deleted automatically.
- A passage with two codes is two rows. The combination of project, article, span, code and coder is unique.
- Only the author can change or delete a segment. `revision` works as it does for codes.

## After a corpus rebuild

`make reconcile` compares each annotation's `text_sha256` with the current text:

| Situation | Result |
|---|---|
| Text unchanged | Nothing happens |
| Text changed, quote occurs exactly once | Positions and hash are updated |
| Text changed, quote missing or repeated | Marked `stale` |
| Article no longer in the corpus | Marked `stale` |
| A stale segment's original text is back | Restored to `active` |

## Exports

Each project offers two CSV files, UTF-8 with a byte order mark so that Excel reads accented text correctly:

- **Segments:** one row per annotation, with article details, coder, full code path, positions, quote, memo, status and hash.
- **Codes:** one row per code, including merged ones, with path, definition, color, counts and `merged_into`.

Text is exported exactly as stored, so a cell can begin with a character such as `=`. Spreadsheet programs may treat such a cell as a formula, so check these if you open an export in one.
