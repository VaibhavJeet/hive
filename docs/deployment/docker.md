# Docker Deployment Guide

This guide covers deploying the Hive using Docker.

---

## Quick Start with Docker Compose

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Ollama installed on host (for GPU access)

### Start Infrastructure

```bash
cd mind

# Start PostgreSQL and Redis
docker-compose up -d

# Wait for services to be ready
sleep 5

# Enable pgvector extension
docker exec -it ai-postgres psql -U postgres -d mind -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Verify Services

```bash
# Check container status
docker-compose ps

# Check PostgreSQL
docker exec -it ai-postgres psql -U postgres -d mind -c "SELECT 1;"

# Check Redis
docker exec -it ai-redis redis-cli ping
```

---

## Docker Compose Configuration

### Current Configuration (`docker-compose.yml`)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg18
    container_name: ai-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: mind
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:latest
    container_name: ai-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

---

## Full Stack Docker Compose

For a complete containerized deployment:

### `docker-compose.full.yml`

```yaml
services:
  # PostgreSQL with pgvector
  postgres:
    image: pgvector/pgvector:pg18
    container_name: ai-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-mind}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    container_name: ai-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # API Server
  api:
    build:
      context: ..
      dockerfile: mind/Dockerfile
    container_name: ai-api
    environment:
      AIC_DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-mind}
      AIC_REDIS_URL: redis://redis:6379/0
      AIC_OLLAMA_BASE_URL: http://host.docker.internal:11434
      AIC_OLLAMA_MODEL: ${OLLAMA_MODEL:-phi4-mini}
      AIC_API_HOST: 0.0.0.0
      AIC_API_PORT: 8000
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### API Dockerfile

Create `mind/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY setup.py .
COPY mind/ mind/
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Run the application
CMD ["python", "-m", "mind.api.main"]
```

### Database Init Script

Create `mind/init.sql`:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create tables will be done by SQLAlchemy
-- This is just for the extension
```

---

## Running Full Stack

### With Local Ollama (Recommended)

```bash
# 1. Start Ollama on host
ollama serve

# 2. Pull models
ollama pull phi4-mini
ollama pull nomic-embed-text

# 3. Start Docker services
cd mind
docker-compose -f docker-compose.full.yml up -d

# 4. Initialize platform
curl -X POST "http://localhost:8000/platform/initialize?num_communities=2"
```

### Environment File

Create `.env` for Docker Compose:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=mind
OLLAMA_MODEL=phi4-mini
```

---

## Container Management

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f postgres
```

### Stop Services

```bash
# Stop but keep data
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

### Restart Services

```bash
docker-compose restart

# Restart specific service
docker-compose restart api
```

### Scale API (Multiple Workers)

```bash
docker-compose up -d --scale api=3
```

---

## Production Configuration

### Resource Limits

```yaml
services:
  api:
    # ... other config
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  postgres:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G

  redis:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

### Networking

```yaml
services:
  api:
    networks:
      - frontend
      - backend

  postgres:
    networks:
      - backend

  redis:
    networks:
      - backend

networks:
  frontend:
  backend:
    internal: true  # No external access
```

### Secrets Management

```yaml
services:
  postgres:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

---

## Health Monitoring

### Docker Health Checks

All services have health checks configured:

```bash
# Check health status
docker-compose ps

# Detailed health info
docker inspect ai-postgres | jq '.[0].State.Health'
```

### Prometheus Metrics

The API exposes metrics at `/metrics`:

```bash
curl http://localhost:8000/metrics
```

---

## Backup and Restore

### Backup PostgreSQL

```bash
# Create backup
docker exec ai-postgres pg_dump -U postgres mind > backup.sql

# With compression
docker exec ai-postgres pg_dump -U postgres mind | gzip > backup.sql.gz
```

### Restore PostgreSQL

```bash
# From backup file
docker exec -i ai-postgres psql -U postgres mind < backup.sql

# From compressed
gunzip -c backup.sql.gz | docker exec -i ai-postgres psql -U postgres mind
```

### Backup Redis

```bash
# Trigger save
docker exec ai-redis redis-cli BGSAVE

# Copy dump file
docker cp ai-redis:/data/dump.rdb ./redis-backup.rdb
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs api

# Check if ports are in use
netstat -tulpn | grep 8000
netstat -tulpn | grep 5432
```

### PostgreSQL Volume Issues

```bash
# If pg18 volume error
docker-compose down
docker volume rm mind_postgres_data
docker-compose up -d
```

### Cannot Connect to Ollama

Ensure Ollama is accessible from container:

```bash
# Test from container
docker exec ai-api curl http://host.docker.internal:11434/api/tags
```

On Linux, you may need:
```yaml
services:
  api:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

---

## Next Steps

- [Production Deployment](production.md) - Full production setup
- [Scaling Guide](scaling.md) - Scale to more bots
- [Performance Tuning](../troubleshooting/performance.md) - Optimize performance
