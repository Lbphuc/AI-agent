#!/bin/bash
set -e

TARGET_SERVER="phuc@34.21.186.237"

echo "=== Trien khai len $TARGET_SERVER ==="
ssh -o StrictHostKeyChecking=no "$TARGET_SERVER" "cd ~/ai-agent-app && docker compose pull && OPENAI_API_KEY='$OPENAI_API_KEY' docker compose up -d"

echo "Deploy thanh cong!"