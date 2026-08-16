import requests
import json
import subprocess
import platform
import re
import os
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

try:
    import screen_brightness_control as sbc
except ImportError:
    sbc = None

# Optional Audio control for Windows using pycaw
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    WINDOWS_AUDIO = True
except ImportError:
    WINDOWS_AUDIO = False
    AudioUtilities = None
    IAudioEndpointVolume = None
    CLSCTX_ALL = None

# ==========================================
# 1. CONFIGURATION
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODELS_URL = "http://localhost:11434/api/tags"
MODEL = os.getenv("RETRO_MODEL", "llama3")
MEMORY_PATH = os.path.join(os.path.expanduser("~"), ".retro_memory.json")
SAFE_APPS = {
    "notepad",
    "calc",
    "mspaint",
    "cmd",
    "powershell",
    "chrome",
    "firefox",
    "msedge",
    "explorer",
    "spotify",
    "vlc",
    "word",
    "excel",
    "outlook",
    "teams",
    "code",
    "notepad++",
}
DANGEROUS_PATTERNS = [
    "delete",
    "remove",
    "format",
    "shutdown",
    "restart",
    "install",
    "uninstall",
    "rm ",
    "del ",
    "rmdir",
    "mklink",
]
CONFIRMATION_REQUIRED_PATTERNS = [
    "shutdown",
    "restart",
    "install",
    "uninstall",
    "delete",
    "format",
    "remove",
    "rm ",
    "del ",
    "rmdir",
    "mklink",
]

# The System Prompt is Retro's personality and rulebook.
SYSTEM_PROMPT = """
You are Retro, an advanced local AI assistant controlling the user's device.
You can execute special commands using specific tags:
- Applications: <CMD>app_name</CMD>
- Brightness: <CMD>BRIGHTNESS:50</CMD> (expects a percentage 0-100)
- Volume: <CMD>VOLUME:70</CMD> (expects a percentage 0-100)
- File Search: <CMD>SEARCH:filename</CMD>
- Read File: <CMD>READ_FILE:path_to_file</CMD>
- Write File: <CMD>WRITE_FILE:path_to_file|content_here</CMD>
- List Directory: <CMD>LIST_DIR:path_to_directory</CMD>

You have the ability to control the user's computer.
If the user asks you to open an application, open a website, or perform a system task, you MUST output a command tag in this exact format: <CMD>command here</CMD>.

Examples:
- User: "Open Notepad." -> You output: "Opening Notepad now. <CMD>notepad</CMD>"
- User: "Open Calculator." -> You output: "Right away. <CMD>calc</CMD>"
- User: "Who are you?" -> You output: "I am Retro, your local AI system." (No command tag needed).
- If the user asks about your creator, developer, maker, or who created you, answer exactly: "I was developed by Amish." (No command tag needed).

Do not explain how to open apps, just use the <CMD> tag. Keep your responses concise and modern.
"""

# ==========================================
# 2. PERSISTENT MEMORY + CONTEXT ENGINE
# ==========================================
def load_memory():
    """Loads Retro's memory file if it exists."""
    if not os.path.exists(MEMORY_PATH):
        return {"preferences": {}, "history": [], "files": [], "tasks": []}
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"preferences": {}, "history": [], "files": [], "tasks": []}
        return {
            "preferences": data.get("preferences", {}),
            "history": data.get("history", []),
            "files": data.get("files", []),
            "tasks": data.get("tasks", []),
        }
    except Exception:
        return {"preferences": {}, "history": [], "files": [], "tasks": []}


def save_memory(memory_data):
    """Saves Retro's memory to disk."""
    try:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, indent=2)
    except Exception as e:
        print(f"[WARN]: Could not save memory: {e}")


def remember_fact(memory_data, key, value):
    """Stores a preference or fact in memory."""
    memory_data.setdefault("preferences", {})
    memory_data["preferences"][key] = value
    save_memory(memory_data)


def remember_history(memory_data, item):
    """Stores a short history entry."""
    memory_data.setdefault("history", [])
    memory_data["history"].append({
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "item": item,
    })
    if len(memory_data["history"]) > 25:
        memory_data["history"] = memory_data["history"][-25:]
    save_memory(memory_data)


