#!/bin/bash
set -e

APP_DIR="/home/phuc/ai-agent-app"
cd "$APP_DIR"

IMAGE_NAME="34.21.186.237:5050/root/ai-agent:${BUILD_NUMBER}"
UPSTREAM_FILE="/etc/nginx/conf.d/upstream.inc"

# 1. Xác định cổng đang chạy và cổng tiếp theo 🔍
if grep -q "8001" "$UPSTREAM_FILE"; then
    CURRENT_PORT=8001
    NEXT_PORT=8002
    OLD_CONTAINER="ai-agent-blue"
    NEW_CONTAINER="ai-agent-green"
else
    CURRENT_PORT=8002
    NEXT_PORT=8001
    OLD_CONTAINER="ai-agent-green"
    NEW_CONTAINER="ai-agent-blue"
fi

echo "=== Đang chạy trên: $OLD_CONTAINER (Port: $CURRENT_PORT) ==="
echo "=== Chuẩn bị triển khai: $NEW_CONTAINER (Port: $NEXT_PORT) với phiên bản: ${BUILD_NUMBER} ==="

# 2. Kéo image mới và dọn dẹp container mới nếu còn sót từ lượt trước 🚀
docker pull "$IMAGE_NAME"
docker rm -f "$NEW_CONTAINER" 2>/dev/null || true

# 3. Khởi chạy container mới ở cổng rảnh 🐳
docker run -d \
  --name "$NEW_CONTAINER" \
  -p "${NEXT_PORT}:8000" \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  --restart unless-stopped \
  "$IMAGE_NAME"

# 4. Kiểm tra sức khỏe (Health Check) 🩺
echo "Đang kiểm tra dịch vụ tại cổng ${NEXT_PORT}..."
sleep 10

if curl -f -s -o /dev/null "http://localhost:${NEXT_PORT}"; then
    echo "✅ Health Check thành công! Chuyển lưu lượng sang ${NEW_CONTAINER} (Port: ${NEXT_PORT})..."
    
    # Đổi cổng upstream và nạp lại Nginx 🔄
    echo "server 127.0.0.1:${NEXT_PORT};" | sudo tee "$UPSTREAM_FILE" > /dev/null
    sudo nginx -s reload
    
    # Dọn dẹp container cũ và dọn dẹp container ban đầu (port 8000 nếu có) 🧹
    echo "Dọn dẹp container phiên bản cũ..."
    docker rm -f "$OLD_CONTAINER" 2>/dev/null || true
    docker rm -f "ai-agent-app" 2>/dev/null || true
    
    # Dọn bớt image rác
    docker image prune -f
    echo "=== Triển khai Zero-Downtime hoàn tất! ==="
else
    echo "❌ Health Check thất bại! Hủy bỏ lượt triển khai."
    # Giữ nguyên Nginx, chỉ dọn dẹp container mới bị lỗi 🛑
    docker rm -f "$NEW_CONTAINER" 2>/dev/null || true
    exit 1
fi