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
    - **LLM API Key**: From your chosen provider (see Supported LLM Providers below)

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

- Web UI: http://localhost:3000
- API Docs: http://localhost:8000/docs

## Configuration

### Secrets (`.env`)

```env
YOUTUBE_API_KEY=your_youtube_api_key
GEMINI_API_KEY=your_gemini_api_key
# OPENAI_API_KEY=your_openai_api_key
# ANTHROPIC_API_KEY=your_anthropic_api_key
```

### Application Config (`config.yaml`)

All non-secret configuration lives in `config.yaml`:

```yaml
llm_providers:
  - id: gemini-flash
    name: "Gemini 2.5 Flash"
    model: gemini/gemini-2.5-flash
    api_key_env: GEMINI_API_KEY

  - id: gpt5-nano
    name: "GPT-5 Nano"
    model: openai/gpt-5-nano
    api_key_env: OPENAI_API_KEY

  - id: claude-sonnet
    name: "Claude Sonnet 4.5"
    model: anthropic/claude-sonnet-4-5-20250929
    api_key_env: ANTHROPIC_API_KEY

default_provider: gemini-flash

whisper:
  model: base
  fallback_enabled: true
```

- **LLM providers**: Switch between providers at runtime via the UI dropdown. Providers are only available if their API key is set in `.env`.
- **Whisper**: Fallback transcription when YouTube captions unavailable.

## Supported LLM Providers

Uses [LiteLLM](https://docs.litellm.ai/docs/providers) for model-agnostic LLM support:

| Provider      | Model Format                | Example                                  |
|---------------|-----------------------------|------------------------------------------|
| Google Gemini | `gemini/model-name`         | `gemini/gemini-2.5-flash`                |
| OpenAI        | `openai/model-name`         | `openai/gpt-5-nano`                      |
| Anthropic     | `anthropic/model-name`      | `anthropic/claude-sonnet-4-5-20250929`   |
| OpenRouter    | `openrouter/provider/model` | `openrouter/anthropic/claude-sonnet-4-5` |

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
