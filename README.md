# YouTube Analyzer

Analyze YouTube channels using AI-powered transcript extraction and analysis. Simple conversational interface, local caching, and LLM-agnostic design.

[![CI](https://github.com/radupana/youtube-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/radupana/youtube-analyzer/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/radupana/youtube-analyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/radupana/youtube-analyzer)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue)](http://mypy-lang.org/)

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/radupana/youtube-analyzer.git
cd youtube-analyzer
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e .

# 2. Configure with environment variables
cp config.example.yaml config.yaml
export GEMINI_API_KEY="your-gemini-api-key"
export YOUTUBE_API_KEY="your-youtube-api-key"

# 3. Run
python -m yt_agent_kit
```

## What It Does

This tool helps you analyze YouTube channels through a simple conversational interface:

1. **Ask for Channel**: Provide channel name, @handle, URL, or channel ID
2. **Specify Intent**: Describe what you want to learn (e.g., "summarize fitness advice")
3. **Choose Format**: Select output format (human-readable, JSON, or Markdown)
4. **Select Videos**: Choose how many videos to analyze
5. **Extract Transcripts**: Automatically fetches and cleans video transcripts
6. **Analyze** *(Coming in Phase 4)*: LLM analyzes transcripts based on your intent

## Installation

### Prerequisites

- Python 3.13 or higher
- Google API credentials (for YouTube Data API v3 and Gemini)
- Git

### Step-by-Step Setup

**1. Clone the Repository**

```bash
git clone https://github.com/radupana/youtube-analyzer.git
cd youtube-analyzer
```

**2. Create Virtual Environment**

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

**3. Install Dependencies**

```bash
pip install -e .
```

This installs the package in editable mode with all dependencies.

**4. Get API Keys**

You need two API keys (can use the same Google API key for both):

- **YouTube Data API v3 Key**: [Get it here](https://console.cloud.google.com/apis/credentials)
- **Gemini API Key**: [Get it here](https://aistudio.google.com/app/apikey)

**5. Configure**

```bash
cp config.example.yaml config.yaml
```

**Set your API keys using environment variables (recommended):**

```bash
export GEMINI_API_KEY="your-gemini-api-key"
export YOUTUBE_API_KEY="your-youtube-api-key"
```

The default `config.yaml` uses environment variable notation:

```yaml
llm:
  provider: "gemini"
  api_key: "${GEMINI_API_KEY}"  # ✅ Uses environment variable
  model: "gemini-2.0-flash"

youtube_api_key: "${YOUTUBE_API_KEY}"  # ✅ Uses environment variable
```

**Why environment variables?**
- ✅ Never accidentally commit secrets to git
- ✅ Easy to switch between dev/prod keys
- ✅ Works with CI/CD and deployment tools
- ✅ Standard practice for secure configuration

**Alternative: Add to your shell profile** (persists across sessions)

```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'export GEMINI_API_KEY="your-key"' >> ~/.zshrc
echo 'export YOUTUBE_API_KEY="your-key"' >> ~/.zshrc
source ~/.zshrc
```

**Only if you must:** You can hardcode keys directly in `config.yaml`, but this is **not recommended**:

```yaml
api_key: "AIza..."  # ⚠️ Not recommended - easy to accidentally commit
```

## Usage

### Basic Usage

```bash
python -m yt_agent_kit
```

The tool will guide you through:

```
Hi! What YouTube channel are we analyzing today?
(You can provide a channel name, @handle, URL, or channel ID)

Channel: Jeff Nippard

Searching for 'Jeff Nippard'...

Great! I found the channel:
  Title: Jeff Nippard
  Subscribers: 4,500,000
  Total Videos: 250
  Handle: @JeffNippard
  Description: Evidence-based muscle building and fat loss...

What are you looking to get out of the analysis?
(Examples: 'summarize key advice', '4-week strength training block', etc.)

Intent: summarize his training philosophy

How would you like the results?
  1. Human-readable (default)
  2. JSON
  3. Markdown

Choice [1]: 1

How many videos should I analyze?
  Available: 250 videos
  Maximum: 200 videos

Videos [50]: 10

Fetching video list from YouTube...
Fetching transcripts for 10 videos...
Progress: 1/10 (10%) - Fetching: 'The Science of Hypertrophy'
Progress: 2/10 (20%) - Fetching: 'Protein Intake Guide'
...
✅ Successfully fetched 10/10 transcripts

Phase 3 Complete: Transcript Acquisition
============================================================
Channel: Jeff Nippard (UC...)
Intent: summarize his training philosophy
Output Format: human
Videos Fetched: 10
Transcripts Retrieved: 10
============================================================
```

### Advanced Options

```bash
# Use custom config file
python -m yt_agent_kit --config my-config.yaml

# Override max videos
python -m yt_agent_kit --max-videos 25

# Override output file
python -m yt_agent_kit --output analysis.json
```

## Testing Your Setup

### 1. Run the Test Suite

Verify everything works:

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src/yt_agent_kit --cov-report=term-missing

# Run specific test file
python -m pytest tests/test_transcript.py -v
```

Expected output:
```
========================= 97 passed in 0.19s =========================
```

### 2. Quick Smoke Test

Test with a small, known channel:

```bash
python -m yt_agent_kit
```

When prompted:
- Channel: `@PrimerBlobs` (small educational channel)
- Intent: `test run`
- Format: `1` (human-readable)
- Videos: `3`

This should complete in under 30 seconds and fetch 3 transcripts.

### 3. Verify Caching

Run the same channel twice - the second run should be much faster due to caching:

```bash
# First run - fetches from APIs
time python -m yt_agent_kit
# (follow prompts)

# Second run - uses cache
time python -m yt_agent_kit
# (same inputs - notice it's faster)
```

Check the cache directory:
```bash
ls -la .cache/
```

You should see cached channel info, videos, and transcripts.

## Project Structure

```
youtube-analyzer/
├── README.md              # This file
├── CLAUDE.md             # Development guidelines
├── pyproject.toml        # Dependencies and build config
├── config.example.yaml   # Configuration template
├── config.yaml           # Your local config (gitignored)
├── .cache/               # Local cache (gitignored)
├── src/
│   └── yt_agent_kit/
│       ├── __init__.py
│       ├── __main__.py   # CLI entry point
│       ├── config.py     # Configuration loading
│       ├── agent.py      # Conversational agent
│       ├── youtube.py    # YouTube API integration
│       ├── transcript.py # Transcript fetching/cleaning
│       └── cache.py      # Local file caching
└── tests/                # Comprehensive test suite
    ├── test_agent.py
    ├── test_cache.py
    ├── test_config.py
    ├── test_main.py
    ├── test_transcript.py
    └── test_youtube.py
```

## Features

### Current (Phase 3 Complete)

- ✅ **Conversational Interface**: User-friendly prompts for channel, intent, and format
- ✅ **Channel Discovery**: Find channels by name, @handle, URL, or channel ID
- ✅ **Video Listing**: Fetch video metadata with pagination support
- ✅ **Transcript Extraction**: Download and clean video transcripts
- ✅ **Progress Indicators**: Real-time progress for batch operations
- ✅ **Local Caching**: Fast repeated runs with file-based cache
- ✅ **Error Handling**: Graceful handling of missing transcripts and API errors
- ✅ **Test Coverage**: 94% code coverage with comprehensive tests

### Coming Soon (Phase 4)

- ⏳ **LLM Analysis**: AI-powered extraction based on user intent
- ⏳ **Multi-provider Support**: OpenAI, Anthropic, local models
- ⏳ **Intent Mapping**: Smart extraction based on natural language goals
- ⏳ **Output Formatting**: Clean, structured results in multiple formats

## Troubleshooting

### "Config file not found"

```bash
# Make sure you copied the example config
cp config.example.yaml config.yaml

# Or specify a custom path
python -m yt_agent_kit --config /path/to/config.yaml
```

### "Invalid API key" or "Quota exceeded"

- Verify your API keys are correct in `config.yaml`
- Check your [Google Cloud Console](https://console.cloud.google.com/apis/credentials) for quota limits
- YouTube Data API has a daily quota - wait 24 hours if exceeded

### "No transcript available"

Some videos don't have transcripts. The tool will:
- Skip videos without transcripts
- Continue processing remaining videos
- Report how many were successfully fetched

### Tests Failing

```bash
# Ensure you're in the virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -e .

# Run tests with verbose output
python -m pytest -v
```

## Development

### Running Tests

```bash
# All tests
python -m pytest

# With coverage
python -m pytest --cov=src/yt_agent_kit

# Specific test file
python -m pytest tests/test_transcript.py -v

# Single test
python -m pytest tests/test_transcript.py::TestCleanTranscript::test_removes_music_markers -v
```

### Code Quality

```bash
# Format code
make format
# or
black src tests
ruff check --fix src tests

# Type checking
make lint
# or
mypy src

# Run all checks
make check
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## FAQ

**Q: Can I use a different LLM provider?**

A: Yes! The tool is LLM-agnostic. Edit `config.yaml`:

```yaml
llm:
  provider: "openai"
  api_key: "${OPENAI_API_KEY}"
  model: "gpt-4o-mini"
```

Support for OpenAI, Anthropic, and local models coming in Phase 4.

**Q: How much does it cost?**

A: Costs depend on your API usage:
- YouTube Data API: Free tier (10,000 units/day) is usually sufficient
- Gemini API: Free tier available, ~$0.001 per video for transcript analysis
- For 100 videos: typically < $0.10

**Q: Can I analyze private/unlisted videos?**

A: No, the tool only works with public videos that have transcripts enabled.

**Q: Where is my data stored?**

A: Everything is local:
- Config: `config.yaml` (in repo root)
- Cache: `.cache/` directory (gitignored)
- Results: `results.json` or your specified output file

**Q: How do I clear the cache?**

```bash
rm -rf .cache/
```

**Q: Can I run this on Windows?**

A: Yes! Use:
```cmd
python -m venv venv
venv\Scripts\activate
pip install -e .
python -m yt_agent_kit
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please:
1. Read `CLAUDE.md` for development guidelines
2. Write tests for new features
3. Ensure all tests pass (`pytest`)
4. Format code (`black`, `ruff`)
5. Type check (`mypy`)

## Support

- Issues: [GitHub Issues](https://github.com/radupana/youtube-analyzer/issues)
- Documentation: This README and `CLAUDE.md`
- Examples: See `config.example.yaml`
