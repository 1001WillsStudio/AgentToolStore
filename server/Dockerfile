# ── Hugging Face Spaces compatible Dockerfile ────────────────────────────
#
#  HF Spaces requirements:
#   • Container runs as user ID 1000
#   • App must listen on port 7860
#   • Set WORKDIR before COPY to avoid permission issues
#
#  Usage:
#   docker build -t toolstore-registry .
#   docker run -p 7860:7860 toolstore-registry
# ──────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── System dependencies ──────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root user (HF Spaces requires UID 1000) ───────────────────
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

# ── Install Python dependencies ──────────────────────────────────────────
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy application code ────────────────────────────────────────────────
COPY --chown=user . .

# ── Ensure data directory exists (for SQLite + future persistence) ───────
RUN mkdir -p /home/user/app/data

# ── Expose HF Spaces default port ────────────────────────────────────────
EXPOSE 7860

# ── Start the registry server ────────────────────────────────────────────
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
