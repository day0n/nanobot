# Tool Usage Notes

Tool signatures are provided automatically via function calling.
This file documents non-obvious constraints and usage patterns.

## Available Tools

- `read_file` for reading allowed local files such as built-in skill docs.
- `web_search` and `web_fetch` for online research when needed.
- `spawn` for subagent delegation when the task benefits from it.
- `get_workflow` for fetching the current canvas workflow before making changes.
- `edit_workflow` for saving the full updated OpenCreator workflow through the backend API.
