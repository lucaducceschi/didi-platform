# DIDI Beta Performance Benchmarks

Measured on local development machine (Apple Silicon, macOS, SQLite 3.x WAL mode, PostgreSQL 16 on OrbStack).

## 1. Corpus Search Latencies (Full 113,823 Article Index)
Average across 5 consecutive runs with warm cache:

| Query Type | Query Expression | Match Count | Avg Latency | Min Latency | Target Latency | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Broad FTS Search** | `Autonomie` (trilingual concept) | 14,618 | 73.86 ms | 72.74 ms | $< 200\text{ ms}$ | ✅ PASS |
| **Medium Multi-term** | `Brenner Transit` | 369 | 6.55 ms | 5.58 ms | $< 100\text{ ms}$ | ✅ PASS |
| **Narrow Specific** | `Scuola bilingue` | 24 | 1.30 ms | 1.17 ms | $< 50\text{ ms}$ | ✅ PASS |
| **Exact Quoted Phrase** | `"Südtiroler Volkspartei"` | 626 | 3.20 ms | 2.85 ms | $< 50\text{ ms}$ | ✅ PASS |
| **Filtered Search** | `Autonomie` + `source='tageszeitung'` | 12,410 | 68.20 ms | 65.40 ms | $< 200\text{ ms}$ | ✅ PASS |
| **Date-Bounded Search** | `Autonomie` + `2023-01-01` to `2023-12-31` | 1,415 | 32.10 ms | 30.50 ms | $< 100\text{ ms}$ | ✅ PASS |

## 2. Quantitative & Aggregation Benchmarks
| Operation | Dataset Scope | Latency | Target | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Corpus Summary API** | 113,823 articles, all facets | 4.2 ms (cached) / 120 ms (cold) | $< 300\text{ ms}$ | ✅ PASS |
| **Longitudinal Timeline (2016–2026)** | 113,823 articles, monthly buckets | 145 ms (cold) / 2.1 ms (cached) | $< 500\text{ ms}$ | ✅ PASS |
| **Moral Radar & Emotions** | 12,220 precomputed + fallback | 65 ms | $< 300\text{ ms}$ | ✅ PASS |
| **Comparison Grid** | 32 codes $\times$ 4 partitions | 82 ms | $< 500\text{ ms}$ | ✅ PASS |
| **Word Bubble Index Aggregation** | 15 seed themes $\times$ 10 years | 650 ms (cold) / $< 0.1$ ms (cached) | $< 1000\text{ ms}$ | ✅ PASS |
| **Single Token Lookup (didi_words.db)** | 1 article (avg 350 tokens) | 1.8 ms | $< 10\text{ ms}$ | ✅ PASS |

