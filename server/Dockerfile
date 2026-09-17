# 369 Studio — Creator backend
FROM python:3.11-slim

# ffmpeg (QC tiles + audio), curl (runners upload refs)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

# copy the whole studio369 repo (runners live in tools/)
COPY . /app

# keys are mounted at runtime, not baked in:  -v ~/.config:/root/.config:ro
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8080"]