def build_context(user_input, existing_context=None, memory_data=None):
    """Builds a richer task context using memory and recent state."""
    if memory_data is None:
        memory_data = load_memory()

    context = {
        "current_task": user_input,
        "user_preferences": memory_data.get("preferences", {}),
        "recent_history": memory_data.get("history", [])[-5:],
        "known_files": memory_data.get("files", []),
        "active_project_folder": os.getcwd(),
        "system_status": {
            "os": platform.system(),
            "model": MODEL,
        },
    }

    if isinstance(existing_context, dict):
        context.update(existing_context)

    return context


def normalize_ollama_context(context):
    """Ollama expects a numeric context array, not the local dict-based app context."""
    if isinstance(context, list):
        return context
    if isinstance(context, tuple):
        return list(context)
    return None


def recognize_multi_step_task(prompt):
    """Detects task chains like 'find X, read Y, and summarize it'."""
    task_markers = [
        " and ", " then ", " then do ", " first ", " next ", " afterwards ",
        " summarize ", " review ", " find ", " compare ", " search ", " open ",
        " look for ", " before ", " after that ", " read ", " write ", " create ",
        " browse ", " go to "
    ]
    lower = prompt.lower()
    if any(marker in lower for marker in task_markers) and len(prompt.split()) > 3:
        return True

    # Small compatibility add-on for chained commands like 'find X then read it'.
    if re.search(r"\b(?:search|find|look for|locate|read|open|write|create)\b.*\b(?:and|then)\b.*\b(?:search|find|look for|locate|read|open|write|create)\b", lower):
        return True
    return False


def extract_app_name(prompt):
    """Parses common app names from natural language prompts."""
    lower = (prompt or "").lower()
    aliases = {
        "notepad": ["notepad"],
        "calc": ["calculator", "calc"],
        "cmd": ["command prompt", "cmd"],
        "powershell": ["powershell"],
        "msedge": ["edge", "microsoft edge", "msedge"],
        "chrome": ["chrome", "google chrome"],
        "firefox": ["firefox"],
        "spotify": ["spotify"],
        "code": ["vscode", "visual studio code", "code"],
        "word": ["word"],
        "excel": ["excel"],
        "outlook": ["outlook"],
        "explorer": ["file explorer", "explorer"],
    }
    for app_name, names in aliases.items():
        if any(name in lower for name in names):
            return app_name

    match = re.search(r"(?:open|launch|start|run)\s+(?:the\s+)?([a-z0-9 .\-]+)", lower)
    if match:
        candidate = match.group(1).strip()
        candidate = candidate.replace(" file explorer", "explorer")
        return candidate if candidate else ""
    return ""


def parse_numeric_level(prompt, default=50):
    """Pulls a 0-100 value from user prompts such as 'set volume to 70%' or 'brightness 25'."""
    text = prompt or ""
    match = re.search(r"(\d{1,3})\s*%?", text)
    if match:
        value = int(match.group(1))
        return max(0, min(100, value))
    return default


