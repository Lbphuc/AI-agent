#!/bin/bash
set -e

# Xác định thư mục gốc của dự án
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 1. Tạo thư mục cache pip trên máy host nếu chưa có 📁
CACHE_DIR="${HOME}/.cache/pip"
mkdir -p "$CACHE_DIR"

echo "🧪 Bắt đầu kiểm thử Backend (Python 3.11) với cache..."

# 2. Khởi chạy container tạm thời để test 🐳
docker run --rm \
  -v "$PROJECT_DIR":/app \
  -v "$CACHE_DIR":/root/.cache/pip \
  -w /app \
  -e PYTHONPATH=. \
  python:3.11-slim \
  bash -c "pip install -r requirements.txt && pytest -v"

echo "✅ Tất cả các bài kiểm thử Backend đã vượt qua thành công!"