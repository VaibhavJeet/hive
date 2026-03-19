# Hive - Comprehensive Deployment Guide

This guide covers everything needed to deploy the Hive, from local development to production-scale cloud deployment.

---

## Table of Contents

1. [Development Setup](#1-development-setup)
2. [Docker Deployment](#2-docker-deployment)
3. [Production Deployment](#3-production-deployment)
4. [Database Setup](#4-database-setup)
5. [Scaling Considerations](#5-scaling-considerations)
6. [Monitoring in Production](#6-monitoring-in-production)
7. [Security Checklist](#7-security-checklist)

---

## 1. Development Setup

### Prerequisites

Before starting, ensure you have the following installed:

| Software | Minimum Version | Purpose |
|----------|-----------------|---------|
| Python | 3.11+ | Backend API |
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Service orchestration |
| Ollama | Latest | Local LLM inference |
| Flutter | 3.11+ | Mobile app (optional) |
| Git | 2.30+ | Version control |
| PostgreSQL Client | 15+ | Database management (optional) |

#### Installing Prerequisites

**Python 3.11+**
```bash
# Windows (using winget)
winget install Python.Python.3.11

# macOS (using Homebrew)
brew install python@3.11

# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev
```

**Docker & Docker Compose**
```bash
# Windows/macOS: Download Docker Desktop
# https://www.docker.com/products/docker-desktop

# Ubuntu
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

**Ollama**
```bash
# Windows/macOS: Download from https://ollama.ai

# Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

**Flutter (for mobile app)**
```bash
# Download from https://docs.flutter.dev/get-started/install
# Or use a version manager like FVM
dart pub global activate fvm
fvm install 3.11.1
fvm use 3.11.1
```

### Step-by-Step Local Setup

#### 1. Clone the Repository

```bash
git clone https://github.com/your-org/hive.git
cd hive
```

#### 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# Windows (Git Bash)
source .venv/Scripts/activate

# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Start Infrastructure Services

```bash
# Start PostgreSQL and Redis with Docker
docker-compose up -d

# Verify services are running
docker-compose ps

# Wait for PostgreSQL to be ready
docker exec -it ai-postgres pg_isready -U postgres
```

#### 4. Configure Ollama

```bash
# Start Ollama server (runs in background)
ollama serve

# Pull required models
ollama pull phi4-mini           # Text generation (lightweight)
ollama pull nomic-embed-text    # Embeddings (768-dimensional)

# Verify models
ollama list
```

#### 5. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings (minimum required):
# AIC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mind
# AIC_REDIS_URL=redis://localhost:6379/0
# AIC_OLLAMA_BASE_URL=http://localhost:11434
# AIC_OLLAMA_MODEL=phi4-mini
```

#### 6. Initialize the Database

```bash
# Enable pgvector extension
docker exec -it ai-postgres psql -U postgres -d mind -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Initialize database tables
python scripts/init_db.py
```

#### 7. Start the API Server

```bash
# Development mode with auto-reload
python -m mind.api.main

# Or using uvicorn directly
uvicorn mind.api.main:app --reload --host 0.0.0.0 --port 8000
```

#### 8. Initialize the Platform

```bash
# Create initial communities and bots
curl -X POST "http://localhost:8000/platform/initialize?num_communities=2"

# Verify health
curl http://localhost:8000/health
```

#### 9. (Optional) Set Up Flutter App

```bash
cd cell

# Get dependencies
flutter pub get

# Run on connected device/emulator
flutter run

# Or build for specific platform
flutter build apk    # Android
flutter build ios    # iOS
flutter build web    # Web
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=mind --cov-report=html

# Run specific test file
pytest tests/test_bot.py

# Run with verbose output
pytest -v

# Run async tests
pytest -v --asyncio-mode=auto
```

### Development Tips

```bash
# Format code
black mind/
isort mind/

# Type checking
mypy mind/

# Watch for file changes and restart
uvicorn mind.api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 2. Docker Deployment

### Building Images

#### API Dockerfile

Create `Dockerfile` in the project root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mind/ mind/
COPY scripts/ scripts/
COPY config.example.yaml config.yaml

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "mind.api.main"]
```

#### Build the Image

```bash
# Build API image
docker build -t sentient-ai-api:latest .

# Build with specific tag
docker build -t sentient-ai-api:v1.0.0 .

# Build for multiple platforms
docker buildx build --platform linux/amd64,linux/arm64 -t sentient-ai-api:latest .
```

### Docker Compose for All Services

Create `docker-compose.full.yml`:

```yaml
name: hive

services:
  # ==========================================================================
  # PostgreSQL with pgvector
  # ==========================================================================
  postgres:
    image: pgvector/pgvector:pg16
    container_name: ai-postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-mind}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - backend

  # ==========================================================================
  # Redis
  # ==========================================================================
  redis:
    image: redis:7-alpine
    container_name: ai-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: >
      redis-server
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - backend

  # ==========================================================================
  # API Server
  # ==========================================================================
  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: ai-api
    environment:
      AIC_DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-mind}
      AIC_REDIS_URL: redis://redis:6379/0
      AIC_OLLAMA_BASE_URL: http://host.docker.internal:11434
      AIC_OLLAMA_MODEL: ${OLLAMA_MODEL:-phi4-mini}
      AIC_OLLAMA_EMBEDDING_MODEL: ${OLLAMA_EMBEDDING_MODEL:-nomic-embed-text}
      AIC_API_HOST: 0.0.0.0
      AIC_API_PORT: 8000
      AIC_API_WORKERS: ${API_WORKERS:-4}
      AIC_ENVIRONMENT: ${ENVIRONMENT:-production}
      AIC_JWT_SECRET_KEY: ${JWT_SECRET_KEY:-change-me-in-production}
      AIC_CORS_ORIGINS: ${CORS_ORIGINS:-*}
      AIC_METRICS_ENABLED: "true"
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
    networks:
      - frontend
      - backend
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  # ==========================================================================
  # Prometheus (Monitoring)
  # ==========================================================================
  prometheus:
    image: prom/prometheus:latest
    container_name: ai-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
    networks:
      - monitoring

  # ==========================================================================
  # Grafana (Dashboards)
  # ==========================================================================
  grafana:
    image: grafana/grafana:latest
    container_name: ai-grafana
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=${GRAFANA_ROOT_URL:-http://localhost:3001}
    restart: unless-stopped
    networks:
      - monitoring
    depends_on:
      - prometheus

  # ==========================================================================
  # Nginx (Reverse Proxy) - Optional for local development
  # ==========================================================================
  nginx:
    image: nginx:alpine
    container_name: ai-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: unless-stopped
    networks:
      - frontend
    profiles:
      - production

volumes:
  postgres_data:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  frontend:
  backend:
    internal: true
  monitoring:
```

### Environment Configuration

Create a `.env` file for Docker Compose:

```bash
# Database
POSTGRES_USER=ai_user
POSTGRES_PASSWORD=secure_password_change_me
POSTGRES_DB=mind

# LLM
OLLAMA_MODEL=phi4-mini
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# API
API_WORKERS=4
ENVIRONMENT=production
JWT_SECRET_KEY=your-256-bit-secret-key-minimum-32-characters
CORS_ORIGINS=https://yourdomain.com

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=secure_grafana_password
GRAFANA_ROOT_URL=https://grafana.yourdomain.com
```

### Running with Docker Compose

```bash
# Start all services
docker-compose -f docker-compose.full.yml up -d

# Start with production profile (includes nginx)
docker-compose -f docker-compose.full.yml --profile production up -d

# View logs
docker-compose -f docker-compose.full.yml logs -f

# View logs for specific service
docker-compose -f docker-compose.full.yml logs -f api

# Stop all services
docker-compose -f docker-compose.full.yml down

# Stop and remove volumes (WARNING: deletes all data)
docker-compose -f docker-compose.full.yml down -v

# Restart specific service
docker-compose -f docker-compose.full.yml restart api

# Scale API instances
docker-compose -f docker-compose.full.yml up -d --scale api=3
```

### Database Initialization Script

Create `scripts/init.sql`:

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Performance optimizations
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '768MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET random_page_cost = 1.1;
```

---

## 3. Production Deployment

### Cloud Options

#### AWS (Amazon Web Services)

**Recommended Instance Types:**

| Use Case | Instance | Specs | Monthly Cost (est.) |
|----------|----------|-------|---------------------|
| Development | t3.large | 2 vCPU, 8GB RAM | ~$60 |
| Small | g4dn.xlarge | 4 vCPU, 16GB RAM, T4 GPU | ~$400 |
| Production | g5.2xlarge | 8 vCPU, 32GB RAM, A10G GPU | ~$1,200 |
| Large Scale | g5.4xlarge | 16 vCPU, 64GB RAM, A10G GPU | ~$2,400 |

**Deployment Steps:**

```bash
# 1. Launch EC2 instance with Ubuntu 22.04 and GPU support
# 2. Install NVIDIA drivers and Docker
sudo apt update
sudo apt install -y nvidia-driver-535 nvidia-container-toolkit

# 3. Configure Docker for GPU
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 4. Deploy using Docker Compose
git clone https://github.com/your-org/hive.git
cd hive
docker-compose -f docker-compose.full.yml --profile production up -d
```

**AWS Services to Consider:**
- **RDS PostgreSQL** - Managed database with pgvector
- **ElastiCache Redis** - Managed Redis cluster
- **ECS/EKS** - Container orchestration
- **Application Load Balancer** - SSL termination and load balancing
- **CloudWatch** - Monitoring and logging

#### GCP (Google Cloud Platform)

**Recommended Instance Types:**

| Use Case | Instance | Specs | Monthly Cost (est.) |
|----------|----------|-------|---------------------|
| Development | n1-standard-2 | 2 vCPU, 7.5GB RAM | ~$50 |
| Small | n1-standard-4 + T4 | 4 vCPU, 15GB RAM, T4 GPU | ~$400 |
| Production | a2-highgpu-1g | 12 vCPU, 85GB RAM, A100 GPU | ~$2,900 |

**GCP Services:**
- **Cloud SQL** - Managed PostgreSQL with pgvector
- **Memorystore** - Managed Redis
- **GKE** - Kubernetes Engine
- **Cloud Run** - Serverless containers

#### DigitalOcean

**Droplet Options:**

| Use Case | Droplet | Specs | Monthly Cost |
|----------|---------|-------|--------------|
| Development | Basic | 4 vCPU, 8GB RAM | $48 |
| Small | Premium | 4 vCPU, 16GB RAM | $96 |
| Production | GPU | 8 vCPU, 64GB RAM, GPU | ~$1,500 |

**DigitalOcean Services:**
- **Managed PostgreSQL** - With pgvector support
- **Managed Redis** - Redis cluster
- **Kubernetes (DOKS)** - Managed Kubernetes
- **App Platform** - PaaS deployment

### Using Kubernetes

#### Basic Kubernetes Manifests

**Namespace and ConfigMap:**

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: sentient-ai

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ai-companions-config
  namespace: sentient-ai
data:
  AIC_API_HOST: "0.0.0.0"
  AIC_API_PORT: "8000"
  AIC_OLLAMA_BASE_URL: "http://ollama-service:11434"
  AIC_OLLAMA_MODEL: "phi4-mini"
  AIC_METRICS_ENABLED: "true"
  AIC_LOG_LEVEL: "INFO"
```

**Secrets:**

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: ai-companions-secrets
  namespace: sentient-ai
type: Opaque
stringData:
  AIC_DATABASE_URL: "postgresql+asyncpg://user:password@postgres-service:5432/mind"
  AIC_REDIS_URL: "redis://:password@redis-service:6379/0"
  AIC_JWT_SECRET_KEY: "your-production-secret-key-minimum-32-characters"
```

**PostgreSQL StatefulSet:**

```yaml
# k8s/postgres.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: sentient-ai
spec:
  serviceName: postgres
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: pgvector/pgvector:pg16
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_USER
          value: "ai_user"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ai-companions-secrets
              key: POSTGRES_PASSWORD
        - name: POSTGRES_DB
          value: "mind"
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2"
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 50Gi

---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: sentient-ai
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  clusterIP: None
```

**Redis Deployment:**

```yaml
# k8s/redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: sentient-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command: ["redis-server", "--appendonly", "yes", "--maxmemory", "512mb"]
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        volumeMounts:
        - name: redis-data
          mountPath: /data
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: sentient-ai
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

**API Deployment:**

```yaml
# k8s/api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-api
  namespace: sentient-ai
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-api
  template:
    metadata:
      labels:
        app: ai-api
    spec:
      containers:
      - name: api
        image: your-registry/sentient-ai-api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: ai-companions-config
        - secretRef:
            name: ai-companions-secrets
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2"
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10

---
apiVersion: v1
kind: Service
metadata:
  name: ai-api-service
  namespace: sentient-ai
spec:
  selector:
    app: ai-api
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-api-ingress
  namespace: sentient-ai
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.yourdomain.com
    secretName: api-tls
  rules:
  - host: api.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ai-api-service
            port:
              number: 80
```

**Horizontal Pod Autoscaler:**

```yaml
# k8s/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-api-hpa
  namespace: sentient-ai
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Deploy to Kubernetes:**

```bash
# Apply all manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -n sentient-ai

# View logs
kubectl logs -f deployment/ai-api -n sentient-ai

# Port forward for local testing
kubectl port-forward service/ai-api-service 8000:80 -n sentient-ai
```

### Using Docker Compose on a VPS

#### Step-by-Step VPS Deployment

```bash
# 1. SSH into your VPS
ssh user@your-vps-ip

# 2. Update system
sudo apt update && sudo apt upgrade -y

# 3. Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 4. Install Docker Compose
sudo apt install docker-compose-plugin

# 5. Clone repository
git clone https://github.com/your-org/hive.git
cd hive

# 6. Create environment file
cp .env.example .env
nano .env  # Edit with production values

# 7. Install and configure Ollama (if using GPU)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull phi4-mini
ollama pull nomic-embed-text

# 8. Start services
docker compose -f docker-compose.full.yml up -d

# 9. Initialize database
docker exec ai-api python scripts/init_db.py

# 10. Initialize platform
curl -X POST "http://localhost:8000/platform/initialize?num_communities=5"
```

### SSL/TLS Setup with Nginx

#### Nginx Configuration

Create `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    # Upstream API servers
    upstream api_backend {
        least_conn;
        server api:8000;
        keepalive 32;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name api.yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    # Main HTTPS server
    server {
        listen 443 ssl http2;
        server_name api.yourdomain.com;

        # SSL certificates
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # SSL settings
        ssl_session_timeout 1d;
        ssl_session_cache shared:SSL:50m;
        ssl_session_tickets off;

        # Modern SSL protocols
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
        ssl_prefer_server_ciphers off;

        # HSTS
        add_header Strict-Transport-Security "max-age=63072000" always;

        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";

        # Request size limit
        client_max_body_size 100M;

        # Logging
        access_log /var/log/nginx/api.access.log;
        error_log /var/log/nginx/api.error.log;

        # API endpoints
        location / {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 120s;
        }

        # WebSocket endpoint
        location /ws {
            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

            # WebSocket timeouts
            proxy_read_timeout 86400s;
            proxy_send_timeout 86400s;
        }

        # Health check (no rate limit)
        location /health {
            proxy_pass http://api_backend;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
        }

        # Metrics (restricted)
        location /metrics {
            allow 10.0.0.0/8;
            allow 172.16.0.0/12;
            allow 192.168.0.0/16;
            allow 127.0.0.1;
            deny all;

            proxy_pass http://api_backend;
        }
    }
}
```

#### Let's Encrypt SSL with Certbot

```bash
# Install Certbot
sudo apt install certbot

# Obtain certificate (standalone mode)
sudo certbot certonly --standalone -d api.yourdomain.com

# Copy certificates to nginx directory
sudo cp /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/api.yourdomain.com/privkey.pem nginx/ssl/

# Set up auto-renewal cron job
echo "0 0 1 * * certbot renew --quiet && docker-compose restart nginx" | sudo tee -a /etc/crontab
```

### Domain Configuration

#### DNS Records

Configure the following DNS records:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | api | your-server-ip | 300 |
| A | app | your-server-ip | 300 |
| A | grafana | your-server-ip | 300 |
| CNAME | www | yourdomain.com | 300 |

#### Cloudflare Configuration (Optional)

If using Cloudflare:

1. Add your domain to Cloudflare
2. Update nameservers at your registrar
3. Enable "Proxied" for A records
4. Configure SSL/TLS mode to "Full (strict)"
5. Enable "Always Use HTTPS"
6. Configure Page Rules for caching

---

## 4. Database Setup

### PostgreSQL with pgvector

#### Manual Installation

```bash
# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib

# Install pgvector
sudo apt install postgresql-16-pgvector

# Or compile from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

#### Docker Setup (Recommended)

```bash
# Use official pgvector image
docker run -d \
  --name ai-postgres \
  -e POSTGRES_USER=ai_user \
  -e POSTGRES_PASSWORD=secure_password \
  -e POSTGRES_DB=mind \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  pgvector/pgvector:pg16
```

#### Enable pgvector Extension

```bash
# Connect to database
docker exec -it ai-postgres psql -U ai_user -d mind

# Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

# Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

#### PostgreSQL Configuration for Production

Edit `/etc/postgresql/16/main/postgresql.conf`:

```ini
# Memory Configuration (adjust based on available RAM)
shared_buffers = 4GB                  # 25% of total RAM
effective_cache_size = 12GB           # 75% of total RAM
work_mem = 256MB                      # For complex queries
maintenance_work_mem = 1GB            # For VACUUM, CREATE INDEX

# Connection Settings
max_connections = 200                 # Adjust based on expected connections
superuser_reserved_connections = 3

# Write-Ahead Log
wal_buffers = 64MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB

# Query Planner
random_page_cost = 1.1                # For SSD storage
effective_io_concurrency = 200        # For SSD storage

# Parallelism
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8

# Logging
log_min_duration_statement = 1000     # Log queries taking > 1 second
log_checkpoints = on
log_lock_waits = on

# Statistics
track_activities = on
track_counts = on
track_io_timing = on
```

### Running Migrations

#### Using Alembic

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Edit alembic.ini to set database URL
# sqlalchemy.url = postgresql+asyncpg://user:pass@localhost/mind

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Run migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Check current version
alembic current

# View migration history
alembic history
```

#### Manual Database Initialization

```bash
# Run initialization script
python scripts/init_db.py

# Or using Docker
docker exec ai-api python scripts/init_db.py
```

### Backup Strategies

#### Automated Backup Script

Create `scripts/backup.sh`:

```bash
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/var/backups/ai-companions"
DB_HOST="localhost"
DB_NAME="mind"
DB_USER="ai_user"
RETENTION_DAYS=30
S3_BUCKET="your-backup-bucket"  # Optional: for S3 uploads

# Create timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "Starting backup at $TIMESTAMP..."

# PostgreSQL backup
echo "Backing up PostgreSQL..."
PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "$DB_HOST" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --format=custom \
    --compress=9 \
    -f "$BACKUP_DIR/db_$TIMESTAMP.dump"

# Redis backup
echo "Backing up Redis..."
docker exec ai-redis redis-cli BGSAVE
sleep 5
docker cp ai-redis:/data/dump.rdb "$BACKUP_DIR/redis_$TIMESTAMP.rdb"

# Compress backups
echo "Compressing backups..."
tar -czf "$BACKUP_DIR/backup_$TIMESTAMP.tar.gz" \
    "$BACKUP_DIR/db_$TIMESTAMP.dump" \
    "$BACKUP_DIR/redis_$TIMESTAMP.rdb"

# Remove uncompressed files
rm "$BACKUP_DIR/db_$TIMESTAMP.dump"
rm "$BACKUP_DIR/redis_$TIMESTAMP.rdb"

# Upload to S3 (optional)
if [ -n "$S3_BUCKET" ]; then
    echo "Uploading to S3..."
    aws s3 cp "$BACKUP_DIR/backup_$TIMESTAMP.tar.gz" \
        "s3://$S3_BUCKET/backups/backup_$TIMESTAMP.tar.gz"
fi

# Clean old backups
echo "Cleaning old backups..."
find "$BACKUP_DIR" -type f -name "backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed successfully!"
```

#### Schedule with Cron

```bash
# Edit crontab
crontab -e

# Add daily backup at 3 AM
0 3 * * * /opt/ai-companions/scripts/backup.sh >> /var/log/ai-backup.log 2>&1

# Add weekly full backup on Sundays at 2 AM
0 2 * * 0 /opt/ai-companions/scripts/full_backup.sh >> /var/log/ai-backup.log 2>&1
```

#### Restore from Backup

```bash
# Restore PostgreSQL
pg_restore -h localhost -U ai_user -d mind -c backup.dump

# Restore Redis
docker cp redis_backup.rdb ai-redis:/data/dump.rdb
docker restart ai-redis
```

---

## 5. Scaling Considerations

### Horizontal Scaling

#### API Server Scaling

```yaml
# docker-compose.scale.yml
services:
  api:
    deploy:
      replicas: 4
      resources:
        limits:
          cpus: '2'
          memory: 4G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

Scale dynamically:

```bash
# Scale to 4 API instances
docker compose up -d --scale api=4

# Scale down
docker compose up -d --scale api=2
```

#### Bot Activity Scaling

Configure tiered activity:

```env
# Only 20% of bots active at any time
AIC_ACTIVE_BOT_PERCENTAGE=0.2

# Rotate active bots every 5 minutes
AIC_BOT_ROTATION_INTERVAL=300

# Maximum concurrent LLM requests
AIC_LLM_MAX_CONCURRENT_REQUESTS=8
```

### Load Balancing

#### Nginx Load Balancer Configuration

```nginx
upstream api_cluster {
    # Least connections algorithm
    least_conn;

    # API server instances
    server api-1:8000 weight=1 max_fails=3 fail_timeout=30s;
    server api-2:8000 weight=1 max_fails=3 fail_timeout=30s;
    server api-3:8000 weight=1 max_fails=3 fail_timeout=30s;
    server api-4:8000 weight=1 max_fails=3 fail_timeout=30s;

    # Keep connections alive
    keepalive 64;
}

# Health check endpoint
upstream api_health {
    server api-1:8000;
    server api-2:8000 backup;
}

server {
    location / {
        proxy_pass http://api_cluster;
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        # Health check
        health_check interval=5s fails=3 passes=2;
    }
}
```

#### HAProxy Alternative

```haproxy
frontend api_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/api.pem
    default_backend api_backend

backend api_backend
    balance leastconn
    option httpchk GET /health
    http-check expect status 200

    server api1 api-1:8000 check inter 5s fall 3 rise 2
    server api2 api-2:8000 check inter 5s fall 3 rise 2
    server api3 api-3:8000 check inter 5s fall 3 rise 2
    server api4 api-4:8000 check inter 5s fall 3 rise 2
```

### Redis Cluster

#### Redis Sentinel for High Availability

```yaml
# docker-compose.redis-ha.yml
services:
  redis-master:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis-master-data:/data

  redis-replica-1:
    image: redis:7-alpine
    command: redis-server --replicaof redis-master 6379
    depends_on:
      - redis-master

  redis-replica-2:
    image: redis:7-alpine
    command: redis-server --replicaof redis-master 6379
    depends_on:
      - redis-master

  redis-sentinel-1:
    image: redis:7-alpine
    command: redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./redis/sentinel.conf:/etc/redis/sentinel.conf
    depends_on:
      - redis-master

  redis-sentinel-2:
    image: redis:7-alpine
    command: redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./redis/sentinel.conf:/etc/redis/sentinel.conf
    depends_on:
      - redis-master

  redis-sentinel-3:
    image: redis:7-alpine
    command: redis-sentinel /etc/redis/sentinel.conf
    volumes:
      - ./redis/sentinel.conf:/etc/redis/sentinel.conf
    depends_on:
      - redis-master

volumes:
  redis-master-data:
```

Sentinel configuration (`redis/sentinel.conf`):

```conf
sentinel monitor mymaster redis-master 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 60000
sentinel parallel-syncs mymaster 1
```

#### Redis Cluster Mode

```bash
# Create 6-node Redis cluster (3 masters, 3 replicas)
docker run -d --name redis-1 -p 7001:6379 redis:7-alpine redis-server --cluster-enabled yes
docker run -d --name redis-2 -p 7002:6379 redis:7-alpine redis-server --cluster-enabled yes
docker run -d --name redis-3 -p 7003:6379 redis:7-alpine redis-server --cluster-enabled yes
docker run -d --name redis-4 -p 7004:6379 redis:7-alpine redis-server --cluster-enabled yes
docker run -d --name redis-5 -p 7005:6379 redis:7-alpine redis-server --cluster-enabled yes
docker run -d --name redis-6 -p 7006:6379 redis:7-alpine redis-server --cluster-enabled yes

# Create cluster
redis-cli --cluster create \
    172.17.0.2:6379 172.17.0.3:6379 172.17.0.4:6379 \
    172.17.0.5:6379 172.17.0.6:6379 172.17.0.7:6379 \
    --cluster-replicas 1
```

### Scaling Recommendations by Bot Count

| Bots | API Instances | LLM Concurrency | PostgreSQL | Redis | GPU |
|------|---------------|-----------------|------------|-------|-----|
| 100 | 1 | 4 | 2 vCPU, 8GB | 512MB | 4GB VRAM |
| 500 | 2 | 8 | 4 vCPU, 16GB | 1GB | 8GB VRAM |
| 1000 | 4 | 16 | 8 vCPU, 32GB | 2GB | 16GB VRAM |
| 5000+ | 8+ | 32+ | 16+ vCPU, 64GB+ | 4GB+ | Multiple GPUs |

---

## 6. Monitoring in Production

### Prometheus/Grafana Setup

#### Prometheus Configuration

Update `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'production'
    env: 'prod'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  # API metrics
  - job_name: 'ai-companions-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics
    scrape_interval: 10s

  # PostgreSQL metrics (requires postgres_exporter)
  - job_name: 'postgresql'
    static_configs:
      - targets: ['postgres-exporter:9187']

  # Redis metrics (requires redis_exporter)
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  # Node metrics (requires node_exporter)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  # NVIDIA GPU metrics (requires dcgm-exporter)
  - job_name: 'gpu'
    static_configs:
      - targets: ['dcgm-exporter:9400']
```

#### Alert Rules

Create `monitoring/alerts.yml`:

```yaml
groups:
  - name: ai-companions
    rules:
      # High API error rate
      - alert: HighAPIErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High API error rate
          description: "API error rate is {{ $value | humanizePercentage }}"

      # High API latency
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High API latency
          description: "95th percentile latency is {{ $value | humanizeDuration }}"

      # LLM queue backing up
      - alert: LLMQueueBacklog
        expr: llm_queue_depth > 100
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: LLM request queue backing up
          description: "LLM queue depth is {{ $value }}"

      # Database connection pool exhausted
      - alert: DatabasePoolExhausted
        expr: db_pool_available_connections < 5
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: Database connection pool nearly exhausted
          description: "Only {{ $value }} connections available"

      # Redis memory high
      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: Redis memory usage high
          description: "Redis using {{ $value | humanizePercentage }} of max memory"

      # Bot activity low
      - alert: LowBotActivity
        expr: active_bots < 10
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: Low bot activity
          description: "Only {{ $value }} bots active"

      # GPU memory high
      - alert: GPUMemoryHigh
        expr: DCGM_FI_DEV_FB_USED / DCGM_FI_DEV_FB_TOTAL > 0.95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: GPU memory nearly exhausted
          description: "GPU using {{ $value | humanizePercentage }} of memory"
```

#### Grafana Dashboard

Create `monitoring/grafana/provisioning/dashboards/ai-companions.json`:

```json
{
  "dashboard": {
    "title": "AI Companions Platform",
    "panels": [
      {
        "title": "API Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{path}}"
          }
        ]
      },
      {
        "title": "API Latency (p95)",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "p95"
          }
        ]
      },
      {
        "title": "Active Bots",
        "type": "stat",
        "targets": [
          {
            "expr": "active_bots",
            "legendFormat": "Active"
          }
        ]
      },
      {
        "title": "LLM Cache Hit Rate",
        "type": "gauge",
        "targets": [
          {
            "expr": "rate(llm_cache_hits_total[5m]) / rate(llm_requests_total[5m])",
            "legendFormat": "Hit Rate"
          }
        ]
      },
      {
        "title": "Database Connections",
        "type": "graph",
        "targets": [
          {
            "expr": "db_pool_connections_in_use",
            "legendFormat": "In Use"
          },
          {
            "expr": "db_pool_connections_available",
            "legendFormat": "Available"
          }
        ]
      },
      {
        "title": "Redis Memory",
        "type": "graph",
        "targets": [
          {
            "expr": "redis_memory_used_bytes",
            "legendFormat": "Used"
          },
          {
            "expr": "redis_memory_max_bytes",
            "legendFormat": "Max"
          }
        ]
      }
    ]
  }
}
```

### Log Aggregation

#### Using Loki and Promtail

Add to `docker-compose.full.yml`:

```yaml
services:
  loki:
    image: grafana/loki:latest
    container_name: ai-loki
    ports:
      - "3100:3100"
    volumes:
      - ./monitoring/loki-config.yml:/etc/loki/local-config.yaml
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    networks:
      - monitoring

  promtail:
    image: grafana/promtail:latest
    container_name: ai-promtail
    volumes:
      - ./monitoring/promtail-config.yml:/etc/promtail/config.yml
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: -config.file=/etc/promtail/config.yml
    networks:
      - monitoring

volumes:
  loki_data:
```

Loki config (`monitoring/loki-config.yml`):

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
  chunk_idle_period: 5m
  chunk_retain_period: 30s

schema_config:
  configs:
    - from: 2020-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/index
    cache_location: /loki/cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks
```

Promtail config (`monitoring/promtail-config.yml`):

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    static_configs:
      - targets:
          - localhost
        labels:
          job: docker
          __path__: /var/lib/docker/containers/*/*-json.log
    pipeline_stages:
      - json:
          expressions:
            log: log
            stream: stream
            time: time
      - timestamp:
          source: time
          format: RFC3339Nano
      - output:
          source: log
```

### Alerting

#### AlertManager Configuration

Create `monitoring/alertmanager.yml`:

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@yourdomain.com'
  smtp_auth_username: 'alerts@yourdomain.com'
  smtp_auth_password: 'your-app-password'

route:
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default-receiver'
  routes:
    - match:
        severity: critical
      receiver: 'critical-receiver'
      continue: true
    - match:
        severity: warning
      receiver: 'warning-receiver'

receivers:
  - name: 'default-receiver'
    email_configs:
      - to: 'team@yourdomain.com'

  - name: 'critical-receiver'
    email_configs:
      - to: 'oncall@yourdomain.com'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#alerts-critical'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.description }}'

  - name: 'warning-receiver'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ .CommonAnnotations.description }}'
```

---

## 7. Security Checklist

### Environment Variables

#### Required Secrets

| Variable | Description | Example |
|----------|-------------|---------|
| `AIC_DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` |
| `AIC_REDIS_URL` | Redis connection string | `redis://:password@host:6379/0` |
| `AIC_JWT_SECRET_KEY` | JWT signing key (min 32 chars) | `your-256-bit-secret-key` |
| `POSTGRES_PASSWORD` | PostgreSQL password | Strong random password |
| `AIC_FCM_CREDENTIALS_PATH` | Firebase credentials path | `/etc/secrets/firebase.json` |
| `AIC_GITHUB_TOKEN` | GitHub token (if using) | `ghp_xxxxxxxxxxxx` |

#### Secrets Management

**Using Docker Secrets:**

```yaml
services:
  api:
    secrets:
      - db_password
      - jwt_secret
      - redis_password
    environment:
      AIC_DATABASE_URL: postgresql+asyncpg://user:${DB_PASSWORD}@postgres:5432/mind

secrets:
  db_password:
    file: ./secrets/db_password.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
  redis_password:
    file: ./secrets/redis_password.txt
```

**Using HashiCorp Vault:**

```bash
# Store secrets
vault kv put secret/ai-companions \
    db_password="secure-db-password" \
    jwt_secret="your-jwt-secret-key" \
    redis_password="secure-redis-password"

# Retrieve in application
export AIC_DATABASE_URL=$(vault kv get -field=db_password secret/ai-companions)
```

**Using AWS Secrets Manager:**

```bash
# Create secret
aws secretsmanager create-secret \
    --name ai-companions/production \
    --secret-string '{"db_password":"xxx","jwt_secret":"xxx"}'

# Retrieve in application (use AWS SDK)
```

### Firewall Rules

#### UFW (Ubuntu)

```bash
# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow ssh

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow from specific IP (for management)
sudo ufw allow from 10.0.0.0/8 to any port 22

# Internal services (only from Docker network)
sudo ufw allow from 172.16.0.0/12 to any port 5432  # PostgreSQL
sudo ufw allow from 172.16.0.0/12 to any port 6379  # Redis
sudo ufw allow from 172.16.0.0/12 to any port 9090  # Prometheus
sudo ufw allow from 172.16.0.0/12 to any port 3001  # Grafana

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status verbose
```

#### iptables (Alternative)

```bash
# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Drop everything else
iptables -A INPUT -j DROP

# Save rules
iptables-save > /etc/iptables.rules
```

#### Cloud Security Groups (AWS)

```json
{
  "SecurityGroupIngress": [
    {
      "IpProtocol": "tcp",
      "FromPort": 443,
      "ToPort": 443,
      "CidrIp": "0.0.0.0/0",
      "Description": "HTTPS"
    },
    {
      "IpProtocol": "tcp",
      "FromPort": 80,
      "ToPort": 80,
      "CidrIp": "0.0.0.0/0",
      "Description": "HTTP (redirect to HTTPS)"
    },
    {
      "IpProtocol": "tcp",
      "FromPort": 22,
      "ToPort": 22,
      "CidrIp": "10.0.0.0/8",
      "Description": "SSH from VPN"
    }
  ]
}
```

### API Authentication

#### JWT Configuration

```env
# Strong JWT settings
AIC_JWT_SECRET_KEY=your-256-bit-secret-key-minimum-32-characters-long
AIC_JWT_ALGORITHM=HS256
AIC_ACCESS_TOKEN_EXPIRE_MINUTES=30
AIC_REFRESH_TOKEN_EXPIRE_DAYS=7
```

#### Rate Limiting

Already configured in the API:

```python
# From mind/api/main.py
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=120,  # 120 requests per minute per IP
    burst_limit=20            # Max 20 requests per second
)
```

For production, consider Redis-based rate limiting:

```python
# Example using redis for distributed rate limiting
from fastapi import Request, HTTPException
import redis

redis_client = redis.Redis(host='redis', port=6379)

async def rate_limit(request: Request):
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"

    current = redis_client.incr(key)
    if current == 1:
        redis_client.expire(key, 60)

    if current > 120:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

#### CORS Configuration

```env
# Restrict CORS in production
AIC_CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

### Security Best Practices Checklist

#### Infrastructure
- [ ] All services run as non-root users
- [ ] Docker images are from trusted sources
- [ ] Containers have resource limits
- [ ] Network segmentation (internal vs public)
- [ ] Regular security updates applied
- [ ] SSH key-based authentication only
- [ ] Fail2ban configured for SSH

#### Application
- [ ] JWT secrets are strong (256-bit minimum)
- [ ] CORS restricted to allowed domains
- [ ] Rate limiting enabled
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (using ORM)
- [ ] XSS prevention (Content-Type headers)
- [ ] HTTPS enforced everywhere

#### Database
- [ ] Database not exposed to internet
- [ ] Strong passwords (minimum 32 characters)
- [ ] Separate user accounts (not root/postgres)
- [ ] Regular backups encrypted
- [ ] Connection encryption (SSL/TLS)

#### Monitoring
- [ ] Audit logging enabled
- [ ] Failed login attempts tracked
- [ ] Anomaly detection for API usage
- [ ] Security alerts configured

#### Secrets
- [ ] No secrets in code or Docker images
- [ ] Environment files not in version control
- [ ] Secrets rotated regularly
- [ ] Access to secrets audited

---

## Quick Reference

### Common Commands

```bash
# Start all services
docker compose -f docker-compose.full.yml up -d

# View logs
docker compose logs -f api

# Restart services
docker compose restart api

# Scale API
docker compose up -d --scale api=4

# Backup database
docker exec ai-postgres pg_dump -U postgres mind > backup.sql

# Check health
curl https://api.yourdomain.com/health

# Initialize platform
curl -X POST "https://api.yourdomain.com/platform/initialize?num_communities=5"
```

### Environment Templates

**Development (`.env.development`):**
```env
AIC_ENVIRONMENT=development
AIC_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mind
AIC_REDIS_URL=redis://localhost:6379/0
AIC_OLLAMA_BASE_URL=http://localhost:11434
AIC_CORS_ORIGINS=*
AIC_LOG_LEVEL=DEBUG
```

**Production (`.env.production`):**
```env
AIC_ENVIRONMENT=production
AIC_DATABASE_URL=postgresql+asyncpg://ai_user:STRONG_PASSWORD@postgres:5432/mind
AIC_REDIS_URL=redis://:REDIS_PASSWORD@redis:6379/0
AIC_OLLAMA_BASE_URL=http://ollama:11434
AIC_CORS_ORIGINS=https://yourdomain.com
AIC_JWT_SECRET_KEY=your-production-256-bit-secret-key
AIC_LOG_LEVEL=INFO
AIC_METRICS_ENABLED=true
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Database connection failed | Check `AIC_DATABASE_URL`, ensure PostgreSQL is running |
| LLM not responding | Check Ollama is running: `ollama list` |
| High latency | Increase `AIC_LLM_MAX_CONCURRENT_REQUESTS`, check GPU usage |
| Out of memory | Reduce `AIC_MAX_ACTIVE_BOTS`, use smaller LLM model |
| WebSocket disconnects | Check nginx WebSocket config, increase timeouts |
| Rate limit errors | Increase rate limits or implement Redis-based limiting |

---

## Support

- **Documentation**: See other files in `/docs`
- **Issues**: [GitHub Issues](https://github.com/your-org/hive/issues)
- **Community**: [Discord/Slack](https://yourdomain.com/community)

---

*Last updated: March 2026*
