#!/usr/bin/env python3
"""Print real corpus articles with difficult text as JSON, for browser tests. No article IDs are hardcoded."""

import json
import re
import sqlite3
import unicodedata
from pathlib import Path

CORPUS = Path(__file__).resolve().parent.parent / "data" / "processed" / "didi_corpus.db"
MARKDOWN = re.compile(r"[*_`$#~]")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def main() -> None:
    connection = sqlite3.connect(f"{CORPUS.as_uri()}?mode=ro", uri=True)
    rows = connection.execute("SELECT id, language, full_text, word_count FROM articles ORDER BY id").fetchall()
    connection.close()

    def first(test):
        return next(row[0] for row in rows if test(row))

    print(json.dumps({
        "non_nfc": first(lambda row: unicodedata.normalize("NFC", row[2]) != row[2] and row[3] > 40),
        "emoji": first(lambda row: any(ord(ch) > 0xFFFF for ch in row[2])),
        "markdown": first(lambda row: MARKDOWN.search(row[2]) and row[3] > 40),
        "control_character": first(lambda row: CONTROL.search(row[2])),
        "long": max(rows, key=lambda row: row[3])[0],
        "german": first(lambda row: row[1] == "de" and row[3] > 40),
        "italian": first(lambda row: row[1] == "it" and row[3] > 40),
        "ladin": first(lambda row: row[1] == "lld_gherd" and row[3] > 40),
    }))


if __name__ == "__main__":
    main()
