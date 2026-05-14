# ToolStore Registry Server

The central online repository for ToolStore. This server handles:
1.  **Tool Submission:** Developers publish tools via API.
2.  **Registry Management:** Stores tool definitions in a database.
3.  **Index Distribution:** Generates and serves the `index.json` consumed by the ToolStore CLI.

## Tech Stack
- **Language:** Python 3.10+
- **Framework:** FastAPI
- **Database:** SQLite (MVP) / PostgreSQL (Production)
- **ORM:** SQLModel (SQLAlchemy + Pydantic)

## API Endpoints (Planned)
- `GET /api/v1/index` - Download the full tool index (JSON).
- `POST /api/v1/tools` - Submit a new tool definition.
- `GET /api/v1/tools/{name}` - Get details for a specific tool.
- `GET /health` - Health check.

## Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload
```
