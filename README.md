# YouTube Analyzer

Analyze YouTube videos using AI. Extract transcripts, ask questions, and get insights through a web interface.

**Use cases:**
- Summarize key points from long-form video content
- Extract training programs, recipes, or tutorials from videos
- Research topics by analyzing educational content
- Build context by adding multiple videos one at a time

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
WHISPER_MODEL=base         # Whisper model size (tiny, base, small, medium, large)
LLM_MODEL=gemini-2.0-flash # LLM model to use
```

## How It Works

1. **Paste a video URL** - Add YouTube videos one at a time
2. **Fetches transcripts** via YouTube's caption API (fast, free)
3. **Falls back to Whisper** audio transcription if captions unavailable
4. **Caches everything** locally for fast repeat access
5. **Chat with AI** about your loaded videos

## Stop & Clean Up

```bash
# Stop containers
docker-compose down

# Remove volumes (clears cache)
docker-compose down -v
```

## License

Apache 2.0
