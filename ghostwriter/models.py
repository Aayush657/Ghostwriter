"""Data shapes shared by the LLM layer, the database and the API."""

import re
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, Field, StringConstraints, field_validator

# Each mood has its own candle and flame colour on the candle wall (static/js/app.js MOODS, style.css .mood-*).
Mood = Literal["joyful", "nostalgic", "loving", "poignant", "mysterious", "eerie"]
MOODS: tuple[str, ...] = get_args(Mood)
# Words a small model (or an older version of this app) used instead; anything else becomes the fallback.
MOOD_SYNONYMS = {
    "happy": "joyful", "cheerful": "joyful", "fun": "joyful", "funny": "joyful", "playful": "joyful",
    "excited": "joyful", "sad": "poignant", "melancholy": "poignant", "bittersweet": "poignant",
    "grief": "poignant", "sorrowful": "poignant", "love": "loving", "tender": "loving", "warm": "loving",
    "affectionate": "loving", "scary": "eerie", "creepy": "eerie", "spooky": "eerie", "haunting": "eerie",
    "frightening": "eerie", "strange": "mysterious", "mystery": "mysterious", "curious": "mysterious",
    "puzzling": "mysterious", "confused": "mysterious", "uncertain": "mysterious", "calm": "nostalgic",
    "peaceful": "nostalgic", "wistful": "nostalgic", "reflective": "nostalgic", "sentimental": "nostalgic",
}
FALLBACK_MOOD = "nostalgic"


def normalise_mood(mood: object) -> str:
    word = str(mood or "").strip().lower()
    return word if word in MOODS else MOOD_SYNONYMS.get(word, FALLBACK_MOOD)


# One tag: a short phrase, not a sentence. The schema sent to Ollama carries these limits too.
Tag = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
Tags = Annotated[list[Tag], Field(max_length=12)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

# The assistant talking about its input instead of about the memory ("The transcript provided contains...").
META_TEXT = re.compile(r"\b(the )?transcri(pt|ption)s?\b|\bas an ai\b|\blanguage model\b|\bprovided text\b|"
                       r"\btext provided\b|\bthe speaker\b|\bthe (audio|recording)\b", re.IGNORECASE)


class StoryAnalysis(BaseModel):
    """What Gemma extracts from one transcript.

    The JSON schema of this class is sent to Ollama as the required output format,
    and the same class validates the reply. Field meanings are spelled out in prompts.py.
    """

    title: Title
    summary: str = Field(min_length=1, max_length=1200)
    people: Tags
    places: Tags
    eras: Tags
    mood: Mood
    keepsakes: Tags
    # 2-4 for a new story; none for an answer to an earlier question (prompts.py says which).
    unfinished_business: list[str] = Field(max_length=4)
    # Some words were unclear, so the summary leaves them out. The story page says so.
    uncertain: bool = False

    @field_validator("mood", mode="before")
    @classmethod
    def _known_mood(cls, mood: object) -> str:
        return normalise_mood(mood)

    @field_validator("title", "summary")
    @classmethod
    def _about_the_memory(cls, text: str) -> str:
        if META_TEXT.search(text):
            raise ValueError("talks about the transcript or the assistant instead of the memory; "
                             "describe only what happened, speaking to the storyteller as 'you'")
        return text

    @field_validator("unfinished_business")
    @classmethod
    def _questions_about_the_memory(cls, questions: list[str]) -> list[str]:
        if any(META_TEXT.search(q) for q in questions):
            raise ValueError("a question mentions the transcript; ask about the memory itself")
        return [q.strip() for q in questions if q.strip()]
