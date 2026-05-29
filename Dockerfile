# ── Hugging Face Spaces Dockerfile ──────────────────────────────────────
#
#  HF Spaces requirements:
#   • Container runs as user ID 1000  
#   • App must listen on port 7860
#   • Dockerfile must be at repo root
#
#  The server code lives in server/; this Dockerfile builds from there.
# ──────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

COPY --chown=user server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user server/ .

EXPOSE 7860

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
