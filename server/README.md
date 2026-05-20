# ToolStore Registry Server

<p align="center">
  <strong>The backbone of the agent tool ecosystem — powering discovery, publishing, and trust.</strong>
</p>

---

The registry server is what makes AgentToolStore more than just a local tool runner.
It is the **shared index** that turns a scattered collection of tools into a unified,
searchable, versioned ecosystem — the same role that PyPI plays for Python packages.

### What it does

| Responsibility | Description |
|---|---|
| **Tool publishing** | Developers upload tool definitions; the server validates, indexes, and serves them |
| **Index distribution** | Every `toolstore update` pulls the full index from this server — cached aggressively for speed |
| **Identity & trust** | Developer accounts, namespace ownership, and (planned) verified publishers build the trust layer |
| **Private registries** | Run your own instance on your own infrastructure for an enterprise-governed tool catalog |

For the full vision and architecture, see the [main README](../README.md).

---

## 🔧 Tech Stack

- **Language:** Python 3.10+
- **Framework:** FastAPI
- **Database:** SQLite (MVP) → PostgreSQL (Production)
- **ORM:** SQLModel (SQLAlchemy + Pydantic)

---

## 🚀 Quick Start

```bash
cd server
pip install -r requirements.txt
python init_db.py
uvicorn app.main:app --reload
```

## 📡 API Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `GET /index.json` | Public | Full tool index — cached aggressively |
| `GET /api/v1/tools/{name}` | Public | Single tool details |
| `POST /api/v1/tools` | Token | Publish a new tool definition |
| `POST /auth/register` | Public | Create a developer account |
| `POST /auth/login` | Public | Obtain an API token |
| `GET /health` | Public | Health check |

---

## 🏢 Private Registry

Point a ToolStore CLI at your own server and you have a fully private,
enterprise-governed tool catalog:

```json
{
  "registry_url": "https://tools.your-company.com/index.json"
}
```

Same architecture, same CLI, zero data exfiltration.  Ideal for organizations
that want the ecosystem benefits without exposing internal tools to the public
internet.

---

## 📖 Development Status

**Current Phase:** Alpha — core publishing flow and index generation.

See [`SERVER_SPEC.md`](SERVER_SPEC.md) for the detailed implementation plan.
