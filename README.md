# YouTube Analyzer

[![CI](https://github.com/radupana/youtube-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/radupana/youtube-analyzer/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/radupana/youtube-analyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/radupana/youtube-analyzer)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Stop watching 2-hour videos for 3 key insights.** Extract what matters in seconds.

![Demo](demo.gif)

## Quick Start

```bash
git clone https://github.com/radupana/youtube-analyzer.git
cd youtube-analyzer
cp .env.example .env
# Add your API keys to .env
docker-compose up
```

Open http://localhost:3000 and paste a YouTube URL. That's it.

## What It Does

Paste any YouTube video and instantly:

- **Summarize** - TL;DR, key takeaways, main topics, and notable quotes
- **Tutorial Notes** - Steps, commands, and prerequisites from technical content

Then chat with AI about the content. Add more videos to build context across multiple sources.

## Features

| Feature                  | Description                                                      |
|--------------------------|------------------------------------------------------------------|
| **Pattern Analysis**     | One-click structured extraction (summaries, tutorial notes)      |
| **Multi-Video Chat**     | Ask questions across multiple videos simultaneously              |
| **RAG-Powered**          | Semantic search finds relevant transcript sections automatically |
| **Transcript Search**    | Find specific moments with keyword highlighting                  |
| **Export Transcripts**   | Download as TXT, SRT, or JSON                                    |
| **Language Preferences** | Set preferred caption languages (drag to reorder priority)       |
| **Streaming Responses**  | See AI responses appear in real-time                             |
| **Whisper Fallback**     | Auto-transcribe videos without captions                          |
| **Session Management**   | Organize videos into separate analysis sessions                  |

## Requirements

1. **Docker** - [Install Docker](https://docs.docker.com/get-docker/)
2. **YouTube Data API key** - [Get one here](https://console.cloud.google.com/apis/credentials)
3. **LLM API key** - Gemini, OpenAI, Anthropic, or OpenRouter

## Configuration

### API Keys (`.env`)

```env
YOUTUBE_API_KEY=your_youtube_api_key
GEMINI_API_KEY=your_gemini_api_key      # Default provider
# OPENAI_API_KEY=your_openai_api_key
# ANTHROPIC_API_KEY=your_anthropic_api_key
```

### LLM Providers (`config.yaml`)

Switch providers at runtime via the UI dropdown:

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
```

Uses [LiteLLM](https://docs.litellm.ai/docs/providers) - any supported provider works.

## How It Works

1. **Paste URL** - Add YouTube videos one at a time
2. **Fetch transcript** - Uses YouTube captions (fast) or Whisper audio transcription (fallback)
3. **Chunk & embed** - Splits transcript into semantic chunks with embeddings
4. **Chat or analyze** - RAG retrieval finds relevant sections for your questions

Everything is cached locally in an SQLite database for fast repeat access.

## Troubleshooting

### YouTube IP Blocking

**"Could not retrieve a transcript"** / **"YouTube is blocking requests from your IP"**

YouTube aggressively blocks automated transcript requests. This is a YouTube limitation, not a tool bug. Common causes:

- **Too many requests** - YouTube rate-limits IPs that fetch many transcripts
- **Cloud/VPN IPs** - Most cloud providers and popular VPNs are pre-blocked
- **Datacenter IPs** - Residential IPs work better than datacenter IPs

**Workarounds (in order of reliability):**

| Solution              | Effort | Notes                                                               |
|-----------------------|--------|---------------------------------------------------------------------|
| **Wait 24-48h**       | None   | IP blocks often expire after a day or two                           |
| **Whisper fallback**  | None   | Enable in config - transcribes audio directly (slower but reliable) |
| **Different network** | Low    | Mobile hotspot, different WiFi, etc.                                |
| **Residential proxy** | Medium | Rotating residential IPs bypass YouTube's blocking (see below)      |

#### Whisper Fallback

To enable Whisper fallback (recommended), ensure your `config.yaml` has:

```yaml
whisper:
  fallback_enabled: true
  model: base  # or 'tiny' for faster, 'small' for better quality
```

#### Proxy Setup (Recommended)

For reliable transcript fetching, use a rotating residential proxy. YouTube actively blocks datacenter IPs (including the free Webshare proxies), so **rotating residential is the only reliable option**.

**Webshare Rotating Residential (~$4/month for 1GB ≈ 6,000+ videos)**

1. Sign up at [webshare.io](https://www.webshare.io/)
2. Purchase a **Rotating Residential** plan (1GB is plenty for normal use)
3. Go to **Rotating Residential** → **Proxy List**, select **"Rotating Proxy Endpoint"** as connection method
4. Copy your **username** (e.g., `username-rotate`) and **password**
5. Add to `config.yaml`:
   ```yaml
   proxy:
     type: webshare_rotating
   ```
6. Add credentials to `.env`:
   ```env
   WEBSHARE_PROXY_USERNAME=your_username-rotate
   WEBSHARE_PROXY_PASSWORD=your_password
   ```
7. Restart: `docker-compose restart backend`

The backend logs will show `Using Webshare rotating residential proxy` when configured.

> **Note:** Webshare's free tier provides datacenter proxies which YouTube typically blocks. The paid rotating residential proxies (~$4 for 1GB) are much more reliable as they use real home IP addresses from an 80M+ IP pool.

### Other Issues

**Whisper transcription is slow**
Use a smaller model in `config.yaml`: `model: tiny` (fastest) or `model: small` (balanced).

**"No transcript available"**
Video has no captions and Whisper fallback may be disabled. Set `fallback_enabled: true` in config.

**Container won't start**
Check `.env` has valid API keys. Run `docker-compose logs` for errors.

## License

Apache 2.0
