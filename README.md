# YouTube Analyzer

Analyze YouTube channels using AI. Extract transcripts from videos, ask questions, and get insights through a web interface.

**Use cases:**
- Summarize a creator's advice across multiple videos
- Extract training programs, recipes, or tutorials from video content
- Research topics by analyzing educational channels
- Build knowledge bases from video transcripts

## Prerequisites

1. **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)
2. **API Keys:**
   - **YouTube Data API v3**: [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - **Gemini API**: [Google AI Studio](https://aistudio.google.com/app/apikey)

## Setup & Run

```bash
# Clone repository
git clone https://github.com/radupana/youtube-analyzer.git
cd youtube-analyzer

# Configure API keys
cp .env.example .env
# Edit .env and add your API keys

# Start application
docker-compose up
```

**That's it!** Access the application at:
- 🌐 **Web UI**: http://localhost:3000
- 📚 **API Docs**: http://localhost:8000/docs

## Configuration

All configuration is done through environment variables in `.env`:

```env
# Required
YOUTUBE_API_KEY=your_youtube_api_key
GEMINI_API_KEY=your_gemini_api_key

# Optional (with defaults)
MAX_VIDEOS=50              # Maximum videos to process
WHISPER_MODEL=base         # Whisper model size (tiny, base, small, medium, large)
LLM_MODEL=gemini-2.0-flash # LLM model to use
```

## How It Works

1. **Fetches transcripts** via YouTube's caption API (fast, free)
2. **Falls back to Whisper** audio transcription if captions unavailable
3. **Caches everything** locally for fast repeat runs
4. **Smart context mode:** Uses full-context for small datasets, RAG for large ones
5. **Analyzes with LLM** based on your intent

## Stop & Clean Up

```bash
# Stop containers
docker-compose down

# Remove volumes (clears cache)
docker-compose down -v
```

## License

Apache 2.0
