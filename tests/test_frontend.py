"""The page and the server agree: one mood list, and every mood has its candle design."""

import re

from ghostwriter.api.main import STATIC_DIR
from ghostwriter.models import MOODS

APP = (STATIC_DIR / "js" / "app.js").read_text(encoding="utf-8")
CSS = (STATIC_DIR / "style.css").read_text(encoding="utf-8")


def test_the_page_uses_the_servers_mood_list():
    block = re.search(r"const MOODS = \{(.*?)\n\};", APP, re.S).group(1)
    assert tuple(re.findall(r"^\s+(\w+): \{", block, re.M)) == MOODS


def test_every_mood_has_a_candle_and_a_flame_colour():
    for mood in MOODS:
        assert re.search(rf"\.mood-{mood} \{{ --core:", CSS), mood  # flame colours
        assert f".mood-{mood} .wax" in CSS, mood  # its own candle design


def test_plain_mode_has_every_word_the_page_uses():
    spooky, plain = (re.search(rf"  {name}: \{{(.*?)\n  \}},", APP, re.S).group(1) for name in ("spooky", "plain"))
    keys = lambda block: set(re.findall(r"^    (\w+):", block, re.M))  # noqa: E731
    assert keys(spooky) == keys(plain)
