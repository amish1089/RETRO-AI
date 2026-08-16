import retro_brain


def test_basic_capability_response():
    memory = {"preferences": {}, "history": [], "files": [], "tasks": []}
    result = retro_brain.handle_agentic_prompt("what can you do", memory)
    assert result is not None
    assert "file search" in result.lower() or "local file" in result.lower()


def test_open_notepad_direct_action():
    memory = {"preferences": {}, "history": [], "files": [], "tasks": []}
    result = retro_brain.handle_agentic_prompt("open notepad", memory)
    assert result == "Opening notepad."


def test_search_falls_back_to_search_tool():
    memory = {"preferences": {}, "history": [], "files": [], "tasks": []}
    result = retro_brain.handle_agentic_prompt("search for python", memory)
    assert "searched" in result.lower() or "found" in result.lower() or "match" in result.lower()
