#!/usr/bin/env bash
# 369 Studio deploy — VPS/Docker path. Run from studio369/ root.
set -e
cd "$(dirname "$0")/.."
echo "== build =="; docker compose -f server/docker-compose.yml build
echo "== up =="; docker compose -f server/docker-compose.yml up -d
echo "Live on :8080  (put nginx/caddy in front for TLS + your domain)"
