# JuiceLab Coach sidecar for OWASP PwnzzAI.
# Transparent reverse proxy + pedagogical API. Leaves PwnzzAI untouched.
FROM python:3.11-slim

WORKDIR /coach

COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip install --retries 10 --timeout 600 -r requirements.txt

COPY app.py llm_judge.py dashboard_client.py labs.json briefing.json quiz.json ./
COPY static ./static

ENV COACH_PORT=8090 \
    PWNZZAI_UPSTREAM=http://pwnzzai-app:8080 \
    OLLAMA_HOST=http://ollama:11434 \
    PYTHONUNBUFFERED=1

EXPOSE 8090

# Single worker keeps the in-process httpx clients simple; the workload is
# I/O bound (proxy + ollama) so async on one worker is plenty for a class.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${COACH_PORT}"]
