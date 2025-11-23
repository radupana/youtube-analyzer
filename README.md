# YouTube Analyzer

Analyze YouTube channels using AI. Extract transcripts from videos, ask questions, and get insights - all through a simple conversational CLI.

**Use cases:**
- Summarize a creator's advice across multiple videos
- Extract training programs, recipes, or tutorials from video content
- Research topics by analyzing educational channels
- Build knowledge bases from video transcripts

## Prerequisites

### Python 3.13+

**Mac:**
```bash
brew install python@3.13
```

**Windows:**
```bash
winget install Python.Python.3.13
# or download from https://www.python.org/downloads/
```

### FFmpeg (required for Whisper audio transcription)

**Mac:**
```bash
brew install ffmpeg
```

**Windows:**
```bash
winget install ffmpeg
# or download from https://ffmpeg.org/download.html and add to PATH
```

### API Keys

1. **YouTube Data API v3**: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. **Gemini API**: [Google AI Studio](https://aistudio.google.com/app/apikey)

## Setup

```bash
# Clone
git clone https://github.com/radupana/youtube-analyzer.git
cd youtube-analyzer

# Create virtual environment
python3 -m venv .venv

# Activate (Mac/Linux)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install
pip install -e .

# Configure
cp config.example.yaml config.yaml
```

Set your API keys:

```bash
# Mac/Linux
export GEMINI_API_KEY="your-key"
export YOUTUBE_API_KEY="your-key"

# Windows (PowerShell)
$env:GEMINI_API_KEY="your-key"
$env:YOUTUBE_API_KEY="your-key"
```

## Run

```bash
python -m yt_agent_kit
```

The agent will ask you:
1. Which YouTube channel/video/playlist to analyze
2. What you want to learn
3. How many videos to process
4. Your preferred output format

## Configuration

Edit `config.yaml` to customize:

```yaml
llm:
  provider: "gemini"
  api_key: "${GEMINI_API_KEY}"
  model: "gemini-2.0-flash"

youtube_api_key: "${YOUTUBE_API_KEY}"
max_videos: 200

# Whisper fallback for videos without captions
transcription:
  fallback_enabled: true
  whisper_model: base  # tiny, base, small, medium, large, turbo
  cleanup_audio: true
```

## How It Works

1. Fetches video transcripts via YouTube's caption API (fast, free)
2. Falls back to Whisper audio transcription if captions unavailable
3. Caches everything locally in `.cache/` for fast repeat runs
4. **Smart context mode:** If transcripts fit in the LLM context window, uses full-context mode for maximum fidelity. Falls back to RAG (semantic search) for larger datasets.
5. Uses LLM to analyze transcripts based on your intent

The context window is auto-detected from Gemini's API. Override via `llm.context_limit` in config if needed.

## License

MIT
