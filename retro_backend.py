from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import retro_brain

app = FastAPI(title="Retro AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    context: list[int] | None = None


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "model": retro_brain.MODEL}


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    message = (request.message or "").strip()
    if not message:
        return {"reply": "Please enter a message for Retro.", "context": None, "model": retro_brain.MODEL}

    memory_data = retro_brain.load_memory()
    agentic_reply = retro_brain.handle_agentic_prompt(message, memory_data)
    if agentic_reply:
        retro_brain.remember_history(memory_data, message)
        return {"reply": agentic_reply, "context": None, "model": retro_brain.MODEL}

    conversation_context = retro_brain.build_context(message, request.context, memory_data)
    raw_response, new_context = retro_brain.ask_retro(message, conversation_context)

    cleaned = retro_brain.parse_and_act(raw_response)
    final_reply = cleaned if cleaned else raw_response

    retro_brain.remember_history(memory_data, message)
    return {"reply": final_reply, "context": new_context, "model": retro_brain.MODEL}
