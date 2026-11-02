#!/usr/bin/env bash
# Dual-Remote Sync Script for DIDI Platform:
#   - `origin` (GitHub, public): pushes `main` (code + copyright-safe derived metadata JSONL; excludes `assets/`, `*.db`, `data/raw/`)
#   - `gitlab` (unibz GitLab, private): pushes `main` AND updates `full-data` branch with `assets/`, `data/raw/salto/`, and `data/processed/didi_corpus.db`
set -euo pipefail

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
  echo "Please run sync_remotes.sh from the 'main' branch (currently on '$CURRENT_BRANCH')."
  exit 1
fi

echo "[1/3] Pushing public 'main' branch to GitHub (origin)..."
git push origin main

echo "[2/3] Pushing 'main' branch to private GitLab (gitlab)..."
git push gitlab main

echo "[3/3] Updating 'full-data' branch on private GitLab with assets/ and full SQLite DB..."
# Use a temporary git index to create a commit on top of main containing ignored assets & DB without touching the working tree
TMP_INDEX=$(mktemp -u)
cp .git/index "$TMP_INDEX"
trap 'rm -f "$TMP_INDEX"' EXIT

GIT_INDEX_FILE="$TMP_INDEX" git add -f assets/ data/processed/didi_corpus.db data/raw/salto/
TREE_SHA=$(GIT_INDEX_FILE="$TMP_INDEX" git write-tree)
MAIN_SHA=$(git rev-parse main)
COMMIT_SHA=$(git commit-tree "$TREE_SHA" -p "$MAIN_SHA" -m "chore(gitlab-mirror): bundle full assets, raw salto, and SQLite corpus DB")
git update-ref refs/heads/full-data "$COMMIT_SHA"
git push -f gitlab full-data

echo "Done! Public GitHub ('origin/main') and private GitLab ('gitlab/main' + 'gitlab/full-data') are in sync."
