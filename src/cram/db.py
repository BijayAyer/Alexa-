"""Small SQLite helpers for notes and quiz history."""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DB_PATH = Path(os.getenv("CRAM_DB_PATH", "cram.db"))


@contextmanager
def _connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path or DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(db_path: Path | None = None) -> None:
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connection(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                id INTEGER PRIMARY KEY,
                topic TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('active', 'finished')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS quiz_questions (
                id INTEGER PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
                position INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                user_answer TEXT,
                correct INTEGER,
                UNIQUE(session_id, position)
            );
            """
        )


def add_note(topic: str, text: str, db_path: Path | None = None) -> int:
    with _connection(db_path) as connection:
        existing = connection.execute(
            "SELECT topic FROM notes WHERE topic = ? COLLATE NOCASE LIMIT 1", (topic,)
        ).fetchone()
        topic = existing["topic"] if existing else topic
        cursor = connection.execute(
            "INSERT INTO notes (topic, text, created_at) VALUES (?, ?, ?)",
            (topic, text, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        return int(cursor.lastrowid)


def list_topics(db_path: Path | None = None) -> list[dict[str, str | int]]:
    with _connection(db_path) as connection:
        rows = connection.execute(
            "SELECT topic, COUNT(*) AS note_count FROM notes GROUP BY topic ORDER BY topic COLLATE NOCASE"
        ).fetchall()
    return [dict(row) for row in rows]


def get_notes(topic: str, db_path: Path | None = None) -> list[str]:
    with _connection(db_path) as connection:
        rows = connection.execute(
            "SELECT text FROM notes WHERE topic = ? COLLATE NOCASE ORDER BY id", (topic,)
        ).fetchall()
    return [row["text"] for row in rows]


def create_quiz(topic: str, questions: list[dict[str, str]], db_path: Path | None = None) -> int:
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connection(db_path) as connection:
        connection.execute("UPDATE quiz_sessions SET status = 'finished' WHERE status = 'active'")
        cursor = connection.execute(
            "INSERT INTO quiz_sessions (topic, status, created_at) VALUES (?, 'active', ?)",
            (topic, created_at),
        )
        session_id = int(cursor.lastrowid)
        connection.executemany(
            "INSERT INTO quiz_questions (session_id, position, question, answer) VALUES (?, ?, ?, ?)",
            [(session_id, position, item["question"], item["answer"])
             for position, item in enumerate(questions, start=1)],
        )
    return session_id


def get_active_question(db_path: Path | None = None) -> dict | None:
    with _connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT s.id AS session_id, s.topic, q.id AS question_id,
                   q.position, q.question, q.answer
            FROM quiz_sessions AS s
            JOIN quiz_questions AS q ON q.session_id = s.id
            WHERE s.status = 'active' AND q.correct IS NULL
            ORDER BY q.position LIMIT 1
            """
        ).fetchone()
    return dict(row) if row else None


def save_answer(question_id: int, user_answer: str, correct: bool, db_path: Path | None = None) -> None:
    with _connection(db_path) as connection:
        connection.execute(
            "UPDATE quiz_questions SET user_answer = ?, correct = ? WHERE id = ?",
            (user_answer, int(correct), question_id),
        )


def finish_quiz(session_id: int, db_path: Path | None = None) -> None:
    with _connection(db_path) as connection:
        connection.execute("UPDATE quiz_sessions SET status = 'finished' WHERE id = ?", (session_id,))


def quiz_accuracy(db_path: Path | None = None) -> list[dict[str, str | int | float]]:
    with _connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT s.topic, COUNT(q.id) AS answered,
                   SUM(CASE WHEN q.correct = 1 THEN 1 ELSE 0 END) AS correct
            FROM quiz_sessions AS s
            JOIN quiz_questions AS q ON q.session_id = s.id
            WHERE q.correct IS NOT NULL
            GROUP BY s.topic
            """
        ).fetchall()
    results = [
        {"topic": row["topic"], "answered": row["answered"], "correct": row["correct"],
         "accuracy": row["correct"] / row["answered"]}
        for row in rows
    ]
    return sorted(results, key=lambda item: (item["accuracy"], str(item["topic"]).casefold()))


def last_quiz_scores(db_path: Path | None = None) -> list[dict[str, str | int]]:
    with _connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT s.topic, s.id AS session_id,
                   SUM(CASE WHEN q.correct = 1 THEN 1 ELSE 0 END) AS correct,
                   COUNT(q.id) AS total
            FROM quiz_sessions AS s
            JOIN quiz_questions AS q ON q.session_id = s.id
            WHERE s.status = 'finished' AND q.correct IS NOT NULL
            GROUP BY s.id
            ORDER BY s.created_at DESC, s.id DESC
            """
        ).fetchall()
    latest: dict[str, dict[str, str | int]] = {}
    for row in rows:
        latest.setdefault(row["topic"], {
            "topic": row["topic"], "correct": row["correct"], "total": row["total"]
        })
    return list(latest.values())


def quiz_score(session_id: int, db_path: Path | None = None) -> tuple[int, int]:
    with _connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT COALESCE(SUM(CASE WHEN correct = 1 THEN 1 ELSE 0 END), 0) AS correct,
                   COUNT(*) AS total
            FROM quiz_questions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    return row["correct"], row["total"]