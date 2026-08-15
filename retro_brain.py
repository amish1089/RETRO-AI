import requests
import json
import subprocess
import platform
import re
import os
import threading
import time
from pathlib import Path

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
MODEL = "llama3"  # Change to 'phi3' or your preferred local model
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


def recognize_multi_step_task(prompt):
    """Simple heuristic to detect multi-step prompts."""
    task_markers = [" and ", " then ", " then do ", " first ", " next ", " afterwards ", " summarize ", " review ", " find ", " compare "]
    lower = prompt.lower()
    return any(marker in lower for marker in task_markers) and len(prompt.split()) > 8


def plan_task(prompt):
    """Creates a lightweight plan for multi-step requests."""
    steps = []
    lower = prompt.lower()
    if "find" in lower or "search" in lower:
        steps.append("search for relevant files or information")
    if "summarize" in lower or "summary" in lower:
        steps.append("summarize the result")
    if "open" in lower or "launch" in lower:
        steps.append("open the requested application or page")
    if "brightness" in lower or "volume" in lower:
        steps.append("adjust system settings")
    if not steps:
        steps = ["handle the user request with the main agent flow"]
    return steps


# ==========================================
# 3. SYSTEM CONTROL ENGINE (The Hands)
# ==========================================
def is_safe_command(command):
    """Checks whether a command is allowed or requires confirmation."""
    lowered = command.lower()
    if any(item in lowered for item in ["shutdown", "restart", "install", "uninstall", "delete", "format", "rm ", "del ", "rmdir"]):
        return False
    return True


def execute_system_command(command):
    """Executes a command using OS-specific launch logic."""
    os_name = platform.system()
    command = (command or "").strip()

    if not command:
        print("[ERROR]: Empty command received.")
        return False

    if not is_safe_command(command):
        print(f"[WARN]: Command requires confirmation before execution: {command}")
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
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[ERROR]: Could not write file: {e}")
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


# ==========================================
# 4. LOCAL LLM INTERFACE (The Brain)
# ==========================================
def ask_retro(prompt, context=None):
    """Sends the prompt to the local Ollama model."""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "context": context,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
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

            new_context = data.get("context", context)
        else:
            raw_text = str(data)
            new_context = context

        return raw_text, new_context

    except requests.exceptions.RequestException:
        return "Error: Could not connect to Ollama. Is it running?", context
    except Exception as e:
        return f"Error: Unexpected response from Ollama ({e})", context


# ==========================================
# 5. PARSER & MAIN LOOP (The Coordinator)
# ==========================================
def parse_and_act(ai_response):
    """Looks for <CMD> tags, executes them, and cleans the text for the user."""
    # 1. Brightness command
    bright_match = re.search(r"<CMD>BRIGHTNESS:(\d+)</CMD>", ai_response, re.IGNORECASE)
    if bright_match:
        set_screen_brightness(bright_match.group(1))
        return re.sub(r"<CMD>BRIGHTNESS:.*?</CMD>", "", ai_response, flags=re.IGNORECASE).strip()

    # 2. Volume command
    vol_match = re.search(r"<CMD>VOLUME:(\d+)</CMD>", ai_response, re.IGNORECASE)
    if vol_match:
        set_system_volume(vol_match.group(1))
        return re.sub(r"<CMD>VOLUME:.*?</CMD>", "", ai_response, flags=re.IGNORECASE).strip()

    # 3. Search command
    search_match = re.search(r"<CMD>SEARCH:(.*?)</CMD>", ai_response, re.IGNORECASE)
    if search_match:
        search_local_files(search_match.group(1))
        return re.sub(r"<CMD>SEARCH:.*?</CMD>", "", ai_response, flags=re.IGNORECASE).strip()

    # 4. Read file
    read_file_match = re.search(r"<CMD>READ_FILE:(.*?)</CMD>", ai_response, re.IGNORECASE)
    if read_file_match:
        file_path = read_file_match.group(1).strip()
        content = read_text_file(file_path)
        print(f"\n[RETRO FILE READ]: {file_path}\n{content[:500]}")
        return re.sub(r"<CMD>READ_FILE:.*?</CMD>", "", ai_response, flags=re.IGNORECASE).strip()

    # 5. Write file
    write_file_match = re.search(r"<CMD>WRITE_FILE:(.*?)\|(.*?)</CMD>", ai_response, re.IGNORECASE | re.DOTALL)
    if write_file_match:
        file_path = write_file_match.group(1).strip()
        content = write_file_match.group(2)
        result = write_text_file(file_path, content)
        if result:
            print(f"\n[RETRO FILE WRITE]: Wrote to {file_path}")
        return re.sub(r"<CMD>WRITE_FILE:.*?</CMD>", "", ai_response, flags=re.IGNORECASE | re.DOTALL).strip()

    # 6. List directory
    list_dir_match = re.search(r"<CMD>LIST_DIR:(.*?)</CMD>", ai_response, re.IGNORECASE)
    if list_dir_match:
        directory = list_dir_match.group(1).strip()
        items = list_directory(directory)
        print(f"\n[RETRO DIR LIST]: {directory}\n{items}")
        return re.sub(r"<CMD>LIST_DIR:.*?</CMD>", "", ai_response, flags=re.IGNORECASE).strip()

    # 7. Standard app execution remains in place
    commands = re.findall(r"<CMD>(.*?)</CMD>", ai_response, re.IGNORECASE | re.DOTALL)
    for cmd in commands:
        execute_system_command(cmd)

    clean_text = re.sub(r"<CMD>.*?</CMD>", "", ai_response, flags=re.IGNORECASE | re.DOTALL).strip()
    return clean_text


def handle_agentic_prompt(user_input, memory_data):
    """Adds lightweight agentic behavior without changing the original command flow."""
    lower = user_input.lower()

    if "remember" in lower or "prefer" in lower:
        if " prefer " in lower or " prefer" in lower:
            key = "preferred_app" if "app" in lower else "preference"
            remember_fact(memory_data, key, user_input)
            return "I will remember that preference."

    if "who developed you" in lower or "who created you" in lower or "who made you" in lower:
        return "I was developed by Amish."

    if recognize_multi_step_task(user_input):
        plan = plan_task(user_input)
        remember_history(memory_data, user_input)
        return "I have a plan: " + "; ".join(plan)

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