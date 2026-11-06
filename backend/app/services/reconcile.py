"""Keep annotations attached to their text after a corpus rebuild."""

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Annotation, utcnow
from backend.app.services.activity import log_activity
from backend.app.services.annotations import text_hash


def _load_texts(corpus_path: Path, article_ids: set) -> Dict[str, str]:
    connection = sqlite3.connect(f"{corpus_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        ids = sorted(article_ids)
        texts: Dict[str, str] = {}
        for index in range(0, len(ids), 500):
            batch = ids[index : index + 500]
            placeholders = ",".join("?" * len(batch))
            texts.update(connection.execute(f"SELECT id, full_text FROM articles WHERE id IN ({placeholders})", batch))
        return texts
    finally:
        connection.close()


def reconcile_annotations(db: Session, corpus_path: Path) -> Counter:
    """
    Check every annotation against the current corpus. It never deletes anything.

    A changed text keeps the annotation if its quote occurs exactly once; otherwise it becomes stale.
    """
    annotations = list(db.scalars(select(Annotation).with_for_update()))
    texts = _load_texts(corpus_path, {a.article_id for a in annotations}) if annotations else {}
    outcome: Counter = Counter()
    per_project: Dict[object, Counter] = {}

    for annotation in annotations:
        text = texts.get(annotation.article_id)
        result = "unchanged"
        if text is None:
            if annotation.status != "stale":
                annotation.status = "stale"
                result = "stale"
        else:
            current_hash = text_hash(text)
            if current_hash == annotation.text_sha256:
                in_place = text[annotation.start_pos : annotation.end_pos] == annotation.quote
                if annotation.status == "stale" and in_place:
                    annotation.status = "active"
                    result = "restored"
            else:
                first = text.find(annotation.quote)
                if first >= 0 and text.find(annotation.quote, first + 1) < 0:
                    annotation.start_pos = first
                    annotation.end_pos = first + len(annotation.quote)
                    annotation.text_sha256 = current_hash
                    annotation.status = "active"
                    result = "reanchored"
                elif annotation.status != "stale":
                    annotation.status = "stale"
                    result = "stale"
        outcome[result] += 1
        if result != "unchanged":
            annotation.revision += 1
            annotation.updated_at = utcnow()
            per_project.setdefault(annotation.project_id, Counter())[result] += 1

    for project_id, counts in per_project.items():
        log_activity(db, "annotations.reconciled", project_id=project_id, **counts)
    return outcome
