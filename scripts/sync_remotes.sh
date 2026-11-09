#!/usr/bin/env bash
# Dual-Remote Sync Script for DIDI Platform:
#   - `origin` (GitHub, public): pushes `main` (code + copyright-safe derived metadata JSONL; excludes `assets/`, `*.db`, `data/raw/`)
#   - `gitlab` (unibz GitLab, private): pushes `main` AND updates `full-data` branch with `assets/` and `data/raw/`
# The SQLite databases (didi_corpus.db, didi_words.db) stay local since 2026-11-09: they are too large for git
# and can be rebuilt from ~/Data/KST/cluster/ with scripts/import_kst_tageszeitung.py. Review this by 2027-01-09.
set -euo pipefail

if [ "$(date +%Y%m%d)" -ge 20270109 ]; then
  echo "Reminder: the decision to keep the SQLite databases local (2026-11-09) was due for review on 2027-01-09."
  echo "See AGENTS.md, section 2. This is only a reminder; the sync continues."
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "Please run sync_remotes.sh from the 'main' branch (currently on '$CURRENT_BRANCH')."
  exit 1
fi

echo "[1/3] Pushing public 'main' branch to GitHub (origin)..."
git push origin main

echo "[2/3] Pushing 'main' branch to private GitLab (gitlab)..."
git push gitlab main

echo "[3/3] Updating 'full-data' branch on private GitLab with assets/ and data/raw/..."
# Use a temporary git index to create a commit on top of main containing ignored assets & DB without touching the working tree
TMP_INDEX=$(mktemp -u)
cp .git/index "$TMP_INDEX"
trap 'rm -f "$TMP_INDEX"' EXIT

GIT_INDEX_FILE="$TMP_INDEX" git add -f assets/ data/raw/
# Refuse to mirror any file over 100 MB (the databases are kept local)
LARGE=$(GIT_INDEX_FILE="$TMP_INDEX" git ls-files -s | awk '{print $2}' | sort -u | while read -r sha; do
  size=$(git cat-file -s "$sha"); [ "$size" -gt 104857600 ] && echo "$sha ($size bytes)"; done || true)
if [ -n "$LARGE" ]; then
  echo "Refusing to push: files over 100 MB in the full-data tree:"; echo "$LARGE"; exit 1
fi
TREE_SHA=$(GIT_INDEX_FILE="$TMP_INDEX" git write-tree)
MAIN_SHA=$(git rev-parse main)
COMMIT_SHA=$(git commit-tree "$TREE_SHA" -p "$MAIN_SHA" -m "chore(gitlab-mirror): bundle assets and raw data")
git update-ref refs/heads/full-data "$COMMIT_SHA"
git push -f gitlab full-data

echo "Done! Public GitHub ('origin/main') and private GitLab ('gitlab/main' + 'gitlab/full-data') are in sync."

