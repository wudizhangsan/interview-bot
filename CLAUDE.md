# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Interview Pilot (AI 面试助手) — an LLM-powered mock interview and evaluation system. It parses resumes and job descriptions (JDs), generates tailored interview syllabi, simulates multi-round interviews with drill-down追问, and produces quantitative evaluation reports.

## Tech Stack

- **Python 3.12** with async/await throughout
- **OpenAI Agents SDK** (`openai-agents` v0.6.1) for agent orchestration and streaming
- **Pydantic v2** for all data models and config validation
- **Jina AI API** (`s.jina.ai` search, `r.jina.ai` fetch) for web search and URL content extraction
- **pytest + pytest-asyncio** for testing
- **pandas** for data processing

## Project Structure

```
├── agent/
│   └── base.py            # BaseAgent class: wraps OpenAI Agents SDK Agent + Runner, supports streaming
├── schema/
│   ├── system_config.py   # SystemConfig Pydantic model, loads JSON config, sets OPENAI_API_KEY/BASE_URL env vars on init
│   └── url.py             # SearchResult Pydantic model for search results
├── tools/
│   └── jina.py            # search_keyword() and fetch_url() via Jina AI APIs
├── config/
│   └── system_config.json # API keys, base URL, default model name
├── tests/
│   └── test_jina.py       # Async tests for Jina tools
├── README.md              # Full project spec (interview flow, evaluation reports)
└── CLAUDE.md
```

## Architecture Notes

- **SystemConfig** (`schema/system_config.py:11`) has a `model_validator` that automatically sets `OPENAI_API_KEY` and `OPENAI_BASE_URL` environment variables when loaded — this is how the OpenAI Agents SDK is configured.
- **BaseAgent** (`agent/base.py:16`) uses `SQLiteSession` for conversation persistence (creates a new session per instance with a UUID name).
- **Jina tools** (`tools/jina.py`) use synchronous `requests` wrapped in async functions — could be refactored to `httpx.AsyncClient` for true async.
- The config file (`config/system_config.json`) contains live API keys — do not commit this to version control.

## Common Commands

```bash
# Run all tests
python3 -m pytest tests/

# Run a single test file
python3 -m pytest tests/test_jina.py -v

# Run a specific test
python3 -m pytest tests/test_jina.py::test_fetch_url -v

# Run with coverage
python3 -m pytest tests/ --cov=. --cov-report=term

# Run the agent directly
python3 -m agent.base

# Run Jina search tool directly
python3 -m tools.jina
```

## Test Style

- Tests are async functions (using `pytest-asyncio`)
- Tests import `load_system_config` at module level, which triggers env var setup
- No `conftest.py` or `pytest.ini` exists yet — test configuration is minimal
