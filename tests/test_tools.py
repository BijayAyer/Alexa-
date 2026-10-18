import pytest

from cram import db
from cram import server


@pytest.fixture(autouse=True)
def local_database(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "cram.db")
    db.init_db()


def test_add_notes_topics_and_summary():
    assert server.add_notes("Photosynthesis", "Plants use sunlight to make glucose. Chlorophyll absorbs light.") == "I saved your notes on Photosynthesis."
    assert server.list_topics() == "Your topics are Photosynthesis (1 notes)."
    assert "sunlight" in server.summarize_topic("photosynthesis")


def test_quiz_fallback_repeat_answers_and_review():
    server.add_notes("Photosynthesis", "Photosynthesis uses sunlight to produce glucose. Chlorophyll absorbs light.")
    first = server.start_quiz("photosynthesis", 2)
    assert first.startswith("Question 1 of 2:")
    assert server.repeat_question() == first

    current = db.get_active_question()
    second = server.answer_question(current["answer"])
    assert second.startswith("Correct. Your answer has the key idea. Question 2 of 2:")

    current = db.get_active_question()
    final = server.answer_question("nothing related")
    assert final.endswith("You got 1 of 2.")
    assert db.get_active_question() is None
    assert "Review" in server.what_to_review()


def test_tools_respond_safely_when_inputs_or_history_are_missing():
    assert server.add_notes(" ", " ") == "Please give me a topic and some notes to save."
    assert "saved topics" in server.list_topics().lower()
    assert "active quiz" in server.answer_question("answer").lower()
    assert "quiz history" in server.what_to_review().lower()


def test_short_model_quiz_is_filled_from_notes(monkeypatch):
    server.add_notes("Biology", "Plants absorb sunlight. Chlorophyll captures light. Glucose stores energy.")
    monkeypatch.setattr(server.llm, "complete_json", lambda *_: [
        {"question": "What stores energy?", "answer": "glucose"}
    ])

    assert server.start_quiz("Biology", 3).startswith("Question 1 of 3:")
    assert db.quiz_score(db.get_active_question()["session_id"])[1] == 3