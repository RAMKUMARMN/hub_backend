# Stage 1: Build dependencies and wheels
FROM python:3.11-slim AS builder

WORKDIR /build

# Install compilation tools needed for packages like bcrypt/cryptography/asyncpg if wheels are missing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python packages system-wide (/usr/local)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Final lightweight image
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime dependencies (like postgresql-client for potential health checks/DB operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from the builder stage (/usr/local is accessible by all users)
COPY --from=builder /usr/local /usr/local

# Copy application source code
COPY . .

# Ensure entrypoint script is executable
RUN chmod +x /app/scripts/entrypoint.sh

# Create a non-privileged user and group to run the app securely
RUN groupadd -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup appuser && \
    chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the port FastAPI runs on
EXPOSE 8000

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Use the entrypoint script to run migrations and start FastAPI
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
