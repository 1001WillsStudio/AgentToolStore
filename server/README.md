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

## 🚀 Deploy to Hugging Face Spaces (Free)

The registry is pre-configured for one-click deployment to Hugging Face Spaces.

### Why HF Spaces?

- **16 GB RAM**, 2 vCPUs, 50 GB disk — more than enough for the tool index
- **48-hour sleep timer** — stays alive as long as anyone pings it daily
- **Right next to your audience** — the AI/ML community is already on HF
- **Free** — no credit card required

### One-time setup

```bash
# 1. Create a new Space on Hugging Face
#    Go to https://huggingface.co/new-space
#    Name: toolstore-registry (or anything you like)
#    SDK: Docker
#    Leave "Blank" template selected

# 2. Clone the empty Space repo
GIT_USER=your-username
GIT_SPACE=toolstore-registry
git clone https://huggingface.co/spaces/$GIT_USER/$GIT_SPACE
cd $GIT_SPACE

# 3. Copy the server files into the Space (from your AgentToolStore repo)
cp -r /path/to/AgentToolStore/server/* .
rm README.md  # HF auto-generates one; replace with ours below

# 4. Create the HF Spaces README with Docker SDK config
cat > README.md << 'EOF'
---
title: AgentToolStore Registry
emoji: 🛠️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AgentToolStore Registry

The public tool index powering [AgentToolStore](https://github.com/Mrw33554432/AgentToolStore) —
the "pip for AI Agents."

## API

| Endpoint | Description |
|---|---|
| `/index.json` | Full tool index — what `toolstore update` pulls |
| `/health` | Health check + tool count |
| `/auth/register` | Create a developer account |
| `/auth/token` | Get an API token |
| `/publish` | Publish a new tool (authenticated) |
EOF

# 5. Push to deploy
GIT_USER=your-username
git add -A && git commit -m "Deploy ToolStore registry"
git push
```

Once pushed, HF builds the Docker image (~2-3 minutes first time) and your
registry is live at:

```
https://huggingface.co/spaces/$GIT_USER/$GIT_SPACE
```

The tool index will be available at:

```
https://$GIT_USER-$GIT_SPACE.hf.space/index.json
```

### Point your CLI at it

```bash
toolstore config set registry_url https://$GIT_USER-$GIT_SPACE.hf.space/index.json
toolstore update
```

> ⚠️ **Alpha note**: HF Spaces have ephemeral storage — the database resets on
> container restart.  We'll add persistent storage (HF Storage Buckets or Turso)
> before Beta.  For now this is perfect for development and demos.

---

## 📖 Development Status

**Current Phase:** Alpha — core publishing flow and index generation.

See [`SERVER_SPEC.md`](SERVER_SPEC.md) for the detailed implementation plan.
