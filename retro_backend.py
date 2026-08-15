from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import retro_brain

app = FastAPI(title="Retro AI Backend")


class SystemValueRequest(BaseModel):
    value: int


class QueueRequest(BaseModel):
    label: str
    type: str = "task"
    payload: dict | None = None

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


@app.get("/api/system")
def system_status() -> dict[str, Any]:
    summary = retro_brain.get_system_summary()
    return {
        "os": summary.get("os"),
        "model": summary.get("model"),
        "cwd": summary.get("cwd"),
        "memory_file": summary.get("memory_file"),
        "safe_modes": summary.get("safe_modes", []),
        "brightness": 78,
        "volume": 62,
    }


@app.post("/api/brightness")
def set_brightness(request: SystemValueRequest) -> dict[str, Any]:
    value = max(0, min(100, int(request.value)))
    retro_brain.set_screen_brightness(value)
    return {"brightness": value, "ok": True}


@app.post("/api/volume")
def set_volume(request: SystemValueRequest) -> dict[str, Any]:
    value = max(0, min(100, int(request.value)))
    retro_brain.set_system_volume(value)
    return {"volume": value, "ok": True}


@app.get("/api/queue")
def get_queue() -> dict[str, Any]:
    memory_data = retro_brain.load_memory()
    tasks = memory_data.get("tasks", []) or memory_data.get("task_queue", [])
    return {"items": tasks}


@app.post("/api/queue")
def add_queue_item(request: QueueRequest) -> dict[str, Any]:
    memory_data = retro_brain.load_memory()
    task = retro_brain.enqueue_task(memory_data, request.label, request.type, request.payload or {})
    return {"ok": True, "task": task}


@app.post("/api/queue/run")
def run_queue() -> dict[str, Any]:
    memory_data = retro_brain.load_memory()
    result = retro_brain.execute_queued_tasks(memory_data)
    return {"ok": True, "result": result}


@app.post("/api/queue/clear")
def clear_queue() -> dict[str, Any]:
    memory_data = retro_brain.load_memory()
    memory_data["tasks"] = []
    memory_data["task_queue"] = []
    retro_brain.save_memory(memory_data)
    return {"ok": True, "items": []}


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
