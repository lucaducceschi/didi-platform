"""Coded passages across a project's articles, for reading them together."""

import uuid
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session
from src.languages import get_active_language_codes
from src.ui.data_service import LANGUAGE_LABELS, SOURCE_LABELS, DataService

from backend.app.errors import not_found
from backend.app.models import Annotation, Code, User
from backend.app.services.codebook import code_paths

CONTEXT_CHARACTERS = 120


@dataclass
class PassageFilters:
    code_id: Optional[uuid.UUID] = None
    include_subcodes: bool = True
    languages: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    coder_id: Optional[uuid.UUID] = None
    status: Optional[str] = None


def _wanted_codes(codes: Dict[uuid.UUID, Code], filters: PassageFilters) -> Optional[Set[uuid.UUID]]:
    """The codes a filter covers. An old link to a merged code follows it to the code it became."""
    if filters.code_id is None:
        return None
    current, seen = codes.get(filters.code_id), set()
    while current is not None and current.merged_into is not None and current.id not in seen:
        seen.add(current.id)
        current = codes.get(current.merged_into)
    if current is None:
        raise not_found("This code")
    wanted = {current.id}
    grew = filters.include_subcodes
    while grew:
        added = {code.id for code in codes.values() if code.merged_into is None and code.parent_id in wanted} - wanted
        wanted |= added
        grew = bool(added)
    return wanted


def _context(text: Optional[str], annotation: Annotation) -> tuple:
    """Text around a passage. A stale or moved passage gets none, as its position can't be trusted."""
    if text is None or annotation.status != "active" or text[annotation.start_pos : annotation.end_pos] != annotation.quote:
        return "", ""
    start, end = annotation.start_pos, annotation.end_pos
    before = text[max(0, start - CONTEXT_CHARACTERS) : start]
    after = text[end : end + CONTEXT_CHARACTERS]
    return ("…" if start > CONTEXT_CHARACTERS else "") + before, after + ("…" if end + CONTEXT_CHARACTERS < len(text) else "")


def _match(db: Session, corpus: DataService, project_id: uuid.UUID, filters: PassageFilters) -> dict:
    """Apply the filters in one pass. Each count ignores its own filter, so it shows what choosing another value gives."""
    rows = db.execute(
        select(Annotation.id, Annotation.article_id, Annotation.user_id, Annotation.code_id, Annotation.status, Annotation.start_pos).where(
            Annotation.project_id == project_id
        )
    ).all()
    codes = {code.id: code for code in db.scalars(select(Code).where(Code.project_id == project_id))}
    wanted = _wanted_codes(codes, filters)
    metadata = corpus.get_article_metadata([row.article_id for row in rows])
    active_codes = get_active_language_codes()

    hidden_passages = sum(1 for row in rows if (item := metadata.get(row.article_id)) and item["language"] not in active_codes)

    tests = {
        "code": lambda row, item: wanted is None or row.code_id in wanted,
        "language": lambda row, item: not filters.languages or (item is not None and item["language"] in filters.languages),
        "source": lambda row, item: not filters.sources or (item is not None and item["source"] in filters.sources),
        "coder": lambda row, item: filters.coder_id is None or row.user_id == filters.coder_id,
        "status": lambda row, item: not filters.status or row.status == filters.status,
    }
    matched, direct, languages, sources, coders = [], Counter(), Counter(), Counter(), Counter()
    for row in rows:
        item = metadata.get(row.article_id)
        # Passages on articles with unconfigured languages are hidden
        if item is not None and item["language"] not in active_codes:
            continue
        failed = [name for name, test in tests.items() if not test(row, item)]
        if not failed:
            matched.append(row)
        if not set(failed) - {"code"}:
            direct[row.code_id] += 1
        if item is not None and item["language"] in active_codes and not set(failed) - {"language"}:
            languages[item["language"]] += 1
        if item is not None and not set(failed) - {"source"}:
            sources[item["source"]] += 1
        if not set(failed) - {"coder"}:
            coders[row.user_id] += 1

    # By position within an article, then newest article first. Articles no longer in the corpus sort last.
    matched.sort(key=lambda row: (row.article_id, row.start_pos, str(row.id)))
    matched.sort(key=lambda row: metadata.get(row.article_id, {}).get("publish_date", ""), reverse=True)
    return {
        "project_total": len(rows),
        "hidden_passages": hidden_passages,
        "ids": [row.id for row in matched],
        "codes": codes,
        "metadata": metadata,
        "direct": direct,
        "languages": languages,
        "sources": sources,
        "coders": coders,
    }


