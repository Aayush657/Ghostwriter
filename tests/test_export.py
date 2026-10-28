"""Memory book tests: finished stories only, oldest first, escaped, and readable without a server."""

from fastapi.testclient import TestClient

from ghostwriter import db, export
from ghostwriter.api import main
from tests.test_search import add_story


def test_book_holds_finished_stories_oldest_first(data_dir):
    first = add_story("The Clock That Listened", "tick")
    second = add_story("Room 307", "pages turning")
    db.update_story(add_story("Still Thinking", "..."), status="thinking")
    db.update_story(second, retelling="Gather close.")
    with db.connect() as con:  # make the order unambiguous
        con.execute("UPDATE stories SET created_at = '2026-01-01 00:00:00' WHERE id = ?", (first,))

    book = export.memory_book_html()

    assert book.index("The Clock That Listened") < book.index("Room 307")
    assert "Still Thinking" not in book
    assert "A haunted retelling" in book and "Gather close." in book
    assert "2 memories" in book


def test_book_escapes_text_and_needs_nothing_from_outside(data_dir):
    add_story("<script>alert(1)</script>", "a story with <b>tags</b>")
    book = export.memory_book_html()
    assert "<script>alert" not in book and "&lt;script&gt;" in book
    assert "data:font/ttf;base64," in book  # fonts travel inside the file
    assert "http://" not in book and "https://" not in book


def test_book_route_serves_html(data_dir, monkeypatch):
    add_story("The Clock That Listened", "tick")
    monkeypatch.setattr(main.selfcheck, "run_checks", lambda: [])
    with TestClient(main.app) as client:
        resp = client.get("/api/book")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
