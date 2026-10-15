#!/bin/bash
set -e

echo "=== [1/3] Đăng nhập GitLab Registry ==="
echo "$GITLAB_TOKEN_PSW" | docker login 34.21.252.216:5050 -u "$GITLAB_TOKEN_USR" --password-stdin

echo "=== [2/3] Build Docker Image ==="
docker build -t "$IMAGE_NAME" .

echo "=== [3/3] Push Docker Image ==="
docker push "$IMAGE_NAME"

echo "Build và Push lên GitLab Registry hoàn tất!"