"""
Single source of truth for media and institutional sources in DIDI.
Defines metadata, human-readable labels, kinds, and ID prefixes.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    name: str
    kind: str
    source_type: str
    id_prefix: str
    default_language: str
    owner: str


SOURCE_REGISTRY: Dict[str, SourceDefinition] = {
    "tageszeitung": SourceDefinition(
        id="tageszeitung",
        name="Die Neue Südtiroler Tageszeitung",
        kind="newspaper",
        source_type="journalism",
        id_prefix="taz",
        default_language="de",
        owner="independent",
    ),
    "salto": SourceDefinition(
        id="salto",
        name="Salto.bz",
        kind="magazine",
        source_type="journalism",
        id_prefix="salto",
        default_language="multi",
        owner="Demos 2.0 cooperative",
    ),
    "provinz_news": SourceDefinition(
        id="provinz_news",
        name="Landespresseamt / Ufficio Stampa",
        kind="institution",
        source_type="official_press",
        id_prefix="provinz",
        default_language="multi",
        owner="Autonome Provinz Bozen - Südtirol / Provincia Autonoma di Bolzano",
    ),
    "rai_bolzano": SourceDefinition(
        id="rai_bolzano",
        name="RAI TGR Bolzano",
        kind="broadcaster",
        source_type="journalism",
        id_prefix="rai",
        default_language="it",
        owner="RAI (public service)",
    ),
    "la_usc": SourceDefinition(
        id="la_usc",
        name="La Usc di Ladins",
        kind="newspaper",
        source_type="journalism",
        id_prefix="la_usc",
        default_language="lld",
        owner="Union Generela di Ladins dla Dolomites",
    ),
    "trail": SourceDefinition(
        id="trail",
        name="RaiNews TGR TRAIL",
        kind="broadcaster",
        source_type="journalism",
        id_prefix="trail",
        default_language="lld",
        owner="RAI Ladinia",
    ),
}

SOURCE_LABELS: Dict[str, str] = {s.id: s.name for s in SOURCE_REGISTRY.values()}

SOURCE_TYPE_LABELS: Dict[str, str] = {
    "journalism": "Journalism",
    "official_press": "Official press",
}


def get_source_type(source_id: str) -> str:
    """Return 'journalism' or 'official_press' for a source. Defaults to 'journalism'."""
    src = SOURCE_REGISTRY.get(source_id)
    return src.source_type if src else "journalism"


def get_sources_for_type(source_type: str) -> list[str]:
    """Return list of source IDs matching given source_type."""
    return [s.id for s in SOURCE_REGISTRY.values() if s.source_type == source_type]


