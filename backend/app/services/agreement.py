"""Inter-Coder Reliability & Agreement (ICA) analysis for qualitative coding."""

import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Annotation, Code, User


def get_inter_coder_agreement(
    db: Session,
    project_id: uuid.UUID,
    min_iou: float = 0.2,
) -> Dict[str, Any]:
    """
    Compute inter-coder agreement across all active annotations in the project.
    Identifies overlapping annotations on the same article between different coders.
    Calculates pairwise observed agreement, chance agreement, Cohen's Kappa,
    confusion matrix, and specific disagreement passages for consensus review.
    """
    # 1. Fetch active annotations and code paths
    annotations = db.scalars(
        select(Annotation)
        .where(Annotation.project_id == project_id, Annotation.status == "active")
        .order_by(Annotation.article_id, Annotation.start_pos)
    ).all()

    codes = {c.id: c for c in db.scalars(select(Code).where(Code.project_id == project_id)).all()}
    users = {u.id: u for u in db.scalars(select(User)).all()}

    # Group annotations by article
    by_article: Dict[str, List[Annotation]] = defaultdict(list)
    for a in annotations:
        by_article[a.article_id].append(a)

    # 2. Find overlapping pairs between distinct coders
    # Key: (user_id_1, user_id_2) where user_id_1 < user_id_2
    pair_matches: Dict[Tuple[uuid.UUID, uuid.UUID], List[Dict[str, Any]]] = defaultdict(list)
    all_coders: Set[uuid.UUID] = set()

    for article_id, arts_anns in by_article.items():
        n = len(arts_anns)
        for i in range(n):
            a1 = arts_anns[i]
            all_coders.add(a1.user_id)
            for j in range(i + 1, n):
                a2 = arts_anns[j]
                if a1.user_id == a2.user_id:
                    continue

                # Check span overlap
                inter = min(a1.end_pos, a2.end_pos) - max(a1.start_pos, a2.start_pos)
                if inter <= 0:
                    continue

                union = max(a1.end_pos, a2.end_pos) - min(a1.start_pos, a2.start_pos)
                iou = inter / union if union > 0 else 0

                if iou >= min_iou or inter >= 15:
                    u_pair = (min(a1.user_id, a2.user_id), max(a1.user_id, a2.user_id))
                    # Standardize ordering
                    first_a, second_a = (a1, a2) if a1.user_id == u_pair[0] else (a2, a1)
                    agreed = first_a.code_id == second_a.code_id
                    pair_matches[u_pair].append({
                        "article_id": article_id,
                        "start_pos": max(first_a.start_pos, second_a.start_pos),
                        "end_pos": min(first_a.end_pos, second_a.end_pos),
                        "quote": first_a.quote if len(first_a.quote) <= len(second_a.quote) else second_a.quote,
                        "coder_1_id": first_a.user_id,
                        "code_1_id": first_a.code_id,
                        "coder_2_id": second_a.user_id,
                        "code_2_id": second_a.code_id,
                        "agreed": agreed,
                        "iou": round(iou, 2),
                    })

    # 3. Calculate pairwise statistics
    pair_stats = []
    total_overlapping = 0
    total_agreed = 0
    all_pairs_for_global: List[Tuple[uuid.UUID, uuid.UUID]] = []

    for (u1, u2), matches in pair_matches.items():
        total_m = len(matches)
        if total_m == 0:
            continue

        agree_cnt = sum(1 for m in matches if m["agreed"])
        total_overlapping += total_m
        total_agreed += agree_cnt

        po = agree_cnt / total_m
        c_pairs = [(m["code_1_id"], m["code_2_id"]) for m in matches]
        all_pairs_for_global.extend(c_pairs)

        # Marginal chance calculation
        all_c = set([c1 for c1, _ in c_pairs] + [c2 for _, c2 in c_pairs])
        f1 = {c: sum(1 for c1, _ in c_pairs if c1 == c) / total_m for c in all_c}
        f2 = {c: sum(1 for _, c2 in c_pairs if c2 == c) / total_m for c in all_c}
        pe = sum(f1[c] * f2[c] for c in all_c)

        kappa = 1.0 if pe == 1.0 else (po - pe) / (1.0 - pe) if (1.0 - pe) != 0 else 0.0

        user1 = users.get(u1)
        user2 = users.get(u2)

        pair_stats.append({
            "coder_1": {"id": str(u1), "display_name": user1.display_name if user1 else str(u1)},
            "coder_2": {"id": str(u2), "display_name": user2.display_name if user2 else str(u2)},
            "overlapping_segments": total_m,
            "agreed_segments": agree_cnt,
            "observed_agreement": round(po, 3),
            "chance_agreement": round(pe, 3),
            "cohens_kappa": round(kappa, 3),
            "interpretation": _interpret_kappa(kappa),
        })

    # 4. Global statistics
    global_po = round(total_agreed / total_overlapping, 3) if total_overlapping > 0 else 0.0
    global_kappa = 0.0
    if all_pairs_for_global:
        tot = len(all_pairs_for_global)
        all_c = set([c1 for c1, _ in all_pairs_for_global] + [c2 for _, c2 in all_pairs_for_global])
        f1 = {c: sum(1 for c1, _ in all_pairs_for_global if c1 == c) / tot for c in all_c}
        f2 = {c: sum(1 for _, c2 in all_pairs_for_global if c2 == c) / tot for c in all_c}
        global_pe = sum(f1[c] * f2[c] for c in all_c)
        global_kappa = round(1.0 if global_pe == 1.0 else (global_po - global_pe) / (1.0 - global_pe) if (1.0 - global_pe) != 0 else 0.0, 3)

    # 5. Confusion matrix between codes
    confusion_counts: Dict[Tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)
    disagreements = []

    for matches in pair_matches.values():
        for m in matches:
            c1_id = m["code_1_id"]
            c2_id = m["code_2_id"]
            if not m["agreed"]:
                # Record confusion
                c_pair = (min(c1_id, c2_id), max(c1_id, c2_id))
                confusion_counts[c_pair] += 1

                c1 = codes.get(c1_id)
                c2 = codes.get(c2_id)
                u1 = users.get(m["coder_1_id"])
                u2 = users.get(m["coder_2_id"])

                disagreements.append({
                    "article_id": m["article_id"],
                    "start_pos": m["start_pos"],
                    "end_pos": m["end_pos"],
                    "quote": m["quote"],
                    "coder_1": u1.display_name if u1 else "Coder 1",
                    "code_1_name": c1.name if c1 else "Unknown",
                    "code_1_color": c1.color if c1 else "#888",
                    "coder_2": u2.display_name if u2 else "Coder 2",
                    "code_2_name": c2.name if c2 else "Unknown",
                    "code_2_color": c2.color if c2 else "#888",
                    "iou": m["iou"],
                })

    confusion_matrix = []
    for (cid1, cid2), count in sorted(confusion_counts.items(), key=lambda x: x[1], reverse=True):
        code1 = codes.get(cid1)
        code2 = codes.get(cid2)
        confusion_matrix.append({
            "code_1": {"id": str(cid1), "name": code1.name if code1 else "Unknown", "color": code1.color if code1 else "#888"},
            "code_2": {"id": str(cid2), "name": code2.name if code2 else "Unknown", "color": code2.color if code2 else "#888"},
            "count": count,
        })

    return {
        "total_coders": len(all_coders),
        "total_overlapping_segments": total_overlapping,
        "total_agreed_segments": total_agreed,
        "global_observed_agreement": global_po,
        "global_kappa": global_kappa,
        "global_interpretation": _interpret_kappa(global_kappa),
        "pairs": pair_stats,
        "confusion_matrix": confusion_matrix[:15],
        "disagreements": disagreements[:50],
    }


def _interpret_kappa(k: float) -> str:
    """Landis & Koch (1977) reliability benchmark interpretation."""
    if k < 0.0:
        return "Poor (Disagreement beyond chance)"
    if k <= 0.20:
        return "Slight Agreement"
    if k <= 0.40:
        return "Fair Agreement"
    if k <= 0.60:
        return "Moderate Agreement"
    if k <= 0.80:
        return "Substantial Agreement"
    return "Almost Perfect Agreement"

