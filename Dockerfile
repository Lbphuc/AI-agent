# ==============================================================================
# Stage 1: Build React Frontend
# ==============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Copy dependencies manifest để tận dụng Docker layer cache
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps

# Copy toàn bộ mã nguồn frontend và tiến hành build production
COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python Backend Runtime
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

# Thiết lập biến môi trường chuẩn cho Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Cài đặt curl phục vụ HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt thư viện Python (tận dụng layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy mã nguồn backend, tools, docs
COPY backend/ ./backend/
COPY tools/   ./tools/
COPY docs/    ./docs/

# Copy thành phẩm build từ Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Khai báo cổng ứng dụng
EXPOSE 8000

# Kiểm tra sức khỏe container
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Khởi chạy server FastAPI bằng Uvicorn
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]