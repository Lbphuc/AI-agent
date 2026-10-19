#!/bin/bash
set -e

APP_DIR="/home/phuc/ai-agent-app"
cd "$APP_DIR"

# 1. Cấu hình biến môi trường và file định tuyến ⚙️
IMAGE_NAME="${IMAGE_NAME:-34.21.186.237:5050/root/ai-agent:${BUILD_NUMBER}}"
UPSTREAM_FILE="/etc/nginx/conf.d/upstream.inc"

# 2. Xác định cổng đang chạy và cổng mục tiêu tiếp theo 🔍
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

echo "=== 🔄 Trạng thái hiện tại: $OLD_CONTAINER (Port: $CURRENT_PORT) ==="
echo "=== 🚀 Chuẩn bị triển khai: $NEW_CONTAINER (Port: $NEXT_PORT) với phiên bản: ${BUILD_NUMBER} ==="

# 3. Kéo image mới và dọn dẹp container trùng tên nếu còn sót 📦
docker pull "$IMAGE_NAME"
docker rm -f "$NEW_CONTAINER" 2>/dev/null || true

# 4. Khởi chạy container mới ở cổng rảnh 🐳
docker run -d \
  --name "$NEW_CONTAINER" \
  -p "${NEXT_PORT}:8000" \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  --restart unless-stopped \
  "$IMAGE_NAME"

# 5. Kiểm tra sức khỏe với vòng lặp thử lại (Retry Loop) 🩺
echo "⏳ Đang kiểm tra dịch vụ tại cổng ${NEXT_PORT} (tối đa 30 giây)..."
SUCCESS=false

for i in {1..15}; do
    echo "Kiểm tra lần $i/15..."
    if curl -f -s -o /dev/null "http://localhost:${NEXT_PORT}"; then
        echo "✅ Dịch vụ đã sẵn sàng và phản hồi tốt!"
        SUCCESS=true
        break
    fi
    sleep 2
done

# 6. Phân nhánh xử lý dựa trên kết quả Health Check 🔀
if [ "$SUCCESS" = true ]; then
    echo "🎉 Health Check thành công! Chuyển lưu lượng sang ${NEW_CONTAINER} (Port: ${NEXT_PORT})..."
    
    # Đổi cổng upstream và nạp lại Nginx không gián đoạn ⚡
    echo "server 127.0.0.1:${NEXT_PORT};" | sudo tee "$UPSTREAM_FILE" > /dev/null
    sudo nginx -s reload
    
    # Dọn dẹp container phiên bản cũ 🧹
    echo "🧹 Dọn dẹp container cũ..."
    docker rm -f "$OLD_CONTAINER" 2>/dev/null || true
    docker rm -f "ai-agent-app" 2>/dev/null || true
    
    # Dọn bớt Docker image rác không còn gắn tag
    docker image prune -f
    echo "=== 🎯 Triển khai Blue/Green hoàn tất thành công! ==="
else
    echo "❌ Health Check thất bại sau 15 lần thử! Hủy bỏ lượt triển khai."
    # Giữ nguyên Nginx, chỉ dọn dẹp container mới bị lỗi 🛑
    docker rm -f "$NEW_CONTAINER" 2>/dev/null || true
    exit 1
fi