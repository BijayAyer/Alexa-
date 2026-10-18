"""Small FastAPI app that simulates Alexa+ with a Strands agent."""

import asyncio
from io import BytesIO
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pypdf import PdfReader
from strands import Agent
from strands.models.openai import OpenAIModel
from strands.tools.mcp import MCPClient

from cram import db

STATIC = Path(__file__).parent / "static"
SYSTEM_PROMPT = (
    "You are a simulated Alexa+ voice assistant helping a student. Always use the Cram tools for study requests. "
    "To save notes use add_notes. To list topics use list_topics. For a summary use summarize_topic. "
    "To answer study questions from saved notes use answer_from_notes. "
    "To start a quiz use start_quiz. When the user is answering a quiz question use answer_question. "
    "To hear the question again use repeat_question. For what to study next use what_to_review. "
    "Keep spoken replies short and plain, no markdown."
)
TOOLS = {
    "notes": "add_notes",
    "study_answer": "answer_from_notes",
    "quiz_answer": "answer_question",
    "topics": "list_topics",
    "summary": "summarize_topic",
    "quiz": "start_quiz",
    "repeat": "repeat_question",
    "review": "what_to_review",
}


class ChatRequest(BaseModel):
    message: str


def obvious_tool(message: str) -> str | None:
    text = message.casefold()
    if any(word in text for word in ("add notes", "save notes", "remember this", "my notes are")):
        return TOOLS["notes"]
    if any(word in text for word in ("list topics", "what topics", "my topics")):
        return TOOLS["topics"]
    if any(word in text for word in ("summarize", "summary", "sum up")):
        return TOOLS["summary"]
    if any(word in text for word in ("quiz", "test me", "quiz me")):
        return TOOLS["quiz"]
    if any(word in text for word in ("repeat", "say that again", "hear the question")):
        return TOOLS["repeat"]
    if any(word in text for word in ("review", "study next", "what should i study")):
        return TOOLS["review"]
    if "?" in text or text.startswith(("what is", "what are", "how does", "how do", "why does", "why do", "explain", "tell me about")):
        return TOOLS["study_answer"]
    if db.get_active_question() and any(
        text.startswith(prefix) for prefix in ("the answer is", "i think", "it's", "it is")
    ):
        return TOOLS["quiz_answer"]
    return None


def used_tools(messages: list[dict], start: int) -> list[str]:
    names = []
    for message in messages[start:]:
        for block in message.get("content", []):
            tool_use = block.get("toolUse") if isinstance(block, dict) else None
            if tool_use and tool_use.get("name") and tool_use["name"] not in names:
                names.append(tool_use["name"])
    return names


def successful_tool_reply(messages: list[dict], start: int, tool_names: list[str]) -> str | None:
    calls = set()
    for message in messages[start:]:
        for block in message.get("content", []):
            tool_use = block.get("toolUse") if isinstance(block, dict) else None
            if tool_use and tool_use.get("name") in tool_names:
                calls.add(tool_use.get("toolUseId"))
    for message in messages[start:]:
        for block in message.get("content", []):
            result = block.get("toolResult") if isinstance(block, dict) else None
            if result and result.get("toolUseId") in calls and result.get("status") == "success":
                texts = [item["text"] for item in result.get("content", []) if isinstance(item, dict) and item.get("text")]
                if texts:
                    return " ".join(texts)
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    api_key = os.getenv("CRAM_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    client = MCPClient(url=os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp"), headers=headers)
    app.state.model = None
    app.state.tools = []
    app.state.conversation = []
    app.state.chat_lock = asyncio.Lock()
    try:
        await asyncio.to_thread(client.start)
        tools = client.list_tools_sync()
        url = os.getenv("LOCAL_LLM_URL", "http://localhost:1234/v1").rstrip("/")
        model_id = os.getenv("LOCAL_LLM_MODEL", "local-model")
        client_args = {"base_url": url, "api_key": os.getenv("LOCAL_LLM_API_KEY", "local-only")}
        app.state.model = OpenAIModel(client_args=client_args, model_id=model_id)
        app.state.tools = tools
        app.state.mcp_client = client
        yield
    except Exception:
        yield
    finally:
        if getattr(app.state, "mcp_client", None) is client:
            await asyncio.to_thread(client.stop, None, None, None)


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(f"PDFs can have up to {MAX_PDF_PAGES} pages.")
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        raise ValueError("No selectable text was found. Scanned PDFs need OCR before upload.")
    return text[:100_000]


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/materials/text")
async def save_material_text(topic: str = Form(), text: str = Form()) -> dict[str, str]:
    topic, text = topic.strip(), text.strip()
    if not topic or not text:
        raise HTTPException(status_code=422, detail="Enter a topic and study notes.")
    if len(text) > 100_000:
        raise HTTPException(status_code=413, detail="Study notes must be under 100,000 characters.")
    try:
        db.add_note(topic, text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not save these study notes.") from exc
    return {"status": "saved", "topic": topic}


@app.post("/api/materials/pdf")
async def upload_material_pdf(topic: str = Form(), file: UploadFile = File()) -> dict[str, str]:
    topic = topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="Enter a topic for this PDF.")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Choose a PDF file.")
    pdf_bytes = await file.read(MAX_PDF_BYTES + 1)
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDFs must be 10 MB or smaller.")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="This file does not look like a valid PDF.")
    try:
        text = extract_pdf_text(pdf_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=415, detail="The PDF could not be read. It may be damaged or password-protected.") from exc
    try:
        db.add_note(topic, text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Could not save this PDF's text.") from exc
    return {"status": "saved", "topic": topic, "filename": file.filename}


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> dict[str, str | list[str]]:
    message = payload.message.strip()
    if not message:
        return {"reply": "Type a message first.", "tools_used": []}
    model = getattr(app.state, "model", None)
    if model is None:
        return {"reply": "The study assistant is not connected yet. Start the Cram server and local model, then reload this page.", "tools_used": []}

    async with app.state.chat_lock:
        conversation = app.state.conversation
        start = len(conversation)
        try:
            expected = obvious_tool(message)
            tools = app.state.tools
            if expected:
                tools = app.state.mcp_client.list_tools_sync(tool_filters={"allowed": [expected]})
            agent = Agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT, messages=conversation)
            result = await asyncio.to_thread(agent, message)
            called = used_tools(conversation, start)
            if expected and expected not in called:
                reminder = f"Use the {expected} tool now for the student's request. Do not answer without using it."
                result = await asyncio.to_thread(agent, reminder)
                called.extend(name for name in used_tools(conversation, start) if name not in called)
            reply = str(result).strip()
            if not reply:
                reply = "I didn't get a spoken reply. Please try that again."
            reply = re.sub(r"\s+", " ", reply)
            return {"reply": reply, "tools_used": called}
        except Exception:
            called = used_tools(conversation, start)
            reply = successful_tool_reply(conversation, start, called)
            if reply:
                return {"reply": reply, "tools_used": called}
            return {
                "reply": "The local model could not finish a reply. Check that its OpenAI-compatible URL and model are correct.",
                "tools_used": called,
            }


@app.get("/api/state")
async def state() -> dict[str, list[dict]]:
    return {"topics": db.list_topics(), "last_quiz_scores": db.last_quiz_scores()}


@app.post("/api/reset")
async def reset() -> dict[str, str]:
    async with app.state.chat_lock:
        app.state.conversation.clear()
    return {"status": "ok"}


def main() -> None:
    uvicorn.run("cram.web:app", host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()