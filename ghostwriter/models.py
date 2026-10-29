"""Data shapes shared by the LLM layer, the database and the API."""

from typing import Literal

from pydantic import BaseModel, Field

# Each mood has its own candle and flame colour on the candle wall (static/style.css, .mood-*).
Mood = Literal["joyful", "nostalgic", "loving", "poignant", "mysterious", "eerie"]


class StoryAnalysis(BaseModel):
    """What Gemma extracts from one transcript.

    The JSON schema of this class is sent to Ollama as the required output format,
    and the same class validates the reply. Field meanings are spelled out in prompts.py.
    """

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1)
    people: list[str]
    places: list[str]
    eras: list[str]
    mood: Mood
    keepsakes: list[str]
    unfinished_business: list[str] = Field(min_length=2, max_length=4)
