# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies - minimal set
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies to a custom directory
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.11/site-packages:$PYTHONPATH"

WORKDIR /app

# Install only runtime dependencies - remove unnecessary build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libzbar0 && \
    rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /install /install

# Copy application code
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:${PORT:-10000}/health', timeout=5)" || exit 1

EXPOSE 10000

CMD ["bash", "start.sh"]
