"""Shared fixtures. Every test gets its own empty data folder, so real data is never touched."""

import pytest

from ghostwriter import db
from ghostwriter.config import settings
from ghostwriter.models import StoryAnalysis


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    db.init_db()
    return settings.data_dir


@pytest.fixture
def analysis():
    return StoryAnalysis(
        title="The Lamp on Dadi's Terrace",
        summary="Dadi lit a brass lamp every Diwali. One year it went out by itself.",
        people=["Dadi (grandmother)"],
        places=["Allahabad"],
        eras=["1990s"],
        mood="eerie",
        keepsakes=["brass lamp"],
        unfinished_business=["What happened to the brass lamp?", "Who was on the terrace that night?"],
    )
