#!/bin/bash
set -e

echo "=== [1/2] Di chuyen vao thu muc ung dung ==="
cd /home/phuc/ai-agent-app

echo "=== [2/2] Keo image moi va khoi chay container ==="
docker compose pull
docker rm -f ai-agent-app 2>/dev/null || true
OPENAI_API_KEY="$OPENAI_API_KEY" docker compose up -d --force-recreate

echo "Deploy thanh cong!"