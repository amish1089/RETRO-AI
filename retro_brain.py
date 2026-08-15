import requests
import json
import subprocess
import platform
import re
import os

# ==========================================
# 1. CONFIGURATION
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3" # Change to 'phi3' or your preferred local model

# The System Prompt is Retro's personality and rulebook.
SYSTEM_PROMPT = """
You are Retro, an advanced, highly capable local AI assistant. 
Your personality is sleek, efficient, and slightly futuristic.

You have the ability to control the user's computer. 
If the user asks you to open an application, open a website, or perform a system task, you MUST output a command tag in this exact format: <CMD>command here</CMD>.

Examples:
- User: "Open Notepad." -> You output: "Opening Notepad now. <CMD>notepad</CMD>"
- User: "Open Calculator." -> You output: "Right away. <CMD>calc</CMD>"
- User: "Who are you?" -> You output: "I am Retro, your local AI system." (No command tag needed).

Do not explain how to open apps, just use the <CMD> tag. Keep your responses concise.
"""

# ==========================================
# 2. SYSTEM CONTROL ENGINE (The Hands)
# ==========================================
def execute_system_command(command):
    """Executes the command safely based on the OS."""
    os_name = platform.system()
    # keep original casing for app names/commands
    command = command.strip()

    print(f"\n[RETRO SYSTEM EXECUTING]: {command}")
    
    try:
        if os_name == "Windows":
            # Handles basic Windows executables; use shell so built-ins work
            subprocess.Popen(command, shell=True)
            return True
        elif os_name == "Darwin": # macOS
            # On Mac, 'open -a' is usually needed for apps
            subprocess.Popen(["open", "-a", command])
            return True
        elif os_name == "Linux":
            # Use shell to allow commands like 'xdg-open' or installed binaries
            subprocess.Popen(command, shell=True)
            return True
        else:
            print("Unsupported OS for direct commands.")
            return False
    except Exception as e:
        print(f"[ERROR]: Failed to execute {command}. Reason: {e}")
        return False

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
    # Find all command tags and execute them in order
    commands = re.findall(r"<CMD>(.*?)</CMD>", ai_response, re.IGNORECASE | re.DOTALL)

    for cmd in commands:
        execute_system_command(cmd)

    # Remove all tags from the final text so the UI looks clean
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