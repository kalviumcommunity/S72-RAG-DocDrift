"""
Text-Offset Locator Service
============================
Fuzzy string matching and character-offset locator for finding the exact
start/end positions of cited chunk excerpts inside the raw source document.
"""

import re
from difflib import SequenceMatcher
from typing import Optional, Tuple, List, Dict, Any


def _normalize(text: str) -> str:
    """Collapse whitespace for fuzzy comparison without mutating offsets."""
    return re.sub(r'\s+', ' ', text).strip()


def find_exact_offset(
    source: str,
    excerpt: str,
) -> Optional[Tuple[int, int]]:
    """
    Attempts an exact substring search for `excerpt` inside `source`.
    Returns (start_char, end_char) or None.
    """
    idx = source.find(excerpt)
    if idx != -1:
        return idx, idx + len(excerpt)
    return None


def find_fuzzy_offset(
    source: str,
    excerpt: str,
    min_ratio: float = 0.75,
    window_size: Optional[int] = None,
) -> Optional[Tuple[int, int]]:
    """
    Sliding-window fuzzy match using SequenceMatcher.
    Scans `source` in overlapping windows of `window_size` characters,
    returning the (start_char, end_char) of the best-matching window
    whose similarity ratio meets `min_ratio`.

    Args:
        source:      Full raw document text.
        excerpt:     Chunk text to locate.
        min_ratio:   Minimum SequenceMatcher ratio (0.0-1.0) to accept.
        window_size: Comparison window; defaults to 2× len(excerpt).

    Returns:
        (start_char, end_char) of the best match, or None if no match found.
    """
    if not excerpt or not source:
        return None

    excerpt_len = len(excerpt)
    ws = window_size or min(excerpt_len * 2, len(source))
    step = max(1, excerpt_len // 4)

    best_ratio = 0.0
    best_start = -1
    best_end = -1

    norm_excerpt = _normalize(excerpt)

    for i in range(0, len(source) - excerpt_len + 1, step):
        window = source[i: i + ws]
        ratio = SequenceMatcher(None, _normalize(window[: excerpt_len + 50]), norm_excerpt).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_start = i
            best_end = min(i + excerpt_len, len(source))

    if best_ratio >= min_ratio and best_start != -1:
        return best_start, best_end
    return None


def locate_excerpt_offsets(
    source: str,
    excerpt: str,
    min_fuzzy_ratio: float = 0.75,
) -> Dict[str, Any]:
    """
    Main entry point: tries exact match first, then fuzzy.
    Returns a location report dict with character and line offsets.

    Returns:
        {
          "found":          bool,
          "method":         "exact" | "fuzzy" | "none",
          "start_char":     int | None,
          "end_char":       int | None,
          "start_line":     int | None,
          "end_line":       int | None,
          "match_ratio":    float,
          "matched_text":   str | None,
        }
    """
    result: Dict[str, Any] = {
        "found": False,
        "method": "none",
        "start_char": None,
        "end_char": None,
        "start_line": None,
        "end_line": None,
        "match_ratio": 0.0,
        "matched_text": None,
    }

    if not excerpt or not source:
        return result

    # 1. Exact match
    offsets = find_exact_offset(source, excerpt)
    if offsets:
        start, end = offsets
        result.update({
            "found": True,
            "method": "exact",
            "start_char": start,
            "end_char": end,
            "match_ratio": 1.0,
            "matched_text": source[start:end],
        })
    else:
        # 2. Fuzzy match
        offsets = find_fuzzy_offset(source, excerpt, min_ratio=min_fuzzy_ratio)
        if offsets:
            start, end = offsets
            matched = source[start:end]
            ratio = SequenceMatcher(None, _normalize(matched), _normalize(excerpt)).ratio()
            result.update({
                "found": True,
                "method": "fuzzy",
                "start_char": start,
                "end_char": end,
                "match_ratio": round(ratio, 4),
                "matched_text": matched,
            })
        else:
            return result

    # Compute line numbers from char offsets
    prefix = source[: result["start_char"]]
    result["start_line"] = prefix.count("\n") + 1
    result["end_line"] = result["start_line"] + source[result["start_char"]: result["end_char"]].count("\n")

    return result


def annotate_document_lines(raw: str) -> List[Dict[str, Any]]:
    """
    Splits a raw document into a numbered-line structure with section detection.
    Returns a list of dicts:
        [{"line_number": 1, "content": "...", "section_header": "..." | None}, ...]
    """
    lines = raw.splitlines()
    annotated: List[Dict[str, Any]] = []
    current_section: Optional[str] = None

    for i, line in enumerate(lines, start=1):
        # Detect Markdown headings
        heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if heading_match:
            current_section = heading_match.group(2).strip()

        annotated.append({
            "line_number":    i,
            "content":        line,
            "section_header": current_section,
        })

    return annotated


def build_line_index(source: str) -> List[Tuple[int, int]]:
    """
    Returns a list of (start_char, end_char) for every line in `source`,
    enabling O(log n) binary-search conversion from char offset → line number.
    """
    index: List[Tuple[int, int]] = []
    pos = 0
    for line in source.splitlines(keepends=True):
        end = pos + len(line)
        index.append((pos, end))
        pos = end
    return index
