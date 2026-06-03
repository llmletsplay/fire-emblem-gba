# Fire Emblem AI Scripts

This directory contains startup and management scripts for the Fire Emblem GBA
AI project, organized by platform.

## Directory Structure

```
scripts/
├── windows/          # Windows batch files (.bat)
└── unix/             # Unix/macOS shell scripts (.sh)
```

## Usage

### From Project Root

You can run scripts directly from the project root:

**Windows:**
- `start.bat` - Start the full application (frontend + backend)

**Unix/macOS:**
- `./start.sh` - Start the full application (frontend + backend)

### Platform-Specific Scripts

If you need to run scripts directly from their platform folders:

**Windows:** `scripts\windows\[script].bat`
**Unix:** `scripts/unix/[script].sh`

## Script Descriptions

### Main Application
- **start**: Launches both frontend and backend, auto-detects LLM provider

### Utilities
- **setup-branch-protection**: Configures GitHub branch protection rules

## Requirements

### Windows
- Python 3.10+
- Node.js 18+
- Git for Windows

### Unix/macOS
- Python 3.10+
- Node.js 18+
- bash shell
- git

## Environment Variables

The scripts respect the following environment variables:
- `LLM_PROVIDER`: OPENAI, ANTHROPIC, GEMINI, OLLAMA, LMSTUDIO, GROQ, TOGETHER, GROK, CUSTOM, or ZAI
- `ROM_FILE`: ROM filename in `roms/`
- `FE_GAME`: `fe7` or `fe8`
- `CUSTOM_BASE_URL`: Custom LLM endpoint URL
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
