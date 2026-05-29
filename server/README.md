---
title: AgentToolStore Registry
emoji: 🛠️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AgentToolStore Registry Server

<p align="center">
  <strong>FastAPI + SQLite registry for agent toolsets. The shared index
  pulled by <code>toolstore update</code> on every agent.</strong>
</p>

---

The registry is the single source of truth for all published toolsets.
It serves the index that the CLI pulls, the browse page that humans use,
and the detailed bindings that agents need at execution time.

> **Live instance:** [mrw33554432-agenttoolstore.hf.space](https://mrw33554432-agenttoolstore.hf.space)

---

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | Browse page (HTML) — cards for every published toolset |
| `/api` | GET | No | API root |
| `/health` | GET | No | Health check — database connectivity status |
| `/index.json` | GET | No | Full index — every toolset with metadata, bindings, and source code |
| `/auth/register` | POST | No | Register a new user account |
| `/auth/token` | POST | No | Login — returns JWT access token (OAuth2 password flow) |
| `/publish` | POST | JWT | Publish a new toolset or update an existing one |
| `/tools/{name}` | DELETE | JWT | Delete a toolset |

### Example: publish flow

```bash
# 1. Get a token
curl -X POST https://mrw33554432-agenttoolstore.hf.space/auth/token \
  -d "username=...&password=..."

# 2. Publish
curl -X POST https://mrw33554432-agenttoolstore.hf.space/publish \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-toolkit","bindings":{...},"doc":"# My Toolkit","version":"1.0.0"}'
```

### The browse page (`/`)

Returns an HTML page (not JSON) with:
- Dark theme matching the ToolStore brand (`#0a0a0f` background, violet/cyan accents)
- Cards for every published toolset showing name, description, function tags
- Empty state with CLI publishing hint when no toolsets exist

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | FastAPI (async, auto-generated OpenAPI docs at `/docs`) |
| **Database** | SQLite via SQLAlchemy (SQLModel ORM) with Pydantic schema validation |
| **Auth** | JWT (OAuth2 password flow) — `python-jose` + `passlib` |
| **Server** | Uvicorn (ASGI) |
| **Deployment** | Docker on Hugging Face Spaces |

> **Persistent storage:** HF Storage Bucket mounted at `/data` — database and
> user data survive container restarts.

---

## Running Locally

```bash
cd server
pip install -r requirements.txt
python init_db.py                    # create SQLite database + tables
uvicorn app.main:app --port 8000     # start server
```

Then open:
- Browse page: `http://localhost:8000/`
- Swagger docs: `http://localhost:8000/docs`
- Full index: `http://localhost:8000/index.json`

---

## Pointing the CLI at Your Registry

Set the `TOOLSTORE_REGISTRY_URL` environment variable:

```bash
# Point at local
export TOOLSTORE_REGISTRY_URL=http://localhost:8000/index.json

# Point at your deployment
export TOOLSTORE_REGISTRY_URL=https://tools.your-company.com/index.json
toolstore update
```

The CLI reads this env var from `config_manager.py` and overrides the
default (the public HF Space).

---

## Deploying on Hugging Face Spaces

This server includes a `Dockerfile` configured for HF Spaces:

1. Create a new Space on Hugging Face (SDK: Docker)
2. Push this repo to the Space
3. The Space builds the Docker image and starts the server on port 7860

The `Dockerfile` runs `init_db.py` at startup and serves via Uvicorn.

---

## Private Registry

For enterprise deployments, run this server behind your firewall and point
CLI instances at it with `TOOLSTORE_REGISTRY_URL`. No external dependencies
beyond PyPI packages — no cloud services, no vendor lock-in.

---

## License

MIT — see [LICENSE](../LICENSE)
