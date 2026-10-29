"""Tidying the tags Gemma extracts, so the candle wall's filters and the search stay useful.

Gemma is asked for named places and real times; this checks it did, because a small model
sometimes returns "the corridor" as a place or "the past" as an era. People are never merged:
"grandmother" and "Nani (grandmother)" may be two different people, so only the storyteller
renames or merges them (from the story page).
"""

from __future__ import annotations

import re

from ghostwriter.models import StoryAnalysis

# A year (1942, 2004), a decade ("1980s", "'80s", "eighties"), or a stage of life.
_YEAR_OR_DECADE = re.compile(
    r"\b(1[5-9]\d\d|20\d\d)s?\b|'\d0s\b|\b\d0s\b|\b(twenties|thirties|forties|fifties|sixties|seventies|eighties|nineties)\b",
    re.IGNORECASE,
)
LIFE_STAGES = {"childhood", "infancy", "boyhood", "girlhood", "youth", "teens", "teenage", "school",
               "college", "university", "wedding", "marriage", "honeymoon", "pregnancy", "retirement",
               "old age", "adulthood", "student", "army", "war"}
_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
# Places that are only a kind of place, even when Gemma capitalises them.
GENERIC_PLACES = {"corridor", "temple", "room", "house", "home", "school", "kitchen", "road", "street", "market",
                  "village", "city", "town", "hostel", "hospital", "station", "garden", "terrace", "verandah",
                  "courtyard", "field", "church", "mosque", "office", "park", "river", "beach", "forest", "hill",
                  "car", "train", "bus", "shop", "hall", "classroom", "library", "bedroom", "roof", "well"}


def is_named_place(place: str) -> bool:
    """'Lucknow', "Nani's house", 'St. Mary's School': yes. 'the corridor', 'Temple', 'room 307': no."""
    name = _LEADING_ARTICLE.sub("", place.strip())
    if any(ch.isalpha() and not ch.isascii() for ch in name):
        return True  # Devanagari and other scripts have no capitals; trust Gemma there
    if re.sub(r"\s*\d+$", "", name).lower() in GENERIC_PLACES:
        return False
    return any(w[:1].isupper() for w in name.split()) or "'s " in name


def is_real_time(era: str) -> bool:
    """'1990s', 'Diwali 2004', 'childhood', 'college days': yes. 'the past', 'night', 'December': no."""
    lower = era.lower()
    return bool(_YEAR_OR_DECADE.search(era)) or any(re.search(rf"\b{stage}\b", lower) for stage in LIFE_STAGES)


def _unique(values: list[str]) -> list[str]:
    """Strip and drop exact repeats (ignoring case), keeping the first spelling."""
    seen, out = set(), []
    for value in (v.strip() for v in values):
        if value and value.lower() not in seen:
            seen.add(value.lower())
            out.append(value)
    return out


def clean(analysis: StoryAnalysis) -> StoryAnalysis:
    return analysis.model_copy(update={
        "people": _unique(analysis.people),
        "places": [p for p in _unique(analysis.places) if is_named_place(p)],
        "eras": [e for e in _unique(analysis.eras) if is_real_time(e)],
        "keepsakes": _unique(analysis.keepsakes),
    })
