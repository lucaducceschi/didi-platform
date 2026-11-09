"""
Near-duplicate detection (64-bit SimHash over word 4-shingles) for DIDI collectors.
Enables tracing syndicated wire copy and press releases without dropping articles.
"""
from __future__ import annotations

import hashlib
import re
from typing import List

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _h64(s: str) -> int:
    return int.from_bytes(hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest(), "big")


def simhash(text: str, k: int = 4) -> int:
    toks = _TOKEN.findall(text.lower())
    if len(toks) < k:
        toks = toks + [""] * (k - len(toks))
    v = [0] * 64
    for i in range(len(toks) - k + 1):
        h = _h64(" ".join(toks[i:i + k]))
        for b in range(64):
            v[b] += 1 if (h >> b) & 1 else -1
    out = 0
    for b in range(64):
        if v[b] > 0:
            out |= 1 << b
    return out


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def bands(h: int, n: int = 4) -> List[int]:
    """Split into n 16-bit bands for candidate lookup."""
    width = 64 // n
    return [(h >> (i * width)) & ((1 << width) - 1) for i in range(n)]


def content_hash(text: str) -> str:
    norm = " ".join(_TOKEN.findall(text.lower()))
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def to_signed(h: int) -> int:
    return h - (1 << 64) if h >= (1 << 63) else h


def to_unsigned(h: int) -> int:
    return h + (1 << 64) if h < 0 else h