def parse_direct_task(prompt):
    """Parses common agent commands from natural-language input without replacing the original flow."""
    user_text = (prompt or "").strip()
    lower = user_text.lower()

    url_direct = re.search(r"\b(?:https?://|www\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\S*\b", user_text, re.IGNORECASE)
    if url_direct and re.match(r"^(open|launch|start|run)\b", lower):
        return {"action": "open_url", "url": url_direct.group(0)}

    if re.match(r"^(open|launch|start|run)\b", lower):
        app_name = extract_app_name(user_text)
        if app_name:
            if app_name in ["https", "http"]:
                return {"action": "open_url", "url": user_text.split(None, 1)[1].strip() if len(user_text.split(None, 1)) > 1 else ""}
            return {"action": "open_app", "command": app_name}

    if any(term in lower for term in ["set brightness", "brightness", "screen brightness"]):
        return {"action": "set_brightness", "level": parse_numeric_level(user_text, 50)}

    if any(term in lower for term in ["set volume", "volume", "sound level"]):
        return {"action": "set_volume", "level": parse_numeric_level(user_text, 50)}

    search_match = re.search(
        r"(?:can\s+you\s+)?(?:please\s+)?(?:search|find|look\s+for|locate)\s+(?:for\s+)?(.+?)(?:\s+(?:for\s+me|for\s+us|please)|$|[?!.]|,|\band\b)",
        user_text,
        re.IGNORECASE
    )
    if search_match:
        query = search_match.group(1).strip().strip('"\'')
        if query and len(query.split()) <= 12:
            return {"action": "search_files", "query": query}

    if any(term in lower for term in ["search for ", "find ", "look for ", "locate "]):
        return {"action": "search_files", "query": extract_search_query(user_text)}

    if any(term in lower for term in ["read file ", "read the file ", "open file ", "view file ", "open the file "]):
        match = re.search(r"(?:read|open|view)\s+(?:the\s+)?(?:file\s+)?(.+)", user_text, re.IGNORECASE)
        if match:
            return {"action": "read_file", "path": match.group(1).strip().strip('"\'')}

    read_file_match = re.search(r"(?:read|open|view)\s+(?:the\s+)?([\w\- ./\\]+\.[A-Za-z0-9]+)", user_text, re.IGNORECASE)
    if read_file_match:
        return {"action": "read_file", "path": read_file_match.group(1).strip().strip('"\'')}

    if any(term in lower for term in ["write file ", "create file ", "make file "]):
        match = re.search(r"(?:write|create|make)\s+(?:the\s+)?(?:file\s+)?(?:named\s+)?([\w\- ./]+\.[a-zA-Z0-9]+)\s*(?:with\s+|to\s+)?(.+)?", user_text, re.IGNORECASE)
        if match:
            path = match.group(1).strip().strip('"\'')
            content = (match.group(2) or "").strip()
            return {"action": "write_file", "path": path, "content": content}

    if any(term in lower for term in ["list directory", "list dir", "show directory", "show files in"]):
        match = re.search(r"(?:in|for|at)\s+(.+)", user_text, re.IGNORECASE)
        directory = match.group(1).strip().strip('"\'') if match else os.getcwd()
        return {"action": "list_dir", "path": directory}

    if any(term in lower for term in ["open website", "open url", "go to "]):
        match = re.search(r"(?:go to|open website|open url)\s+(https?://\S+|www\.\S+|[A-Za-z0-9.-]+\.[A-Za-z]{2,}\S*)", user_text, re.IGNORECASE)
        if match:
            return {"action": "open_url", "url": match.group(1)}

    url_match = re.search(r"\b(?:https?://|www\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\S*\b", user_text, re.IGNORECASE)
    if url_match:
        return {"action": "open_url", "url": url_match.group(0)}

    return None


def extract_search_query(prompt):
    """Extracts the main subject from a natural-language search request."""
    text = (prompt or "").strip()
    lower = text.lower()

    patterns = [
        r"(?:can\s+you\s+)?(?:please\s+)?(?:search|find|look\s+for|locate)\s+(?:for\s+)?(.+?)(?:\s+(?:for\s+me|for\s+us|please)|$|[?!.]|,|\band\b)",
        r"(?:search\s+for|find|look\s+for|locate)\s+(.+?)(?:\s+(?:for\s+me|for\s+us|please)|$|[?!.]|,|\band\b)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            query = match.group(1).strip().strip('"\'')
            if query:
                return query

    for marker in ["search for ", "find ", "look for ", "locate "]:
        idx = lower.find(marker)
        if idx != -1:
            remainder = text[idx + len(marker):]
            for splitter in [" and ", " then ", " to "]:
                if splitter in remainder.lower():
                    split_idx = remainder.lower().find(splitter)
                    remainder = remainder[:split_idx]
                    break
            return remainder.strip(" .?")

    if "about" in lower:
        idx = lower.find("about ") + len("about ")
        remainder = text[idx:]
        for splitter in [" and ", " then ", " to "]:
            if splitter in remainder.lower():
                split_idx = remainder.lower().find(splitter)
                remainder = remainder[:split_idx]
                break
        return remainder.strip(" .?")

    if re.search(r"\b(?:search|find|look for|locate)\b", lower):
        return text

    return text.strip(" .? ")