def _load_in_order(db: Session, ids: List[uuid.UUID]) -> List[Annotation]:
    found: Dict[uuid.UUID, Annotation] = {}
    for index in range(0, len(ids), 1000):
        found.update({item.id: item for item in db.scalars(select(Annotation).where(Annotation.id.in_(ids[index : index + 1000])))})
    return [found[item] for item in ids if item in found]


def matching_annotations(db: Session, corpus: DataService, project_id: uuid.UUID, filters: PassageFilters) -> List[Annotation]:
    return _load_in_order(db, _match(db, corpus, project_id, filters)["ids"])


def _code_counts(codes: Dict[uuid.UUID, Code], direct: Counter) -> List[dict]:
    totals = Counter()
    for code_id, count in direct.items():
        current, seen = codes.get(code_id), set()
        while current is not None and current.id not in seen:
            seen.add(current.id)
            totals[current.id] += count
            current = codes.get(current.parent_id)
    return [{"id": code.id, "direct": direct[code.id], "total": totals[code.id]} for code in codes.values() if code.merged_into is None]


def find_passages(
    db: Session, corpus: DataService, project_id: uuid.UUID, filters: PassageFilters, page: int, page_size: int
) -> dict:
    found = _match(db, corpus, project_id, filters)
    page_items = _load_in_order(db, found["ids"][(page - 1) * page_size : page * page_size])
    metadata, codes = found["metadata"], found["codes"]
    texts = corpus.get_article_texts([item.article_id for item in page_items if item.status == "active"])
    paths = code_paths(db, project_id)

    results = []
    for annotation in page_items:
        item = metadata.get(annotation.article_id)
        before, after = _context(texts.get(annotation.article_id), annotation)
        results.append({
            "id": annotation.id,
            "article_id": annotation.article_id,
            "in_corpus": item is not None,
            "article_title": item["title"] if item else annotation.article_id,
            "publish_date": item["publish_date"][:10] if item else None,
            "source_label": SOURCE_LABELS.get(item["source"], item["source"]) if item else None,
            "language": item["language"] if item else None,
            "language_label": LANGUAGE_LABELS.get(item["language"], item["language"]) if item else None,
            "code_id": annotation.code_id,
            "code_path": paths.get(annotation.code_id, ""),
            "code_color": codes[annotation.code_id].color,
            "user": annotation.user,
            "quote": annotation.quote,
            "memo": annotation.memo,
            "status": annotation.status,
            "before": before,
            "after": after,
        })

    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(found["coders"])))} if found["coders"] else {}
    return {
        "project_total": found["project_total"],
        "hidden_passages": found["hidden_passages"],
        "total": len(found["ids"]),
        "page": page,
        "page_size": page_size,
        "results": results,
        "codes": _code_counts(codes, found["direct"]),
        "languages": [{"id": key, "label": LANGUAGE_LABELS.get(key, key), "count": count} for key, count in sorted(found["languages"].items())],
        "sources": [{"id": key, "label": SOURCE_LABELS.get(key, key), "count": count} for key, count in sorted(found["sources"].items())],
        "coders": sorted(
            ({"user": users[key], "count": count} for key, count in found["coders"].items()),
            key=lambda entry: entry["user"].display_name.lower(),
        ),
    }
