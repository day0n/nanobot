# OpenCreator Agent Skills

This directory contains built-in skills that extend OpenCreator Agent's capabilities.

## Skill Format

Each skill is a directory containing a `SKILL.md` file with:
- YAML frontmatter (name, description, metadata)
- Markdown instructions for the agent

## Attribution

These skills are adapted from [OpenClaw](https://github.com/openclaw/openclaw)'s skill system.
The skill format and metadata structure follow OpenClaw's conventions to maintain compatibility.

## Available Skills

| Skill | Description | Always Loaded |
|-------|-------------|---------------|
| `edit-workflow` | Edit OpenCreator workflows in the current canvas | ✅ Yes |
| `workflow-user-guide` | User-facing OpenCreator workflow guidance (nodes, wiring, templates) | No |
| `weather` | Get weather info using wttr.in and Open-Meteo | No |
| `summarize` | Summarize URLs, files, and YouTube videos | No |
| `cron` | Schedule recurring tasks | No |