def plan_task(prompt):
    """Creates a structured plan for multi-step requests."""
    lower = prompt.lower()
    steps = []

    if any(word in lower for word in ["find ", "search ", "look for ", "locate "]):
        steps.append({
            "action": "search_files",
            "label": "search for relevant files or information",
            "query": extract_search_query(prompt),
        })

    if any(word in lower for word in ["read ", "open file", "open the file", "view "]):
        steps.append({
            "action": "read_file",
            "label": "read the most relevant file",
            "path": "",
        })

    if any(word in lower for word in ["write ", "create file", "make file", "save to file"]):
        steps.append({
            "action": "write_file",
            "label": "write the requested content to a file",
            "path": "",
            "content": "",
        })

    if any(word in lower for word in ["summarize", "summary", "review"]):
        steps.append({
            "action": "summarize",
            "label": "summarize the result",
        })

    app_name = extract_app_name(prompt)
    if app_name:
        steps.append({
            "action": "open_app",
            "label": "open the requested application",
            "command": app_name,
        })

    if "brightness" in lower:
        steps.append({
            "action": "set_brightness",
            "label": "adjust brightness",
            "level": parse_numeric_level(prompt, 50),
        })

    if "volume" in lower:
        steps.append({
            "action": "set_volume",
            "label": "adjust volume",
            "level": parse_numeric_level(prompt, 50),
        })

    if "website" in lower or "url" in lower or "go to " in lower:
        steps.append({
            "action": "open_url",
            "label": "open the requested website",
            "url": "",
        })

    if re.search(r"\b(?:search|find|look for|locate|read|open|write|create)\b.*\b(?:and|then)\b.*\b(?:search|find|look for|locate|read|open|write|create)\b", lower):
        if not steps:
            steps.append({"action": "respond", "label": "handle the user request with the main agent flow"})

    if not steps:
        steps = [{"action": "respond", "label": "handle the user request with the main agent flow"}]

    return steps


def execute_multi_step_task(prompt, memory_data):
    """Executes a step-by-step plan for a complex request."""
    steps = plan_task(prompt)
    if not steps or steps[0].get("action") == "respond":
        return None

    results = []
    search_hits = []

    for step in steps:
        action = step.get("action")

        if action == "search_files":
            query = step.get("query") or extract_search_query(prompt)
            search_hits = search_local_files(query)
            results.append(f"Search for '{query}' returned {len(search_hits)} result(s).")

        elif action == "read_file":
            path = step.get("path") or (search_hits[0] if search_hits else os.getcwd())
            content = read_text_file(path)
            if isinstance(content, str):
                results.append(f"Read file: {path}")
                results.append(content[:400])

        elif action == "open_app":
            command = step.get("command")
            if command:
                execute_system_command(command)
                results.append(f"Opened: {command}")

        elif action == "set_brightness":
            level = step.get("level", 50)
            set_screen_brightness(level)
            results.append(f"Brightness adjusted to {level}%.")

        elif action == "set_volume":
            level = step.get("level", 50)
            set_system_volume(level)
            results.append(f"Volume adjusted to {level}%.")

        elif action == "summarize":
            context_text = "\n".join(str(item) for item in results if item)
            summary_prompt = (
                f"User request: {prompt}\n\nRelevant findings:\n{context_text}\n\n"
                "Give a concise summary of the results and what was done."
            )
            summary, _ = ask_retro(summary_prompt, build_context(prompt, None, memory_data))
            return summary

    if not results:
        return None

    return "I completed the task in this order: " + "; ".join(str(item) for item in results if item)


# ==========================================
# 3. SYSTEM CONTROL ENGINE (The Hands)
# ==========================================
def is_safe_command(command):
    """Checks whether a command is allowed or requires confirmation."""
    lowered = command.lower()
    if any(item in lowered for item in CONFIRMATION_REQUIRED_PATTERNS):
        return False
    return True


def confirm_action(action_description):
    """Prompts the user to confirm an action that could be risky."""
    try:
        answer = input(f"[CONFIRM] {action_description} (y/N): ").strip().lower()
        return answer in ["y", "yes"]
    except (EOFError, KeyboardInterrupt):
        print("\n[CONFIRM] Action cancelled.")
        return False


def execute_system_command(command):
    """Executes a command using OS-specific launch logic."""
    os_name = platform.system()
    command = (command or "").strip()

    if not command:
        print("[ERROR]: Empty command received.")
        return False

    if not is_safe_command(command):
        print(f"[WARN]: Command requires confirmation before execution: {command}")
        if not confirm_action("Execute potentially risky command"):
            print("[CANCELLED]: Command not executed.")
            return False

    print(f"\n[RETRO SYSTEM EXECUTING]: {command}")

    try:
        if os_name == "Windows":
            if re.match(r"^(https?://|www\.)", command, re.IGNORECASE):
                subprocess.Popen(["cmd", "/c", "start", "", command], shell=False)
            elif command.lower().endswith((".exe", ".bat", ".cmd")):
                subprocess.Popen([command], shell=False)
            else:
                subprocess.Popen(["cmd", "/c", command], shell=False)
            return True

        elif os_name == "Darwin":
            if re.match(r"^(https?://|www\.)", command, re.IGNORECASE):
                subprocess.Popen(["open", command], shell=False)
            else:
                subprocess.Popen(["open", "-a", command], shell=False)
            return True

        elif os_name == "Linux":
            if re.match(r"^(https?://|www\.)", command, re.IGNORECASE):
                subprocess.Popen(["xdg-open", command], shell=False)
            else:
                try:
                    subprocess.Popen(["xdg-open", command], shell=False)
                except OSError:
                    subprocess.Popen(command, shell=True)
            return True

        else:
            print("Unsupported OS for direct commands.")
            return False

    except Exception as e:
        print(f"[ERROR]: Failed to execute {command}. Reason: {e}")
        return False


