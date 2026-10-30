"""Browser smoke test: the real page in Chrome, driven by Playwright, against the real server.

Whisper and Gemma are faked (fast and repeatable); ffmpeg/ffprobe, SQLite, the routes and every line
of the page run for real. Chrome's fake microphone plays a WAV file, so recording is tested too.
Skipped when Playwright or Google Chrome isn't installed (pip install -r requirements-dev.txt).
"""

from __future__ import annotations

import re
import socket
import threading
import time
from pathlib import Path

import pytest

from ghostwriter import db, embed, llm, transcribe
from ghostwriter.api import main
from ghostwriter.models import StoryAnalysis
from ghostwriter.selfcheck import Check
from ghostwriter.transcribe import Quality, Transcript
from tests.conftest import wav_bytes

playwright = pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")

SPOOKY = re.compile(r"ghost(?!writer)|archivist|s[ée]ance|candle|haunt|spirit|summon|\bfog\b|laid to rest|my dear|"
                    r"skull|lantern|grave|flame", re.IGNORECASE)
# Every piece of interface text that is visible (or a placeholder, tooltip or label), but not the
# stories themselves (.content) or the app's name.
UI_TEXT = """() => {
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t = walker.nextNode(); t; t = walker.nextNode()) {
    const e = t.parentElement;
    if (!t.textContent.trim() || e.closest('.content, h1, script, .scene') || !e.checkVisibility()) continue;
    out.push(t.textContent.trim());
  }
  for (const e of document.querySelectorAll('[placeholder], [title], [aria-label]')) {
    if (e.closest('.content, h1, .scene') || !e.checkVisibility()) continue;
    out.push(e.placeholder || '', e.title || '', e.getAttribute('aria-label') || '');
  }
  return out.filter(Boolean);
}"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def site(data_dir, monkeypatch, tmp_path):
    """The app on a free port, with Whisper and Gemma replaced by quick stand-ins."""
    def fake_transcribe(wav, names=()):
        return Transcript("My grandmother cooked kadhi in a brass pot in Lucknow.", 0.5,
                          Quality(-0.3, 0.01, 1.4, 0.0, scripts=["LATIN"]))

    def fake_analyse(transcript, answering=None, written=False):
        return StoryAnalysis(title="Grandmother's Kadhi", summary="Your grandmother cooked kadhi in Lucknow.",
                             people=["Nani (grandmother)"], places=["Lucknow"], eras=["1980s"], mood="nostalgic",
                             keepsakes=["brass pot"],
                             unfinished_business=[] if answering else ["What did the kitchen smell like?",
                                                                       "Who else ate the kadhi?"])

    def fake_stream(messages, temperature=0.7):
        ids = re.findall(r"\[S(\d+)\]", messages[-1]["content"])
        if ids:  # a Seance: cite the first story, with the marker split across pieces as Gemma does
            yield from ["Your grandmother cooked kadhi ", "[S", ids[0], "]", " in a brass pot."]
        else:
            yield from ["The pot ", "whispered ", "at midnight."]

    monkeypatch.setattr(transcribe, "transcribe", fake_transcribe)
    monkeypatch.setattr(transcribe, "warm_up", lambda: None)
    monkeypatch.setattr(llm, "analyse_story", fake_analyse)
    monkeypatch.setattr(llm, "unanswered_questions", lambda t, analysis, answering=None: analysis.unfinished_business)
    monkeypatch.setattr(llm, "write_note", lambda story: "What a warm memory. The brass pot still glows.")
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    monkeypatch.setattr(llm, "warm_up", lambda: None)
    # "Which relative was a good cook?" shares no word with the story: the meaning search finds it.
    monkeypatch.setattr(embed, "similar", lambda q: [(s["id"], 0.5) for s in db.list_stories() if not s["parent_id"]][:1])
    monkeypatch.setattr(main.selfcheck, "run_checks", lambda ping=False: [Check("Python", True, "3.11")])

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    wav = tmp_path / "story.wav"
    wav.write_bytes(wav_bytes(2.0))
    yield f"http://127.0.0.1:{port}", wav
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def browser(site):
    _, wav = site
    with playwright.sync_playwright() as p:
        try:
            chrome = p.chromium.launch(channel="chrome", args=[
                "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-audio-capture={wav}"])
        except Exception as exc:  # no Google Chrome on this machine
            pytest.skip(f"Chrome not available: {exc}")
        yield chrome
        chrome.close()


def story_count(page) -> int:
    return page.evaluate("fetch('/api/stories').then(r => r.json()).then(s => s.filter(x => !x.parent_id).length)")


def test_every_main_flow_in_the_browser(site, browser, tmp_path):
    base, wav = site
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    # 1. The wall loads without errors.
    page.goto(base + "/#/")
    page.wait_for_selector("#wall .empty")
    assert errors == []

    # 2. Upload a recording; it is written down and becomes ready.
    page.set_input_files("#upload-form input[type=file]", str(wav))
    page.click("#upload-form button[type=submit]")
    page.wait_for_url(re.compile(r"#/story/\d+$"))
    page.wait_for_selector("#story h2:has-text(\"Grandmother's Kadhi\")", timeout=20_000)
    story_id = int(page.url.rsplit("/", 1)[1])

    # 3. Rename: spaces only is refused by the browser; a real title is saved.
    page.click("#story .title-row button:has-text('Rename')")
    page.fill("#story .inline-edit input", "   ")
    page.click("#story .inline-edit button[type=submit]")
    assert page.eval_on_selector("#story .inline-edit input", "e => e.validity.valueMissing")
    page.fill("#story .inline-edit input", "Nani's Kadhi")
    page.click("#story .inline-edit button[type=submit]")
    page.wait_for_selector("#story h2:has-text(\"Nani's Kadhi\")")

    # 4. Tags: add a place and change the mood.
    page.click("#story button:has-text('Edit tags')")
    page.fill("#story .tags-edit input[placeholder='Add places']", "Pune")
    page.select_option("#story .tags-edit select", "joyful")
    page.click("#story .tags-edit button[type=submit]")
    page.wait_for_selector("#story dl.details dd:has-text('Pune')")
    assert "joyful" in page.inner_text("#story dl.details")

    # 5. Answer a follow-up question with a file: the answer appears inside this story.
    with page.expect_file_chooser() as chooser:
        page.click("#story .questions li >> nth=0 >> button:has-text('or upload a file')")
    chooser.value.set_files(str(wav))
    page.wait_for_selector("#story .questions .added:has-text('Your grandmother cooked kadhi in Lucknow.')", timeout=20_000)
    assert "Added later" in page.inner_text("#story .questions .added")

    # 6. The Seance answers a paraphrased question, with a numbered citation and no raw marker.
    page.click("#story a.back")
    page.wait_for_selector("#seance-form")
    assert page.locator("#wall .candle").count() == 1  # the answer is not a candle of its own
    page.fill("#seance-form input", "Which relative was a good cook?")
    page.click("#seance-form button")
    page.wait_for_selector("#seance-sources a")
    answer = page.inner_text("#seance-answer")
    assert "[S" not in answer and page.inner_text("#seance-answer sup.cite a") == "[1]"
    assert page.get_attribute("#seance-answer sup.cite a", "href") == f"#/story/{story_id}"

    # 7. The memory book opens with the story and its answer.
    with page.expect_popup() as popup:
        page.click("a.book-link")
    book = popup.value
    book.wait_for_load_state()
    text = book.inner_text("body")
    assert "The Memory Book" in text and "Nani's Kadhi" in text and "Added later" in text
    book.close()

    # 8. A file that isn't audio: an inline error, and no story is created.
    notes = tmp_path / "notes.mp3"
    notes.write_text("shopping list, not a recording")
    page.set_input_files("#upload-form input[type=file]", str(notes))
    page.click("#upload-form button[type=submit]")
    page.wait_for_selector("#upload-status .error")
    assert "isn't a recording" in page.inner_text("#upload-status")
    assert story_count(page) == 1

    # Write a story: autocorrect fixes typos and capitalises sentences and quoted speech as you type,
    # Backspace undoes a fix, the draft survives a reload, and the story is read without a listening
    # step. Then a question is answered in writing.
    page.click("#write-text")
    page.keyboard.type("teh lantern dissapeared ")
    assert page.input_value("#write-text") == "The lantern disappeared "
    assert "dissapeared" in page.inner_text("#write-fixed")
    page.keyboard.type("i ")
    page.keyboard.press("Backspace")  # put the writer's own "i" back
    assert page.input_value("#write-text") == "The lantern disappeared i"
    page.keyboard.type(' swear it was real. maya said "dont tell." ')
    written = 'The lantern disappeared i swear it was real. Maya said "Don\'t tell." '
    assert page.input_value("#write-text") == written
    assert page.inner_text("#write-count").startswith("12 words")
    page.reload()
    page.wait_for_selector("#wall .candle")
    assert page.input_value("#write-text") == written  # the draft was kept
    page.click("#write-form button[type=submit]")
    page.wait_for_url(re.compile(r"#/story/\d+$"))
    page.wait_for_selector("#story h2:has-text(\"Grandmother's Kadhi\")", timeout=20_000)
    assert page.inner_text("#story details.words summary") == "The words as you wrote them"
    assert page.locator("#story audio").count() == 0
    page.click("#story .questions li >> nth=0 >> button:has-text('or write it')")
    page.fill("#story .answer-write textarea", "It smelled like wood smoke and rain.")
    page.click("#story .answer-write button[type=submit]")
    page.wait_for_selector("#story .questions .added:has-text('Added later')", timeout=20_000)
    assert story_count(page) == 2
    page.click("#story a.back")
    page.wait_for_selector("#write-text")
    assert page.input_value("#write-text") == ""  # sent, so the draft is gone

    # The microphone: waiting, recording with a clock, Stop, and the story is sent.
    page.click("#recorder button")
    page.wait_for_selector("#recorder .recording")
    page.wait_for_timeout(1500)
    assert page.inner_text("#recorder .elapsed") != "0:00"
    page.click("#recorder button:has-text('Stop')")
    page.wait_for_url(re.compile(r"#/story/\d+$"))
    page.wait_for_selector("#story h2:has-text(\"Grandmother's Kadhi\")", timeout=20_000)
    assert story_count(page) == 3

    # 9. Delete from the bottom of the story: Undo brings it back; deleting again leaves nothing behind.
    recorded = page.url.rsplit("/", 1)[1]
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.click("#story button.danger")
    page.click("#confirm-ok")
    page.wait_for_url(re.compile(r"#/$"))
    page.click("#toast button:has-text('Undo')")
    page.wait_for_url(re.compile(rf"#/story/{recorded}$"))
    page.wait_for_selector("#story button.danger")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.click("#story button.danger")
    page.click("#confirm-ok")
    page.wait_for_url(re.compile(r"#/$"))
    page.wait_for_function("document.querySelectorAll('#wall .candle').length === 2")
    assert page.evaluate("scrollY") == 0
    assert page.evaluate("document.querySelector('#story').hidden && document.querySelector('#story').children.length === 0")
    assert page.locator("#story input[type=file], #story h2").count() == 0

    # 10. Plain mode: nothing spooky is left in the interface.
    page.click("#plain-toggle")
    page.wait_for_selector("body.plain")
    for route in ("#/", f"#/story/{story_id}"):
        page.evaluate(f"location.hash = '{route}'")
        page.wait_for_timeout(600)
        spooky = [t for t in page.evaluate(UI_TEXT) if SPOOKY.search(t)]
        assert spooky == [], f"{route}: {spooky}"

    assert [e for e in errors if "Failed to load resource" not in e] == []  # the 415 above is expected


def test_microphone_problems_are_explained(site, browser):
    base, _ = site
    context = browser.new_context()
    # A browser that is still asking: the page says so, and Cancel goes back.
    context.add_init_script("navigator.mediaDevices.getUserMedia = () => new Promise(() => {});")
    page = context.new_page()
    page.goto(base + "/#/")
    page.click("#recorder button")
    assert "Waiting for microphone permission" in page.inner_text("#recorder")
    page.click("#recorder button:has-text('Cancel')")
    page.wait_for_selector("#recorder button.record")
    context.close()

    for name, says in [("NotAllowedError", "allow the microphone"), ("NotFoundError", "No microphone was found"),
                       ("NotReadableError", "busy in another program")]:
        context = browser.new_context()
        context.add_init_script(f"navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('x', '{name}'));")
        page = context.new_page()
        page.goto(base + "/#/")
        page.click("#recorder button")
        page.wait_for_selector("#recorder .error")
        assert says in page.inner_text("#recorder .error")
        context.close()


OVERLAP_CHECK = (Path(__file__).parent / "overlap.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("width", [390, 1280])
def test_decorations_never_cover_text(site, browser, width):
    """The moon, cobweb, crystal ball, graveyard, speech bubble and whisper stay off every line of text,
    on the wall and on a story, scrolled from top to bottom."""
    base, wav = site
    page = browser.new_page(viewport={"width": width, "height": 800}, reduced_motion="reduce")
    page.goto(base + "/#/")
    page.set_input_files("#upload-form input[type=file]", str(wav))
    page.click("#upload-form button[type=submit]")
    page.wait_for_selector("#story .questions", timeout=20_000)
    story = page.url
    problems = set()
    for url in (base + "/#/", story):
        page.goto(url)
        page.wait_for_timeout(800)
        page.click("#mascot")  # the speech bubble is showing
        page.evaluate("""() => { const w = document.querySelector('#whisper'); w.hidden = false;
            w.innerHTML = '<p>"हमने वो notebook आज तक किसी को नहीं दिखाई, और न कभी दिखाएँगे."</p><p class=from>from a story</p>'; }""")
        for y in range(0, page.evaluate("document.documentElement.scrollHeight"), 300):
            page.evaluate(f"window.scrollTo(0, {y})")
            problems.update(page.evaluate(OVERLAP_CHECK))
    assert sorted(problems) == []
