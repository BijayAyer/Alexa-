from cram import db


def test_notes_and_topics(tmp_path):
    path = tmp_path / "cram.db"
    db.init_db(path)
    db.add_note("Biology", "Plants use light.", path)
    db.add_note("Biology", "Chlorophyll absorbs light.", path)

    assert db.get_notes("Biology", path) == ["Plants use light.", "Chlorophyll absorbs light."]
    assert db.list_topics(path) == [{"topic": "Biology", "note_count": 2}]


def test_quiz_lifecycle_and_review_scores(tmp_path):
    path = tmp_path / "cram.db"
    db.init_db(path)
    session_id = db.create_quiz("Biology", [
        {"question": "What absorbs light?", "answer": "chlorophyll"},
        {"question": "What do plants use?", "answer": "light"},
    ], path)

    first = db.get_active_question(path)
    assert first["position"] == 1
    db.save_answer(first["question_id"], "chlorophyll", True, path)
    second = db.get_active_question(path)
    assert second["position"] == 2
    db.save_answer(second["question_id"], "darkness", False, path)
    db.finish_quiz(session_id, path)

    assert db.get_active_question(path) is None
    assert db.quiz_accuracy(path) == [{"topic": "Biology", "answered": 2, "correct": 1, "accuracy": 0.5}]
    assert db.last_quiz_scores(path) == [{"topic": "Biology", "correct": 1, "total": 2}]


def test_new_quiz_finishes_previous_active_session(tmp_path):
    path = tmp_path / "cram.db"
    db.init_db(path)
    db.create_quiz("Biology", [{"question": "Q?", "answer": "A"}], path)
    db.create_quiz("History", [{"question": "Q?", "answer": "A"}], path)

    assert db.get_active_question(path)["topic"] == "History"