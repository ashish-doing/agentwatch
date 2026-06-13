# agentwatch/Dockerfile
# Combined backend (FastAPI) + frontend (static files) image for Railway.
#
# main.py mounts frontend/ as static files and serves frontend/index.html
# at "/", so this is a single-service deployment.

FROM python:3.11-slim

WORKDIR /app

# Install backend dependencies first (better layer caching)
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy the rest of the repo (backend + frontend)
COPY . .

# Railway provides $PORT; default to 8001 for local docker runs
ENV PORT=8001
EXPOSE 8001

CMD uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT}