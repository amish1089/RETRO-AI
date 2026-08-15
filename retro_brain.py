import requests
import json
import subprocess
import platform
import re
import os

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
MODEL = "llama3" # Change to 'phi3' or your preferred local model

# The System Prompt is Retro's personality and rulebook.
SYSTEM_PROMPT = """
You are Retro, an advanced local AI assistant controlling the user's device.
You can execute special commands using specific tags:
- Applications: <CMD>app_name</CMD>
- Brightness: <CMD>BRIGHTNESS:50</CMD> (expects a percentage 0-100)
- Volume: <CMD>VOLUME:70</CMD> (expects a percentage 0-100)
- File Search: <CMD>SEARCH:filename</CMD>

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
# 2. SYSTEM CONTROL ENGINE (The Hands)
# ==========================================
def execute_system_command(command):
    """Executes a command using OS-specific launch logic."""
    os_name = platform.system()
    command = (command or "").strip()

    if not command:
        print("[ERROR]: Empty command received.")
        return False

    print(f"\n[RETRO SYSTEM EXECUTING]: {command}")

    try:
        if os_name == "Windows":
            # Use cmd /c for shell commands and start for app launches.
            if re.match(r"^(https?://|www\.)", command, re.IGNORECASE):
                subprocess.Popen(["cmd", "/c", "start", "", command], shell=False)
            elif command.lower().endswith((".exe", ".bat", ".cmd")):
                subprocess.Popen([command], shell=False)
            else:
                subprocess.Popen(["cmd", "/c", command], shell=False)
            return True

        elif os_name == "Darwin":
            # macOS: use 'open' for apps and urls; supports shell-safe app names.
            if re.match(r"^(https?://|www\.)", command, re.IGNORECASE):
                subprocess.Popen(["open", command], shell=False)
            else:
                subprocess.Popen(["open", "-a", command], shell=False)
            return True

        elif os_name == "Linux":
            # Linux: xdg-open covers browsers and apps; shell fallback for commands.
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


# ==========================================
# 3. LOCAL LLM INTERFACE (The Brain)
# ==========================================
def ask_retro(prompt, context=None):
    """Sends the prompt to the local Ollama model."""
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "context": context # Allows for conversation memory
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        # Try a few common response shapes returned by local LLM servers
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
# 4. PARSER & MAIN LOOP (The Coordinator)
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

    # 4. Standard app execution remains in place
    commands = re.findall(r"<CMD>(.*?)</CMD>", ai_response, re.IGNORECASE | re.DOTALL)
    for cmd in commands:
        execute_system_command(cmd)

    # Remove all tags from the final text so the UI looks clean
    clean_text = re.sub(r"<CMD>.*?</CMD>", "", ai_response, flags=re.IGNORECASE | re.DOTALL).strip()
    return clean_text


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

    # 4. Standard app execution remains in place
    commands = re.findall(r"<CMD>(.*?)</CMD>", ai_response, re.IGNORECASE | re.DOTALL)
    for cmd in commands:
        execute_system_command(cmd)

    clean_text = re.sub(r"<CMD>.*?</CMD>", "", ai_response, flags=re.IGNORECASE | re.DOTALL).strip()
    return clean_text

def main():
    print("===================================================")
    print(" RETRO LOCAL BRAIN INITIATED. TYPE 'exit' TO QUIT.")
    print("===================================================")
    
    conversation_context = None

    try:
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit']:
                print("Retro shutting down...")
                break

            # 1. Ask the Local LLM
            raw_response, conversation_context = ask_retro(user_input, conversation_context)

            # 2. Parse for commands and execute them
            final_response = parse_and_act(raw_response)

            # 3. Output to the console (This will eventually go to your UI)
            print(f"\nRetro: {final_response}")
    except KeyboardInterrupt:
        print("\nRetro interrupted by user. Exiting.")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()