#!/bin/bash
set -e

# Xác định thư mục gốc của dự án
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 1. Tạo thư mục cache npm trên máy host nếu chưa có 📁
CACHE_DIR="${HOME}/.npm"
mkdir -p "$CACHE_DIR"

echo "📦 Bắt đầu kiểm tra biên dịch Frontend (Node.js 20) với cache..."

# 2. Khởi chạy container tạm thời để kiểm tra build 🐳
docker run --rm \
  -v "$PROJECT_DIR/frontend":/app \
  -v "$CACHE_DIR":/root/.npm \
  -w /app \
  node:20-slim \
  bash -c "npm install --legacy-peer-deps && npm run build"

echo "✅ Kiểm tra biên dịch Frontend hoàn tất thành công!"