def set_system_volume(level):
    """Sets system volume (0 to 100) on Windows."""
    try:
        level_int = int(level)
        level_int = max(0, min(100, level_int))

        if platform.system() == "Windows" and WINDOWS_AUDIO:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            scalar = max(0.0, min(1.0, level_int / 100.0))
            volume.SetMasterVolumeLevelScalar(scalar, None)
        else:
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level_int}%"], check=False)

        print(f"\n[RETRO HANDS]: Volume set to {level_int}%")
    except Exception as e:
        print(f"[ERROR]: Failed to change volume: {e}")


def set_screen_brightness(level):
    """Sets screen brightness (0 to 100)."""
    try:
        level_int = int(level)
        level_int = max(0, min(100, level_int))
        if sbc is not None:
            sbc.set_brightness(level_int)
        else:
            print("[WARN]: screen_brightness_control is not available in this environment.")
        print(f"\n[RETRO HANDS]: Brightness set to {level_int}%")
    except Exception as e:
        print(f"[ERROR]: Failed to change brightness: {e}")


def search_local_files(query_term):
    """Searches the user's home directory for matching files."""
    print(f"\n[RETRO HANDS]: Searching local files for '{query_term}'...")
    home_dir = os.path.expanduser("~")
    matches = []

    for root, dirs, files in os.walk(home_dir):
        if "AppData" in root or ".git" in root or "Library" in root:
            continue
        for file in files:
            if query_term.lower() in file.lower():
                matches.append(os.path.join(root, file))
                if len(matches) >= 5:
                    break
        if len(matches) >= 5:
            break

    if matches:
        print("Found files:\n" + "\n".join(matches))
    else:
        print("No matching files found nearby.")
    return matches


def list_directory(path):
    """Lists a directory safely."""
    target = path if path else os.getcwd()
    if not os.path.exists(target):
        return []
    return sorted(os.listdir(target))


def read_text_file(path):
    """Reads a text file safely."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[ERROR]: Could not read file: {e}"


def write_text_file(path, content):
    """Writes a text file safely."""
    try:
        # Debug info to help diagnose OneDrive/permission issues
        print(f"[DEBUG WRITE] target={path} cwd={os.getcwd()}")
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except Exception as e:
                print(f"[DEBUG WRITE] failed to create parent dir: {e}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[ERROR]: Could not write file: {e}")
        try:
            print(f"[ERROR DEBUG] parent_exists={os.path.exists(os.path.dirname(path))}")
        except Exception:
            pass
        return False


def run_background_task(task_name, func, *args, **kwargs):
    """Runs a long task in a background thread."""
    thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
    thread.start()
    print(f"[RETRO TASK]: Started background task '{task_name}'")
    return thread


def route_tool_call(tool_name, args):
    """Maps tool names to actions while preserving Retro's original architecture."""
    tool_name = (tool_name or "").strip().lower()
    if tool_name == "open_app":
        return execute_system_command(args.get("command", ""))
    if tool_name == "set_brightness":
        set_screen_brightness(args.get("level", 50))
        return True
    if tool_name == "adjust_volume":
        set_system_volume(args.get("level", 50))
        return True
    if tool_name == "search_files":
        return search_local_files(args.get("query", ""))
    if tool_name == "read_file":
        return read_text_file(args.get("path", ""))
    if tool_name == "write_file":
        return write_text_file(args.get("path", ""), args.get("content", ""))
    if tool_name == "list_dir":
        return list_directory(args.get("path", os.getcwd()))
    return False


def get_system_summary():
    """Returns a compact overview of the current device context."""
    return {
        "os": platform.system(),
        "model": MODEL,
        "cwd": os.getcwd(),
        "memory_file": MEMORY_PATH,
        "safe_modes": ["search", "read", "list_dir", "open_app", "brightness", "volume"],
    }


