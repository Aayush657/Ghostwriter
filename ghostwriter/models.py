"""Data shapes shared by the LLM layer, the database and the API."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

# Each mood has its own candle and flame colour on the candle wall (static/style.css, .mood-*).
Mood = Literal["joyful", "nostalgic", "loving", "poignant", "mysterious", "eerie"]
# One tag: a short phrase, not a sentence. The schema sent to Ollama carries these limits too.
Tag = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
Tags = Annotated[list[Tag], Field(max_length=12)]


class StoryAnalysis(BaseModel):
    """What Gemma extracts from one transcript.

    The JSON schema of this class is sent to Ollama as the required output format,
    and the same class validates the reply. Field meanings are spelled out in prompts.py.
    """

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1)
    people: Tags
    places: Tags
    eras: Tags
    mood: Mood
    keepsakes: Tags
    unfinished_business: list[str] = Field(min_length=2, max_length=4)
