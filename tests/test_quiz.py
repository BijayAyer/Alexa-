from cram.quiz import answer_is_correct, fallback_questions


def test_fallback_questions_blank_terms_from_notes():
    questions = fallback_questions(
        ["Photosynthesis lets plants convert sunlight into glucose. Chlorophyll absorbs light."], 2
    )

    assert len(questions) == 2
    assert "____" in questions[0]["question"]
    assert questions[0]["answer"] == "photosynthesis"
    assert questions[1]["answer"] == "chlorophyll"


def test_fallback_questions_uses_short_sentences_from_notes():
    questions = fallback_questions(["sun and rain"], 3)

    assert questions == [{"question": "sun and ____", "answer": "rain"}]


def test_answer_matching_uses_half_of_expected_keywords():
    assert answer_is_correct("plants make sugar", "plants make sugar")
    assert answer_is_correct("plants make", "plants make sugar")
    assert not answer_is_correct("water", "plants make sugar")