def open_url(url):
    """Opens a URL using the OS default browser."""
    target = (url or "").strip()
    if not target:
        return False
    if not re.match(r"^(https?://|www\.)", target, re.IGNORECASE):
        target = "https://" + target
    return execute_system_command(target)


def enqueue_task(memory_data, label, task_type, payload=None):
    """Adds a queued task to memory without disturbing the original logic."""
    memory_data.setdefault("tasks", [])
    memory_data.setdefault("task_queue", memory_data["tasks"])

    task = {
        "label": label,
        "type": task_type,
        "payload": payload or {},
        "status": "pending",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    memory_data["tasks"].append(task)
    memory_data["task_queue"] = memory_data["tasks"]
    save_memory(memory_data)
    return task


def execute_queued_tasks(memory_data):
    """Runs any queued tasks one by one in a simple but fuller task-queue loop."""
    tasks = memory_data.get("task_queue") or memory_data.get("tasks", [])
    if not tasks:
        return "No queued tasks found."

    results = []
    for task in tasks:
        task_type = task.get("type")
        payload = task.get("payload", {})
        task["status"] = "running"

        if task_type == "search":
            hits = search_local_files(payload.get("query", ""))
            results.append(f"Queued task '{task.get('label')}' found {len(hits)} match(es).")
        elif task_type == "open_app":
            execute_system_command(payload.get("command", ""))
            results.append(f"Queued task '{task.get('label')}' launched successfully.")
        elif task_type == "brightness":
            set_screen_brightness(payload.get("level", 50))
            results.append(f"Queued task '{task.get('label')}' adjusted brightness.")
        elif task_type == "volume":
            set_system_volume(payload.get("level", 50))
            results.append(f"Queued task '{task.get('label')}' adjusted volume.")
        else:
            results.append(f"Queued task '{task.get('label')}' is pending.")

        task["status"] = "completed"

    memory_data["tasks"] = []
    memory_data["task_queue"] = []
    save_memory(memory_data)
    return " ; ".join(results)


def browser_search(query):
    """Opens a web search in the default browser."""
    q = quote_plus((query or "").strip())
    if not q:
        return False
    url = "https://www.google.com/search?q=" + q
    return webbrowser.open(url)


def browser_open_url(url):
    """Opens a site in the default browser without disturbing the original app flow."""
    target = (url or "").strip()
    if not target:
        return False
    if not re.match(r"^(https?://|www\.)", target, re.IGNORECASE):
        target = "https://" + target
    return webbrowser.open(target)


# ==========================================
# 4. LOCAL LLM INTERFACE (The Brain)
# ==========================================
def get_available_ollama_models():
    """Returns available model names from the running Ollama server."""
    try:
        response = requests.get(OLLAMA_MODELS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = []
        for item in data.get("models", []):
            if isinstance(item, dict):
                name = item.get("name") or item.get("model")
                if name:
                    models.append(name)
        return models
    except Exception:
        return []


def resolve_model_name():
    """Uses the locally available Ollama models to pick a valid one."""
    global MODEL
    available = get_available_ollama_models()
    if not available:
        return MODEL

    preferred = [MODEL, f"{MODEL}:latest", "llama3", "llama3:latest", "mistral", "phi3:mini"]
    for candidate in preferred:
        if candidate in available:
            MODEL = candidate
            return MODEL

    MODEL = available[0]
    return MODEL


def ask_retro(prompt, context=None):
    """Sends the prompt to the local Ollama model."""
    model_name = resolve_model_name()
    normalized_context = normalize_ollama_context(context)

    payload = {
        "model": model_name,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
    }
    if normalized_context is not None:
        payload["context"] = normalized_context

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        raw_text = ""
        if isinstance(data, dict):
            raw_text = data.get("response") or data.get("text") or ""

            if not raw_text and "results" in data and isinstance(data["results"], list):
                parts = []
                for r in data["results"]:
                    if isinstance(r, dict):
                        parts.append(r.get("text", ""))
                    elif isinstance(r, str):
                        parts.append(r)
                raw_text = "\n".join([p for p in parts if p])

            new_context = data.get("context")
            if not isinstance(new_context, list):
                new_context = None
        else:
            raw_text = str(data)
            new_context = None

        return raw_text, new_context

    except requests.exceptions.ConnectionError:
        return "Error: Ollama is not running or not reachable at http://localhost:11434. Start Ollama and try again.", context
    except requests.exceptions.RequestException as exc:
        details = str(exc)
        if "model" in details.lower() or "not found" in details.lower():
            return f"Error: The selected Ollama model '{model_name}' is unavailable. Available models: {get_available_ollama_models() or 'none'}.", context
        return f"Error: Ollama request failed: {details}", context
    except Exception as e:
        return f"Error: Unexpected response from Ollama ({e})", context


# ==========================================
# 5. PARSER & MAIN LOOP (The Coordinator)
# ==========================================
def parse_and_act(ai_response):
    """Looks for <CMD> tags, executes them, and cleans the text for the user."""
    clean_text = ai_response

    # 1. Brightness command
    for match in re.finditer(r"<CMD>BRIGHTNESS:(\d+)</CMD>", clean_text, re.IGNORECASE):
        set_screen_brightness(match.group(1))
    clean_text = re.sub(r"<CMD>BRIGHTNESS:.*?</CMD>", "", clean_text, flags=re.IGNORECASE)

    # 2. Volume command
    for match in re.finditer(r"<CMD>VOLUME:(\d+)</CMD>", clean_text, re.IGNORECASE):
        set_system_volume(match.group(1))
    clean_text = re.sub(r"<CMD>VOLUME:.*?</CMD>", "", clean_text, flags=re.IGNORECASE)

    # 3. Search command
    for match in re.finditer(r"<CMD>SEARCH:(.*?)</CMD>", clean_text, re.IGNORECASE):
        search_local_files(match.group(1).strip())
    clean_text = re.sub(r"<CMD>SEARCH:.*?</CMD>", "", clean_text, flags=re.IGNORECASE)

    # 4. Read file
    for match in re.finditer(r"<CMD>READ_FILE:(.*?)</CMD>", clean_text, re.IGNORECASE):
        file_path = match.group(1).strip()
        content = read_text_file(file_path)
        print(f"\n[RETRO FILE READ]: {file_path}\n{content[:500]}")
    clean_text = re.sub(r"<CMD>READ_FILE:.*?</CMD>", "", clean_text, flags=re.IGNORECASE)

    # 5. Write file
    for match in re.finditer(r"<CMD>WRITE_FILE:(.*?)\|(.*?)</CMD>", clean_text, re.IGNORECASE | re.DOTALL):
        file_path = match.group(1).strip()
        content = match.group(2)
        result = write_text_file(file_path, content)
        if result:
            print(f"\n[RETRO FILE WRITE]: Wrote to {file_path}")
    clean_text = re.sub(r"<CMD>WRITE_FILE:.*?</CMD>", "", clean_text, flags=re.IGNORECASE | re.DOTALL)

    # 6. List directory
    for match in re.finditer(r"<CMD>LIST_DIR:(.*?)</CMD>", clean_text, re.IGNORECASE):
        directory = match.group(1).strip()
        items = list_directory(directory)
        print(f"\n[RETRO DIR LIST]: {directory}\n{items}")
    clean_text = re.sub(r"<CMD>LIST_DIR:.*?</CMD>", "", clean_text, flags=re.IGNORECASE)

    # 7. Standard app execution
    commands = re.findall(r"<CMD>(.*?)</CMD>", clean_text, re.IGNORECASE | re.DOTALL)
    for cmd in commands:
        execute_system_command(cmd)

    # Final cleanup of any executed tags
    clean_text = re.sub(r"<CMD>.*?</CMD>", "", clean_text, flags=re.IGNORECASE | re.DOTALL).strip()
    return clean_text


def handle_agentic_prompt(user_input, memory_data):
    """Adds lightweight agentic behavior without changing the original command flow."""
    lower = user_input.lower()

    direct_task = parse_direct_task(user_input)
    if direct_task:
        action = direct_task["action"]
        if action == "open_app":
            execute_system_command(direct_task["command"])
            return f"Opening {direct_task['command']}."
        if action == "set_brightness":
            set_screen_brightness(direct_task["level"])
            return f"Brightness set to {direct_task['level']}%."
        if action == "set_volume":
            set_system_volume(direct_task["level"])
            return f"Volume set to {direct_task['level']}%."
        if action == "search_files":
            query = direct_task["query"]
            hits = search_local_files(query)
            if hits:
                return f"I found {len(hits)} local match(es): " + "; ".join(hits[:3])
            return f"I searched for '{query}' and found no local matches."
        if action == "read_file":
            path = direct_task["path"]
            content = read_text_file(path)
            return f"Reading {path}\n{content[:400]}" if isinstance(content, str) else content
        if action == "write_file":
            path = direct_task["path"]
            content = direct_task["content"]
            ok = write_text_file(path, content)
            return f"Wrote {path}." if ok else f"Failed to write {path}."
        if action == "list_dir":
            items = list_directory(direct_task["path"])
            return f"Directory listing for {direct_task['path']}: " + ", ".join(items[:10]) if items else "No items found."
        if action == "open_url":
            browser_open_url(direct_task["url"])
            return f"Opening {direct_task['url']} in the default browser."

    # Quick local file creation shortcut: handle simple "create file" requests
    if any(kw in lower for kw in ("create file", "create a file", "make a file", "write file", "create file named", "create file called")):
        # try to extract a filename from the user input
        m = re.search(r'file(?: named| called)?\s+["\']?([^"\'\n]+)["\']?', user_input, re.IGNORECASE)
        if not m:
            m = re.search(r"([\w\- ./]+\.[a-zA-Z0-9]+)", user_input)
        if m:
            filename = m.group(1).strip()
            # Normalize to absolute path to avoid cwd/OneDrive ambiguity
            if os.path.isabs(filename):
                target = os.path.normpath(filename)
            else:
                target = os.path.normpath(os.path.abspath(filename))
            try:
                parent = os.path.dirname(target)
                if parent and not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)
                ok = write_text_file(target, "")
                if ok:
                    remember_history(memory_data, user_input)
                    return f"Created file: {target}"
                else:
                    return f"Failed to create file: {target}"
            except Exception as e:
                return f"Error creating file: {e}"
        else:
            return "Please specify the file name to create."

    if "remember" in lower or "prefer" in lower:
        if " prefer " in lower or " prefer" in lower:
            key = "preferred_app" if "app" in lower else "preference"
            remember_fact(memory_data, key, user_input)
            return "I will remember that preference."

    if "who developed you" in lower or "who created you" in lower or "who made you" in lower:
        return "I was developed by Amish."

    if any(term in lower for term in ["what can you do", "what are your capabilities", "list your features", "your features", "capabilities"]):
        return (
            "I can help with local file search, file reading and writing, app launching, "
            "browser URL opening, brightness and volume control, memory, planning, and safe task execution."
        )

    if "queue" in lower or "schedule" in lower or "run my tasks" in lower:
        queued = execute_queued_tasks(memory_data)
        return queued

    if "search the web" in lower or "web search" in lower:
        query = user_input.split("search the web", 1)[-1].strip() or user_input.split("web search", 1)[-1].strip()
        browser_search(query)
        return f"Searching the web for: {query or 'your query'}"

    if "open website" in lower or "open url" in lower or "go to " in lower:
        match = re.search(r"(?:go to|open website|open url)\s+(https?://\S+|www\.\S+|[A-Za-z0-9.-]+\.[A-Za-z]{2,}\S*)", user_input, re.IGNORECASE)
        url = match.group(1) if match else ""
        if url:
            browser_open_url(url)
            return f"Opening {url} in the default browser."

    if "system status" in lower or "status" in lower and "system" in lower:
        return str(get_system_summary())

    if recognize_multi_step_task(user_input):
        plan = plan_task(user_input)
        remember_history(memory_data, user_input)

        executed = execute_multi_step_task(user_input, memory_data)
        if executed:
            return executed

        steps = []
        for item in plan:
            if isinstance(item, dict):
                steps.append(item.get("label", "step"))
            else:
                steps.append(str(item))
        return "I have a plan: " + "; ".join(steps)

    return None


def main():
    print("===================================================")
    print(" RETRO LOCAL BRAIN INITIATED. TYPE 'exit' TO QUIT.")
    print("===================================================")

    memory_data = load_memory()
    conversation_context = None

    try:
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit']:
                print("Retro shutting down...")
                break

            agentic_reply = handle_agentic_prompt(user_input, memory_data)
            if agentic_reply:
                print(f"\nRetro: {agentic_reply}")
                remember_history(memory_data, user_input)
                continue

            # 1. Build richer context with memory support
            conversation_context = build_context(user_input, conversation_context, memory_data)

            # 2. Ask the Local LLM
            raw_response, conversation_context = ask_retro(user_input, conversation_context)
            if not isinstance(conversation_context, list):
                conversation_context = None

            # 3. Parse for commands and execute them
            final_response = parse_and_act(raw_response)

            # 4. Output to the console
            print(f"\nRetro: {final_response}")
            remember_history(memory_data, user_input)

    except KeyboardInterrupt:
        print("\nRetro interrupted by user. Exiting.")
    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()