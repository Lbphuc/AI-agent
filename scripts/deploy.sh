#!/bin/bash
set -e

echo "=== [1/2] Di chuyen vao thu muc ung dung ==="
cd /home/phuc/ai-agent-app

echo "=== [2/2] Keo image moi va khoi chay container ==="
docker compose pull
OPENAI_API_KEY="$OPENAI_API_KEY" docker compose up -d

echo "Deploy thanh cong!"