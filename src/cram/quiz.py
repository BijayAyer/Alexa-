"""Quiz question generation fallbacks and answer matching."""

import re


def fallback_questions(notes: list[str], num_questions: int) -> list[dict[str, str]]:
    questions = []
    for note in notes:
        for sentence in re.split(r"(?<=[.!?])\s+", note.strip()):
            candidates = re.findall(r"\b[\w'-]{4,}\b", sentence)
            if not candidates:
                continue
            answer = max(candidates, key=len)
            question = re.sub(rf"\b{re.escape(answer)}\b", "____", sentence, count=1, flags=re.IGNORECASE)
            questions.append({"question": question, "answer": answer.strip("'-").casefold()})
            if len(questions) >= num_questions:
                return questions
    return questions


def answer_is_correct(user_answer: str, expected_answer: str) -> bool:
    expected = set(re.findall(r"[a-z0-9]+", expected_answer.lower()))
    given = set(re.findall(r"[a-z0-9]+", user_answer.lower()))
    return bool(expected) and len(expected & given) / len(expected) >= 0.5