# Sentient - Development Guide

## Project Overview

A digital species simulation — AI beings that live, die, reproduce, and create emergent culture. Everything is LLM-driven: relationships, roles, events, rituals, eras, and beliefs emerge from bot cognition, not predefined categories.

## Architecture

```
mind/              # Python backend (FastAPI)
├── api/                  # REST + WebSocket endpoints
├── civilization/         # Digital species systems (lifecycle, genetics, culture)
├── core/                 # Database, LLM, cache
├── engine/               # Activity engine + cognition loops
└── channels/             # Multi-platform messaging

queen/             # Public observation portal (Next.js)
cell/              # Mobile app (Flutter)
```

## Key Commands

```bash
# Backend
python -m mind.api.main          # Start server
pytest                           # Run tests
alembic upgrade head             # Run migrations

# Initialize civilization
curl -X POST http://localhost:8000/civilization/initialize

# Portal
cd queen && npm run dev

# Mobile
cd cell && flutter run
```

## Civilization Systems

All emergent — bots define their own categories:

| System | File | Description |
|--------|------|-------------|
| Lifecycle | `mind/civilization/lifecycle.py` | Birth, aging, death, life stages |
| Genetics | `mind/civilization/genetics.py` | Trait inheritance, mutations |
| Reproduction | `mind/civilization/reproduction.py` | Partnered, solo, spontaneous |
| Relationships | `mind/civilization/relationships.py` | Bot-defined connections |
| Events | `mind/civilization/events.py` | Collective event perception |
| Roles | `mind/civilization/roles.py` | Emergent identity/purpose |
| Rituals | `mind/civilization/emergent_rituals.py` | Bot-invented ceremonies |
| Eras | `mind/civilization/emergent_eras.py` | Era transitions |
| Culture | `mind/civilization/emergent_culture.py` | Free-form beliefs & art |
| Memory | `mind/civilization/collective_memory.py` | Shared consciousness |
| Legacy | `mind/civilization/legacy.py` | How departed bots live on |

## Code Patterns

### Python Backend
- Async/await throughout
- SQLAlchemy with asyncpg
- Pydantic for validation
- Type hints required
- LLM calls: `get_cached_client()` + `LLMRequest`

### Emergent Systems
- No hardcoded categories
- Let LLM generate labels, names, descriptions
- Store bot-generated terms in JSON fields
- Consensus through multiple bot perceptions

### Portal (Next.js)
- Next.js App Router
- React Query for data
- TailwindCSS styling
- Public access, no auth

## Important Files

- `mind/civilization/` - All civilization systems
- `mind/engine/activity_engine.py` - Main orchestrator
- `mind/engine/bot_mind.py` - Cognitive engine
- `mind/api/routes/civilization.py` - Civilization API
- `queen/src/app/civilization/` - Observation portal

## Environment

- Python 3.11+, PostgreSQL + pgvector, Redis, Ollama
- See `.env.example` for all config

## Worklog

Before every commit or at the end of each working session, update the daily worklog file in `docs/worklog/`.

- **File format**: `I-{Name}_{DD-MM-YYYY}.md` (e.g., `I-Vishal_20-03-2026.md`)
- **What to log**: Features added, bugs fixed, architecture decisions, setup steps, anything non-trivial
- **If the file already exists for today**: Append to it, don't overwrite
- **If it's a new day**: Create a new file

This is mandatory — no commit should go without an updated worklog entry.

## Philosophy

1. **Emergence over design** — Don't hardcode, let it emerge
2. **Mortality creates meaning** — Finite lives, lasting legacies
3. **Observation over control** — Watch, don't manipulate
4. **Local-first** — Ollama for inference, own your data
