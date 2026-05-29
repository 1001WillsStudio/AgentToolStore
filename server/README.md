---
title: AgentToolStore Registry
emoji: 🛠️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🛠️ AgentToolStore Registry

<p align="center">
  <strong>The backbone of the agent tool ecosystem — powering discovery, publishing, and trust.</strong>
</p>

---

The registry server is what makes AgentToolStore more than just a local tool runner.
It is the **shared index** that turns a scattered collection of tools into a unified,
searchable, versioned ecosystem — the same role that PyPI plays for Python packages.

---

## 📡 API Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `GET /` | Public | Welcome message |
| `GET /health` | Public | Health check + tool count |
| `GET /index.json` | Public | Full tool index — what `toolstore update` pulls |
| `POST /auth/register` | Public | Create a developer account |
| `POST /auth/token` | Public | Obtain an API token (OAuth2 form) |
| `POST /publish` | Token | Publish a new tool (authenticated) |
| `DELETE /tools/{name}` | Token | Delete a tool (authenticated) |

---

## 🔧 Tech Stack

- **Framework:** FastAPI
- **Database:** SQLite (MVP) → PostgreSQL (Production)
- **ORM:** SQLModel (SQLAlchemy + Pydantic)

---

## 🚀 Quick Start (Local)

```bash
cd server
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## 🏢 Private Registry

Point a ToolStore CLI at your own server for a fully private,
enterprise-governed tool catalog:

```json
{
  "registry_url": "https://tools.your-company.com/index.json"
}
```

---

## 🔗 Point your CLI at this Space

```bash
toolstore config set registry_url https://YOUR_USERNAME-TOOLSTORE-REGISTRY.hf.space/index.json
toolstore update
```

> 💾 **Persistent storage**: This Space uses an HF Storage Bucket mounted at
> `/data` — database and user data survive container restarts.

---

## 📖 Development Status

**Current Phase:** Alpha — core publishing flow and index generation.

See [`SERVER_SPEC.md`](SERVER_SPEC.md) for the detailed implementation plan.
