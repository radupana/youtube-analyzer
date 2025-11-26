# Copilot Instructions for YouTube Analyzer

## Project Overview
A simple web tool (Next.js frontend + FastAPI backend) for analyzing YouTube videos using AI. Users add videos one at a time, transcripts are extracted, and they can chat about video content.

## Architecture
- **Frontend**: Next.js 15, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python 3.13+
- **Deployment**: Docker Compose
- **Storage**: Local file cache (no database)

## Code Review Focus Areas

### Code Quality
- Prefer simple functions over classes
- No over-abstraction (avoid factories, unnecessary dependency injection)
- Remove dead code, unused imports, and empty blocks
- No TODO comments - implement completely or don't add

### Testing
- All code must have tests
- Tests must validate real behavior, not mock-only code
- Backend: pytest with mocked external services
- Frontend: TypeScript strict mode catches most issues

### Python (Backend)
- Use Python 3.13+ features without compatibility shims
- Type hints required on all function signatures
- Ruff for linting, mypy for type checking
- FastAPI patterns: Pydantic models for requests/responses
- Handle errors explicitly, never silently swallow exceptions

### TypeScript (Frontend)
- Strict mode enabled
- ESLint with next/core-web-vitals config
- Prefer functional components with hooks
- Explicit typing, avoid `any`

### Security
- Never commit API keys (use environment variables)
- Validate all user inputs
- Sanitize data before external API calls
- Never log sensitive data

### What to Flag in Reviews
- Unused code or imports
- Missing error handling
- Hardcoded values that should be configurable
- Security vulnerabilities (exposed secrets, unsanitized input)
- Breaking changes without test updates
- Complex abstractions where simple functions suffice
- Async code without proper error handling

### What's Acceptable
- Simple, readable code over "clever" code
- Local file caching (no database required)
- Single video input per request (design choice)
- Docker-first deployment model
