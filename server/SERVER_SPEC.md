# ToolStore Server Specification

> **Status:** Planning
> **Focus:** Central Registry for Publishing & Distributing Tools

---

## 1. Core Architecture

The server acts as the "Source of Truth" for the public tool index.

### Components
1.  **API (FastAPI):** Handles publishing and index generation.
2.  **Database (SQLite/Postgres):** Stores persistent tool data and user accounts.
3.  **Storage:** Stores raw JSON tool definitions (could be DB or S3).

---

## 2. API Endpoints

### Public
*   `GET /index.json`: Returns the full list of tools (the "Index"). Cached aggressively.
*   `GET /tools/{name}`: Returns details for a specific tool.
*   `GET /search?q=...`: Server-side search (optional, since client does local search).

### Publisher (Authenticated)
*   `POST /auth/register`: Create a developer account.
*   `POST /auth/login`: Get an API token.
*   `POST /tools/publish`: Upload a new tool definition (`tool.json`).
    *   Validates schema.
    *   Checks namespace ownership.
    *   Updates the database.

---

## 3. Database Schema (SQLModel)

### User
*   `id`: int
*   `username`: str (unique)
*   `email`: str
*   `password_hash`: str
*   `created_at`: datetime

### Tool
*   `id`: int
*   `name`: str (unique)
*   `owner_id`: int (FK -> User)
*   `version`: str
*   `type`: str ('api', 'mcp')
*   `description`: str
*   `definition`: JSON (The full tool schema)
*   `created_at`: datetime
*   `updated_at`: datetime
*   `downloads`: int

---

## 4. Implementation Plan

### Phase 1: Project Skeleton
- [ ] Initialize FastAPI project (`server/app`).
- [ ] Setup SQLModel database connection.
- [ ] Create User and Tool models.

### Phase 2: Authentication
- [ ] Implement User Registration.
- [ ] Implement Login (JWT Tokens).
- [ ] Protect publish endpoints.

### Phase 3: Publishing Flow
- [ ] Implement `POST /tools/publish`.
- [ ] Add JSON Schema validation for uploaded tools.
- [ ] Ensure unique names.

### Phase 4: Index Generation
- [ ] Implement `GET /index.json`.
- [ ] Query DB -> Format as massive JSON list.
- [ ] Add simple caching headers.

---

**Goal:** A running server where I can POST a tool JSON and then GET index.json to see it.

