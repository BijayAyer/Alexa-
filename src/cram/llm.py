"""Optional OpenAI-compatible chat completion helper."""

import json
import os
import re
from typing import Any

import httpx


def complete(system: str, prompt: str) -> str | None:
    if os.getenv("LLM_PROVIDER", "local").lower() != "local":
        return None

    url = os.getenv("LOCAL_LLM_URL", "http://localhost:1234/v1").rstrip("/")
    model = os.getenv("LOCAL_LLM_MODEL", "local-model")
    headers = {}
    api_key = os.getenv("LOCAL_LLM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = httpx.post(
            f"{url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
            },
            timeout=30,
        )
        response.raise_for_status()
        text = response.json()["choices"][0]["message"]["content"]
        return text.strip() if isinstance(text, str) and text.strip() else None
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None


def complete_json(system: str, prompt: str) -> Any | None:
    for attempt in range(2):
        request = prompt if attempt == 0 else f"{prompt}\nReturn only valid JSON, with no code fences."
        text = complete(system, request)
        if text is None:
            continue
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            continue
    return None