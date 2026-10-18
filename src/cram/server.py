"""Cram's MCP tools and Streamable HTTP server."""

import os
import re
import secrets

import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from cram import db, llm
from cram.quiz import answer_is_correct, fallback_questions

load_dotenv()
mcp = FastMCP("Cram", host="0.0.0.0", port=8000)


def _short(text: str, max_words: int = 60) -> str:
    plain = re.sub(r"[*_`#]+", "", " ".join(line.strip(" -*") for line in text.splitlines()))
    return " ".join(plain.split()[:max_words])


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _canonical_topic(topic: str) -> str:
    topic = topic.strip()
    return next(
        (str(item["topic"]) for item in db.list_topics() if str(item["topic"]).casefold() == topic.casefold()),
        topic,
    )


def _current_question_text(question: dict, total: int) -> str:
    return f"Question {question['position']} of {total}: {question['question']}"


@mcp.tool()
def add_notes(topic: str, text: str) -> str:
    """Save a student's notes when they share new study material for a topic."""
    topic, text = topic.strip(), text.strip()
    if not topic or not text:
        return "Please give me a topic and some notes to save."
    try:
        db.add_note(topic, text)
        return _short(f"I saved your notes on {topic}.")
    except Exception:
        return "I couldn't save those notes just now. Please try again."


@mcp.tool()
def list_topics() -> str:
    """List topics with saved notes when a student asks what they have studied."""
    try:
        topics = db.list_topics()
        if not topics:
            return "You don't have any saved topics yet."
        entries = [f"{item['topic']} ({item['note_count']} notes)" for item in topics]
        return _short("Your topics are " + ", ".join(entries) + ".")
    except Exception:
        return "I couldn't load your topics just now. Please try again."


@mcp.tool()
def summarize_topic(topic: str) -> str:
    """Give a short spoken summary of saved notes when a student asks for a topic recap."""
    try:
        notes = db.get_notes(topic.strip())
        if not notes:
            return _short(f"I don't have any notes on {topic.strip()} yet.")
        source = "\n".join(notes)
        summary = llm.complete(
            "Summarize only the supplied study notes in at most four short spoken sentences. Use plain language, no markdown, and add no facts.",
            source,
        )
        return _short(" ".join(_sentences(summary)[:4])) if summary else _short(" ".join(_sentences(source)[:4]))
    except Exception:
        return "I couldn't summarize those notes just now. Please try again."


@mcp.tool()
def start_quiz(topic: str, num_questions: int = 3) -> str:
    """Start a one-question-at-a-time quiz using only the student's saved notes on a topic."""
    try:
        topic = _canonical_topic(topic)
        notes = db.get_notes(topic)
        if not notes:
            return _short(f"I don't have notes on {topic} yet. Add some notes before we start a quiz.")
        count = max(1, min(num_questions, 10))
        source = "\n".join(notes)
        generated = llm.complete_json(
            "Write quiz questions using only the supplied notes. Return a JSON array of objects with string keys question and answer. Do not add outside facts.",
            f"Make {count} short questions from these notes:\n{source}",
        )
        questions = []
        if isinstance(generated, list):
            for item in generated:
                if isinstance(item, dict) and isinstance(item.get("question"), str) and isinstance(item.get("answer"), str):
                    question, answer = item["question"].strip(), item["answer"].strip()
                    if question and answer:
                        questions.append({"question": question, "answer": answer})
                if len(questions) == count:
                    break
        if not questions:
            questions = fallback_questions(notes, count)
        if not questions:
            return "I couldn't make a quiz from those notes. Try adding a few complete sentences."
        db.create_quiz(topic, questions)
        return _short(_current_question_text(db.get_active_question(), len(questions)))
    except Exception:
        return "I couldn't start a quiz just now. Please try again."


@mcp.tool()
def answer_question(answer: str) -> str:
    """Check the student's reply to the current quiz question and continue the quiz."""
    try:
        current = db.get_active_question()
        if not current:
            return "There isn't an active quiz. Ask me to start a quiz on one of your topics."
        response = llm.complete_json(
            "Compare the student's response with the expected answer. Return JSON with verdict set to correct, partly, or incorrect, and a brief one-sentence reason.",
            f"Expected answer: {current['answer']}\nStudent response: {answer.strip()}",
        )
        verdict = response.get("verdict") if isinstance(response, dict) else None
        reason = response.get("reason") if isinstance(response, dict) else None
        if verdict not in {"correct", "partly", "incorrect"} or not isinstance(reason, str) or not reason.strip():
            correct = answer_is_correct(answer, current["answer"])
            verdict = "correct" if correct else "incorrect"
            reason = "Your answer has the key idea." if correct else f"The key idea is {current['answer']}."
        else:
            correct = verdict == "correct"
            reason = _sentences(reason)[0]
        db.save_answer(current["question_id"], answer.strip(), correct)
        feedback = _short(f"{verdict.capitalize()}. {reason}", 30)
        next_question = db.get_active_question()
        if next_question:
            total = db.quiz_score(current["session_id"])[1]
            return _short(f"{feedback} {_current_question_text(next_question, total)}", 80)
        db.finish_quiz(current["session_id"])
        correct_count, total = db.quiz_score(current["session_id"])
        return _short(f"{feedback} You got {correct_count} of {total}.")
    except Exception:
        return "I couldn't check that answer just now. Please try again."


@mcp.tool()
def repeat_question() -> str:
    """Repeat the current quiz question when a student asks to hear it again."""
    try:
        current = db.get_active_question()
        if not current:
            return "There isn't an active quiz to repeat. Ask me to start a quiz first."
        total = db.quiz_score(current["session_id"])[1]
        return _short(_current_question_text(current, total))
    except Exception:
        return "I couldn't repeat that question just now. Please try again."


@mcp.tool()
def what_to_review() -> str:
    """Suggest the topic to review based on the student's lowest quiz accuracy."""
    try:
        topics = db.quiz_accuracy()
        if not topics:
            return "You don't have quiz history yet. Try taking a quiz on one of your topics."
        weakest = topics[0]
        percent = round(float(weakest["accuracy"]) * 100)
        return _short(
            f"Review {weakest['topic']} next. You got {weakest['correct']} of {weakest['answered']} answers right, or {percent} percent."
        )
    except Exception:
        return "I couldn't check your quiz history just now. Please try again."


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, api_key: str):
        self.app = app
        self.api_key = api_key.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] in {"/mcp", "/mcp/"}:
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"authorization", b"")
            if not secrets.compare_digest(supplied, b"Bearer " + self.api_key):
                response = JSONResponse({"detail": "Unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def main() -> None:
    db.init_db()
    app: ASGIApp = mcp.streamable_http_app()
    api_key = os.getenv("CRAM_API_KEY")
    if api_key:
        app = BearerAuthMiddleware(app, api_key)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()