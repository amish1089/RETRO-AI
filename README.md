RETRO AI
What this is
Retro is a small local Python assistant that forwards user prompts to a locally-hosted Ollama model and can execute system commands embedded in the model's responses using <CMD>command</CMD> tags. It's intended as a minimal, local proof-of-concept for a "local LLM + system control" assistant.

Stack
Language(s): Python (single-file script)
Framework / runtime: Python 3.8+ (CLI script)
Notable libraries / tools: requests (HTTP client), Ollama (local LLM server), standard library modules: subprocess, platform, re, os
How it's organized
Text
retro_brain.py    # Main CLI: sends prompts to Ollama, parses <CMD> tags, executes commands
README.md         # This file
How it fits together
retro_brain.py is a single-process CLI loop. When you type a prompt it:

Sends the prompt (plus a built-in system prompt) to the local Ollama API.
Receives the model's text response.
Scans the response for <CMD>...</CMD> tags; executes each command in order (platform-aware).
Strips tags and prints the cleaned response to the console. Conversation context is passed back to Ollama (if the Ollama API and model support it), allowing short multi-turn sessions.
Requirements
A working Ollama server running locally and reachable at http://localhost:11434 (or change the URL in the script).
A compatible local model available to Ollama (example model names used in the script: "llama3", "phi3").
Python 3.8+ and pip.
Python dependency: requests
Quick start — run locally
Clone the repo and change into it:
bash
git clone https://github.com/amish1089/RETRO-AI.git
cd RETRO-AI
Install the Python dependency:
bash
python3 -m pip install requests
Ensure Ollama is running and a model (e.g., "llama3") is available locally:
Follow Ollama's docs to start the server and install your model(s).
By default the script expects Ollama at: http://localhost:11434/api/generate
Run Retro:
bash
python3 retro_brain.py
Type messages into the CLI. Type exit or quit to stop.

Configuration
Open retro_brain.py and update the top constants as needed:

OLLAMA_URL — change if your Ollama server is at a different host/port or API path.
MODEL — the model name to send with requests (e.g., "llama3", "phi3").
Example (top of retro_brain.py):

Python
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
SYSTEM_PROMPT = """ ... """
If you want environment-driven configuration, you can modify the script to read os.environ values for OLLAMA_URL and MODEL.

Security & safety
This script will execute any command included in a model response inside <CMD>...</CMD> tags using the host shell (Windows/macOS/Linux). That is powerful but also potentially dangerous.
Never run this against untrusted models or in an environment with sensitive data unless you fully trust the model and understand the commands it may emit.
Consider running in a sandbox, VM, or container, or add explicit allow-listing for permitted commands before executing them.
The script currently does not sanitize commands beyond platform handling — treat it as an experiment/proof-of-concept, not production-ready automation.
Behavior notes / Design decisions
The system prompt enforces Retro's personality and instructs the model to use <CMD> tags when it should perform system actions.
The script supports basic conversation context by passing a context field to the Ollama API when present, subject to the local model server's API behavior.

