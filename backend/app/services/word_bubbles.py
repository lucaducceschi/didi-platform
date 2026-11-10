"""
Word Bubbles Service for DIDI Platform Dashboard.

Provides pre-aggregated and dynamically cached semantic word bubbles
across three research perspectives:
1. 'focus': Key regional sociopolitical themes (Autonomie, Brenner, Proporz, Wolf, etc.)
2. 'languages': Cross-linguistic keyness terms (German media vs. Italian media emphasis)
3. 'discourse': Journalistic scrutiny vs. Official Press institutional releases
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ui.data_service import DataService

# Curated regional lexicon seeds with metadata and bilingual mappings
FOCUS_THEMES = [
    {
        "id": "autonomie",
        "term": "Autonomie",
        "twin_term": "Autonomia",
        "fts_query": "autonomie* OR autonomia*",
        "category": "Autonomy & Rights",
        "category_color": "#2b6cb0",
        "primary_moral": "Authority",
        "sentiment": 0.12,
        "sample_snippet": "Die Weiterentwicklung des Südtiroler Autonomiestatuts steht im Mittelpunkt der institutionellen Verhandlungen mit Rom.",
        "collocates": ["Statut", "Zuständigkeiten", "Rom", "Verhandlungen", "Schutzmacht"],
    },
    {
        "id": "brenner",
        "term": "Brenner",
        "twin_term": "Brennero",
        "fts_query": "brenner* OR brennero*",
        "category": "Infrastructure & Mobility",
        "category_color": "#dd6b20",
        "primary_moral": "Fairness",
        "sentiment": -0.22,
        "sample_snippet": "Der Transitverkehr über den Brenner und die Sanierung der Luegbrücke sorgen für anhaltende Spannungen zwischen Bozen, Innsbruck und Rom.",
        "collocates": ["Transit", "Luegbrücke", "Verkehr", "Lkw", "Autobahn"],
    },
    {
        "id": "transit",
        "term": "Transit",
        "twin_term": "Transito",
        "fts_query": "transit*",
        "category": "Infrastructure & Mobility",
        "category_color": "#dd6b20",
        "primary_moral": "Harm / Care",
        "sentiment": -0.35,
        "sample_snippet": "Bürgermeister und Anrainer fordern eine wirksame Obergrenze für den alpenquerenden Schwerverkehr.",
        "collocates": ["Brenner", "Fahrverbot", "Korridor", "Emissionen", "Klage"],
    },
    {
        "id": "wolf",
        "term": "Wolf",
        "twin_term": "Lupo",
        "fts_query": "wolf* OR wölfe* OR lupo* OR lupi*",
        "category": "Environment & Agriculture",
        "category_color": "#38a169",
        "primary_moral": "Harm / Care",
        "sentiment": -0.28,
        "sample_snippet": "Die Zunahme von Wolfsrissen auf den Südtiroler Almen entfacht hitzige Debatten zwischen Tierhaltern und Naturschutzverbänden.",
        "collocates": ["Almen", "Abschuss", "Großraubwild", "Bauernbund", "Weidewirtschaft"],
    },
    {
        "id": "proporz",
        "term": "Proporz",
        "twin_term": "Proporzionale",
        "fts_query": "proporz*",
        "category": "Minority & Governance",
        "category_color": "#805ad5",
        "primary_moral": "Fairness",
        "sentiment": 0.05,
        "sample_snippet": "Der ethnische Proporz bleibt der Grundpfeiler des friedlichen Zusammenlebens und der Stellenvergabe im öffentlichen Dienst.",
        "collocates": ["Sprachgruppen", "Erklärung", "Stellen", "Quote", "Zweisprachigkeit"],
    },
    {
        "id": "zweisprachigkeit",
        "term": "Zweisprachigkeit",
        "twin_term": "Bilinguismo",
        "fts_query": "zweisprachig* OR bilingu*",
        "category": "Education & Language",
        "category_color": "#319795",
        "primary_moral": "Loyalty",
        "sentiment": 0.10,
        "sample_snippet": "Die Reform der Zweisprachigkeitsprüfung soll den Erwerb von Sprachzertifikaten praxisnaher und flexibler gestalten.",
        "collocates": ["Prüfung", "Schule", "Italienisch", "Deutsch", "Niveau"],
    },
    {
        "id": "sanitaet",
        "term": "Sanität",
        "twin_term": "Sanità",
        "fts_query": "sanität* OR sanit*",
        "category": "Healthcare",
        "category_color": "#e53e3e",
        "primary_moral": "Harm / Care",
        "sentiment": -0.15,
        "sample_snippet": "Personalmangel und Wartezeiten im Südtiroler Sanitätsbetrieb fordern grundlegende strukturelle Reformen.",
        "collocates": ["Krankenhaus", "Ärzte", "Pflege", "Wartezeiten", "Betrieb"],
    },
    {
        "id": "schule",
        "term": "Schule",
        "twin_term": "Scuola",
        "fts_query": "schule* OR schul* OR scuola* OR scuole*",
        "category": "Education & Language",
        "category_color": "#319795",
        "primary_moral": "Care",
        "sentiment": 0.25,
        "sample_snippet": "Die deutsche und die italienische Bildungsdirektion investieren in mehrsprachige Schulmodelle und digitale Lehrmittel.",
        "collocates": ["Lehrer", "Bildung", "Kinder", "Unterricht", "Spracherwerb"],
    },
    {
        "id": "kompatscher",
        "term": "Kompatscher",
        "twin_term": "Kompatscher",
        "fts_query": "kompatscher*",
        "category": "Governance & Politics",
        "category_color": "#4a5568",
        "primary_moral": "Authority",
        "sentiment": 0.08,
        "sample_snippet": "Landeshauptmann Arno Kompatscher führt die Verhandlungen über die Kompetenzübertragungen mit Ministerpräsidentin Meloni.",
        "collocates": ["Landeshauptmann", "Landesregierung", "Rom", "Koalition", "SVP"],
    },
    {
        "id": "ladin",
        "term": "Ladinisch",
        "twin_term": "Ladino",
        "fts_query": "ladin* OR ladinisch*",
        "category": "Minority & Culture",
        "category_color": "#d69e2e",
        "primary_moral": "Loyalty",
        "sentiment": 0.30,
        "sample_snippet": "Kulturelle und mediale Initiativen stärken die ladinische Identität in Gröden und im Gadertal.",
        "collocates": ["Gherdëina", "Badia", "Kultur", "Sprache", "Minderheit"],
    },
    {
        "id": "wohnen",
        "term": "Wohnen",
        "twin_term": "Abitare",
        "fts_query": "wohnen* OR wohnung* OR casa* OR allogg*",
        "category": "Economy & Social",
        "category_color": "#718096",
        "primary_moral": "Fairness",
        "sentiment": -0.20,
        "sample_snippet": "Die explodierenden Mieten und Immobilienpreise machen bezahlbaren Wohnraum für Einheimische zu einer der drängendsten sozialen Fragen.",
        "collocates": ["Mieten", "Wohnbauförderung", "Mittelstand", "Preise", "Gemeinden"],
    },
    {
        "id": "klimaplan",
        "term": "Klimaplan",
        "twin_term": "Piano Clima",
        "fts_query": "klimaplan* OR klima* OR clima*",
        "category": "Environment & Agriculture",
        "category_color": "#38a169",
        "primary_moral": "Care",
        "sentiment": 0.02,
        "sample_snippet": "Mit dem Klimaplan 2040 setzt die Südtiroler Landesregierung auf Dekarbonisierung, erneuerbare Energien und nachhaltige Mobilität.",
        "collocates": ["Ziele", "CO2", "Mobilität", "Energie", "Nachhaltigkeit"],
    },
    {
        "id": "tourismus",
        "term": "Tourismus",
        "twin_term": "Turismo",
        "fts_query": "tourismus* OR tourist* OR turismo*",
        "category": "Economy & Social",
        "category_color": "#d69e2e",
        "primary_moral": "Authority",
        "sentiment": 0.15,
        "sample_snippet": "Bettenstopp und Besucherlenkung: Südtirol sucht den Ausgleich zwischen wirtschaftlicher Wertschöpfung und Lebensqualität für die Bewohner.",
        "collocates": ["Gäste", "Bettenstopp", "Saison", "Hotels", "Wirtschaft"],
    },
    {
        "id": "pnrr",
        "term": "PNRR",
        "twin_term": "PNRR",
        "fts_query": "pnrr*",
        "category": "Economy & Investments",
        "category_color": "#2b6cb0",
        "primary_moral": "Fairness",
        "sentiment": 0.18,
        "sample_snippet": "EU-Wiederaufbaufonds: Millioneninvestitionen für Digitalisierung, Wassernetze und Schulgebäude im ländlichen Raum.",
        "collocates": ["Projekte", "Mittel", "Investitionen", "Fristen", "Gemeinden"],
    },
    {
        "id": "landtag",
        "term": "Landtag",
        "twin_term": "Consiglio",
        "fts_query": "landtag* OR consiglio*",
        "category": "Governance & Politics",
        "category_color": "#4a5568",
        "primary_moral": "Authority",
        "sentiment": -0.05,
        "sample_snippet": "Hitzige Haushaltsdebatten und Misstrauensanträge prägen die Plenarsitzungen des Südtiroler Landtages.",
        "collocates": ["Abgeordnete", "Opposition", "Beschluss", "Debatte", "Mehrheit"],
    },
]

LANGUAGE_GAP_THEMES = [
    # Distinctive German media focus
    {"id": "landesregierung", "term": "Landesregierung", "twin_term": "Giunta Provinciale", "fts_query": "landesregierung*", "category": "German Media Focus", "category_color": "#3182ce", "primary_moral": "Authority", "sentiment": 0.04, "sample_snippet": "Die Landesregierung beschließt neue Richtlinien für die Vergabe von Fördergeldern.", "collocates": ["Beschluss", "SVP", "Landeshauptmann", "Sitzung"]},
    {"id": "bauernbund", "term": "Bauernbund", "twin_term": "Unione Agricoltori", "fts_query": "bauernbund*", "category": "German Media Focus", "category_color": "#3182ce", "primary_moral": "Loyalty", "sentiment": 0.12, "sample_snippet": "Der Südtiroler Bauernbund mahnt schnelle Hilfen bei Unwetterschäden und Entlastungen an.", "collocates": ["Landwirtschaft", "Obmann", "Höfe", "Förderung"]},
    {"id": "schuetzen", "term": "Schützen", "twin_term": "Cappelli piumati", "fts_query": "schützen* OR schuetzen*", "category": "German Media Focus", "category_color": "#3182ce", "primary_moral": "Loyalty", "sentiment": 0.01, "sample_snippet": "Der Schützenbund erinnert an historische Abkommen und fordert konsequenten Minderheitenschutz.", "collocates": ["Bund", "Tradition", "Heimat", "Gedenken"]},
    {"id": "volkspartei", "term": "SVP", "twin_term": "SVP", "fts_query": "volkspartei* OR svp*", "category": "German Media Focus", "category_color": "#3182ce", "primary_moral": "Authority", "sentiment": 0.06, "sample_snippet": "Parteitag der Volkspartei: Kursbestimmung zwischen traditioneller Basis und urbaner Wählerschaft.", "collocates": ["Partei", "Obmann", "Wahlen", "Fraktion"]},
    {"id": "sanitaetsbetrieb", "term": "Sanitätsbetrieb", "twin_term": "Azienda Sanitaria", "fts_query": "sanitätsbetrieb*", "category": "German Media Focus", "category_color": "#3182ce", "primary_moral": "Care", "sentiment": -0.18, "sample_snippet": "Generaldirektion des Sanitätsbetriebes legt neuen Strategieplan zur Primärversorgung vor.", "collocates": ["Krankenhäuser", "Direktion", "Pflege", "Ausschreibung"]},

    # Distinctive Italian media focus
    {"id": "giunta", "term": "Giunta", "twin_term": "Landesregierung", "fts_query": "giunta*", "category": "Italian Media Focus", "category_color": "#38a169", "primary_moral": "Authority", "sentiment": 0.05, "sample_snippet": "La Giunta provinciale ha approvato lo stanziamento di fondi straordinari per le famiglie.", "collocates": ["Provincia", "Assessore", "Delibera", "Seduta"]},
    {"id": "fratelli", "term": "Fratelli d'Italia", "twin_term": "Fratelli d'Italia", "fts_query": "fratelli*", "category": "Italian Media Focus", "category_color": "#38a169", "primary_moral": "Loyalty", "sentiment": -0.02, "sample_snippet": "Il gruppo consiliare di Fratelli d'Italia solleva la questione dell'ordine pubblico nel capoluogo.", "collocates": ["Governo", "Meloni", "Consiglio", "Sicurezza"]},
    {"id": "questura", "term": "Questura", "twin_term": "Polizeidirektion", "fts_query": "questura*", "category": "Italian Media Focus", "category_color": "#38a169", "primary_moral": "Authority", "sentiment": -0.22, "sample_snippet": "Intensificati i controlli straordinari della Questura di Bolzano nelle zone calde della città.", "collocates": ["Polizia", "Bolzano", "Controlli", "Sicurezza"]},
    {"id": "comunita", "term": "Comunità Comprensoriale", "twin_term": "Bezirksgemeinschaft", "fts_query": "comunità*", "category": "Italian Media Focus", "category_color": "#38a169", "primary_moral": "Care", "sentiment": 0.15, "sample_snippet": "I servizi sociali della Comunità Comprensoriale potenziano l'assistenza domiciliare per anziani.", "collocates": ["Sociale", "Servizi", "Territorio", "Sindaco"]},
    {"id": "prefettura", "term": "Commissariato del Governo", "twin_term": "Regierungskommissariat", "fts_query": "commissariato* OR prefettura*", "category": "Italian Media Focus", "category_color": "#38a169", "primary_moral": "Authority", "sentiment": 0.00, "sample_snippet": "Vertice per la sicurezza convocato presso il Commissariato del Governo alla presenza dei vertici delle forze dell'ordine.", "collocates": ["Prefetto", "Sicurezza", "Forze", "Stato"]},
]

DISCOURSE_THEMES = [
    # Official press office framing (PR & Institutional announcements)
    {"id": "investitionen", "term": "Investitionen", "twin_term": "Investimenti", "fts_query": "investition* OR investiment*", "category": "Institutional Press", "category_color": "#d69e2e", "primary_moral": "Fairness", "sentiment": 0.35, "sample_snippet": "Rekordinvestitionen in Bildungsinfrastruktur und nachhaltigen öffentlichen Nahverkehr freigegeben.", "collocates": ["Millionen", "Zukunft", "Projekte", "Förderung"]},
    {"id": "nachhaltigkeit", "term": "Nachhaltigkeit", "twin_term": "Sostenibilità", "fts_query": "nachhaltig* OR sostenibil*", "category": "Institutional Press", "category_color": "#d69e2e", "primary_moral": "Care", "sentiment": 0.40, "sample_snippet": "Die Provinz setzt auf eine ganzheitliche Strategie für ökologische und ökonomische Zukunftsfähigkeit.", "collocates": ["Klima", "Ressourcen", "Entwicklung", "Zertifikat"]},
    {"id": "zusammenarbeit", "term": "Zusammenarbeit", "twin_term": "Collaborazione", "fts_query": "zusammenarbeit* OR collaborazion*", "category": "Institutional Press", "category_color": "#d69e2e", "primary_moral": "Loyalty", "sentiment": 0.32, "sample_snippet": "Grenzüberwindende Kooperation der Europaregion Tirol-Südtirol-Trentino weiter vertieft.", "collocates": ["Euregio", "Grenzen", "Gemeinsam", "Abkommen"]},
    {"id": "aufwertung", "term": "Aufwertung", "twin_term": "Riqualificazione", "fts_query": "aufwert* OR riqualificazion*", "category": "Institutional Press", "category_color": "#d69e2e", "primary_moral": "Care", "sentiment": 0.28, "sample_snippet": "Projekt zur städtebaulichen Riqualificazione historischer Ortskerne und Dorfplätze gestartet.", "collocates": ["Zentrum", "Orte", "Bürger", "Lebensqualität"]},

    # Journalistic scrutiny framing (Critical news reporting)
    {"id": "kritik", "term": "Kritik", "twin_term": "Critica", "fts_query": "kritik* OR critic*", "category": "Investigative Journalism", "category_color": "#805ad5", "primary_moral": "Fairness", "sentiment": -0.32, "sample_snippet": "Scharfe Kritik der Opposition an intransparenten Vergaben und überhöhten Beraterhonoraren.", "collocates": ["Opposition", "Vorwurf", "Vergabe", "Transparenz"]},
    {"id": "streit", "term": "Streit", "twin_term": "Scontro", "fts_query": "streit* OR scontr* OR polemic*", "category": "Investigative Journalism", "category_color": "#805ad5", "primary_moral": "Harm", "sentiment": -0.42, "sample_snippet": "Koalitionskrach eskaliert: Parteiflügel streiten offen über die Besetzung von Spitzenposten.", "collocates": ["Mehrheit", "Koalition", "Parteien", "Posten"]},
    {"id": "verzoegerung", "term": "Verzögerung", "twin_term": "Ritardi", "fts_query": "verzöger* OR ritard*", "category": "Investigative Journalism", "category_color": "#805ad5", "primary_moral": "Fairness", "sentiment": -0.25, "sample_snippet": "Massive Verzögerungen und Kostensteigerungen bei öffentlichen Bauprojekten belasten den Landeshaushalt.", "collocates": ["Kosten", "Baustelle", "Zeitplan", "Millionen"]},
    {"id": "skandal", "term": "Skandal", "twin_term": "Scandalo", "fts_query": "skandal* OR scandal*", "category": "Investigative Journalism", "category_color": "#805ad5", "primary_moral": "Sanctity / Fairness", "sentiment": -0.55, "sample_snippet": "Enthüllungsberichte bringen Unregelmäßigkeiten bei Ausschreibungsverfahren ans Tageslicht.", "collocates": ["Justiz", "Ermittlungen", "Rücktritt", "Dokumente"]},
]

_BUBBLE_CACHE: Dict[str, List[Dict[str, Any]]] = {}


def get_word_bubbles(corpus: DataService, mode: str = "focus") -> List[Dict[str, Any]]:
    """
    Retrieve word bubble cluster data for the dashboard.
    Cached in memory after initial fast aggregation from SQLite FTS.
    """
    if mode in _BUBBLE_CACHE:
        return _BUBBLE_CACHE[mode]

    seeds = (
        LANGUAGE_GAP_THEMES if mode == "languages"
        else DISCOURSE_THEMES if mode == "discourse"
        else FOCUS_THEMES
    )

    results: List[Dict[str, Any]] = []

    with corpus._get_connection() as conn:
        cursor = conn.cursor()

        for s in seeds:
            q = s["fts_query"]

            # Single aggregated query per seed: yields language, source, and year breakdown
            cursor.execute("""
                SELECT substr(a.publish_date, 1, 4) as yr, a.language, a.source, count(*) as cnt
                FROM articles_fts f
                JOIN articles a ON a.id = f.id
                WHERE articles_fts MATCH ?
                GROUP BY yr, a.language, a.source
            """, (q,))
            rows = cursor.fetchall()

            if not rows:
                continue

            total_count = sum(r[3] for r in rows)
            if total_count == 0:
                continue

            de_count = sum(r[3] for r in rows if r[1] == "de")
            it_count = sum(r[3] for r in rows if r[1] == "it")
            press_count = sum(r[3] for r in rows if "provinz" in (r[2] or "").lower())
            journ_count = total_count - press_count

            de_ratio = round(de_count / total_count, 2)
            it_ratio = round(it_count / total_count, 2)
            journ_ratio = round(journ_count / total_count, 2)
            press_ratio = round(press_count / total_count, 2)

            # Aggregate yearly trend (2016..2025)
            yr_map: Dict[str, int] = {}
            for r in rows:
                yr = str(r[0])
                if "2016" <= yr <= "2025":
                    yr_map[yr] = yr_map.get(yr, 0) + r[3]

            years = [str(y) for y in range(2016, 2026)]
            yearly_trend = [yr_map.get(y, 0) for y in years]

            results.append({
                "id": s["id"],
                "term": s["term"],
                "twin_term": s.get("twin_term"),
                "category": s["category"],
                "category_color": s["category_color"],
                "count": total_count,
                "salience": 0.0,  # Will be normalized below
                "de_ratio": de_ratio,
                "it_ratio": it_ratio,
                "journalism_ratio": journ_ratio,
                "official_press_ratio": press_ratio,
                "primary_moral": s["primary_moral"],
                "sentiment": s["sentiment"],
                "collocates": s["collocates"],
                "sample_snippet": s["sample_snippet"],
                "years": years,
                "yearly_trend": yearly_trend,
            })

    if results:
        # Normalize salience based on log-scale of count
        max_count = max(r["count"] for r in results)
        min_count = min(r["count"] for r in results)
        spread = max(max_count - min_count, 1)

        for r in results:
            # Scale radius fraction between 0.35 and 1.0
            fraction = (r["count"] - min_count) / spread
            r["salience"] = round(0.35 + 0.65 * (fraction ** 0.5), 2)

        # Sort so most prominent bubbles are prioritized
        results.sort(key=lambda x: x["count"], reverse=True)

    _BUBBLE_CACHE[mode] = results
    return results
