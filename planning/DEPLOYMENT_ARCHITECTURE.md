# Deployment Architecture

## Overview
QA Manager deployment architecture is designed for reliability, scalability, and maintainability in a Linux production environment. The architecture supports both containerized and traditional deployment models, with emphasis on high availability and monitoring.

## Deployment Models

### Model 1: Docker Compose (Small/Development)
**Use Case**: Development, small teams, proof-of-concept

**Components:**
- Single host deployment
- Docker Compose orchestration
- PostgreSQL container
- Redis container
- QA Manager API container
- NiceGUI UI (embedded in API)
- Nginx reverse proxy

**Architecture Diagram:**
```
                    [Internet]
                        |
                   [Nginx:443]
                        |
         +--------------+---------------+
         |              |               |
    [QA Manager    [PostgreSQL]    [Redis]
      API+UI]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    container_name: qamgr-postgres
    environment:
      POSTGRES_DB: qamgr
      POSTGRES_USER: qamgr
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U qamgr"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: qamgr-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: qamgr-api
    environment:
      DATABASE_URL: postgresql://qamgr:${DB_PASSWORD}@postgres:5432/qamgr
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      ENVIRONMENT: production
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
      - ./uploads:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: qamgr-celery
    command: celery -A tasks.celery worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://qamgr:${DB_PASSWORD}@postgres:5432/qamgr
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

  celery-beat:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: qamgr-celery-beat
    command: celery -A tasks.celery beat --loglevel=info
    environment:
      DATABASE_URL: postgresql://qamgr:${DB_PASSWORD}@postgres:5432/qamgr
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: qamgr-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

**Pros:**
- Simple setup
- Easy to manage
- Low resource overhead
- Good for testing

**Cons:**
- Single point of failure
- Limited scalability
- Manual updates
- No auto-scaling

### Model 2: Kubernetes (Production/Enterprise)
**Use Case**: Production, high availability, auto-scaling

**Architecture Diagram:**
```
                        [Load Balancer]
                              |
                    [Ingress Controller]
                              |
        +---------------------+----------------------+
        |                     |                      |
   [API Pods]          [Celery Workers]      [Celery Beat]
    (3 replicas)        (5 replicas)          (1 replica)
        |                     |                      |
        +---------------------+----------------------+
                              |
                 +------------+-------------+
                 |            |             |
           [PostgreSQL]   [Redis]    [Prometheus]
            (StatefulSet) (StatefulSet)  (Monitoring)
```

**Namespace Structure:**
```
qa-manager/
├── api-deployment
├── celery-worker-deployment
├── celery-beat-deployment
├── postgres-statefulset
├── redis-statefulset
├── ingress
├── configmaps
├── secrets
└── services
```

**Key Kubernetes Resources:**

**Deployment (API):**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qamgr-api
  namespace: qa-manager
spec:
  replicas: 3
  selector:
    matchLabels:
      app: qamgr-api
  template:
    metadata:
      labels:
        app: qamgr-api
    spec:
      containers:
      - name: api
        image: company/qamgr-api:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: qamgr-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: qamgr-secrets
              key: redis-url
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: qamgr-secrets
              key: secret-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

**StatefulSet (PostgreSQL):**
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
  namespace: qa-manager
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
        image: postgres:16
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_DB
          value: qamgr
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: username
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 100Gi
```

**Ingress:**
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: qamgr-ingress
  namespace: qa-manager
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - qa-mgr.company.com
    secretName: qamgr-tls
  rules:
  - host: qa-mgr.company.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: qamgr-api
            port:
              number: 8000
```

**Horizontal Pod Autoscaler:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: qamgr-api-hpa
  namespace: qa-manager
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: qamgr-api
  minReplicas: 3
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

**Pros:**
- High availability
- Auto-scaling
- Self-healing
- Rolling updates
- Resource management

**Cons:**
- Complex setup
- Requires K8s expertise
- Higher resource overhead
- More expensive

## Container Images

### Dockerfile (Multi-stage Build)

```dockerfile
# Stage 1: Base
FROM python:3.12-slim as base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Stage 2: Builder
FROM base as builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --user --no-warn-script-location \
    -r <(python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))")

# Stage 3: Runtime
FROM base as runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 qamgr && chown -R qamgr:qamgr /app
USER qamgr

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run migrations on startup, then start server
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
```

### Image Management

**Tagging Strategy:**
```bash
company/qamgr-api:v1.2.3        # Semantic version
company/qamgr-api:v1.2.3-abc123 # Version + commit hash
company/qamgr-api:latest        # Latest stable
company/qamgr-api:dev           # Development branch
```

**Registry:**
- Private registry (Harbor, AWS ECR, Azure ACR, GCP Artifact Registry)
- Vulnerability scanning enabled
- Image signing for security

## Infrastructure

### Server Specifications

**Minimum (Docker Compose):**
- 4 CPU cores
- 16 GB RAM
- 200 GB SSD storage
- Linux (Ubuntu 22.04 LTS or RHEL 8+)

**Recommended (Production):**
- 8 CPU cores
- 32 GB RAM
- 500 GB SSD storage
- Linux (Ubuntu 22.04 LTS)

**Kubernetes Cluster (Production):**
- 3 control plane nodes: 4 CPU, 8 GB RAM each
- 5+ worker nodes: 8 CPU, 32 GB RAM each
- Load balancer (external)
- Shared storage (NFS, Ceph, or cloud provider)

### Networking

**Ports:**
```
80/tcp   - HTTP (redirect to HTTPS)
443/tcp  - HTTPS (public access)
5432/tcp - PostgreSQL (internal only)
6379/tcp - Redis (internal only)
9090/tcp - Prometheus (internal/VPN)
3000/tcp - Grafana (internal/VPN)
```

**Firewall Rules:**
```bash
# Allow HTTPS from anywhere
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Allow Jenkins to access API
iptables -A INPUT -p tcp --dport 443 -s <jenkins-ip> -j ACCEPT

# Block PostgreSQL from external
iptables -A INPUT -p tcp --dport 5432 -j DROP

# Block Redis from external
iptables -A INPUT -p tcp --dport 6379 -j DROP
```

**DNS:**
```
qa-mgr.company.com           -> Load Balancer/Ingress
api.qa-mgr.company.com       -> API (if separate)
grafana.qa-mgr.company.com   -> Monitoring dashboards
```

## Database Management

### PostgreSQL Setup

**Configuration (postgresql.conf):**
```ini
# Memory
shared_buffers = 8GB
effective_cache_size = 24GB
work_mem = 64MB
maintenance_work_mem = 1GB

# WAL
wal_level = replica
max_wal_size = 4GB
checkpoint_completion_target = 0.9

# Replication
max_replication_slots = 5
max_wal_senders = 5

# Performance
random_page_cost = 1.1  # For SSD
effective_io_concurrency = 200

# Logging
log_min_duration_statement = 1000  # Log slow queries (>1s)
log_line_prefix = '%t [%p]: user=%u,db=%d,app=%a,client=%h '
```

### Backup Strategy

**Automated Backups:**
```bash
#!/bin/bash
# Backup script (run daily via cron)

BACKUP_DIR="/backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Full backup
pg_dump -h postgres -U qamgr -F c -f "${BACKUP_DIR}/qamgr_${DATE}.dump" qamgr

# Compress
gzip "${BACKUP_DIR}/qamgr_${DATE}.dump"

# Upload to S3/Object Storage
aws s3 cp "${BACKUP_DIR}/qamgr_${DATE}.dump.gz" s3://qamgr-backups/daily/

# Clean old backups
find ${BACKUP_DIR} -name "*.dump.gz" -mtime +${RETENTION_DAYS} -delete

# Verify backup integrity
pg_restore --list "${BACKUP_DIR}/qamgr_${DATE}.dump.gz" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "Backup successful: qamgr_${DATE}.dump.gz"
else
    echo "Backup verification failed!" | mail -s "ALERT: Backup Failed" ops@company.com
fi
```

**Backup Schedule:**
- Full backup: Daily at 2 AM
- Incremental (WAL archiving): Continuous
- Retention: 30 days local, 90 days in object storage
- Test restore: Weekly

### High Availability

**PostgreSQL Replication:**
```
  [Primary]
      |
      ├── [Standby 1] (sync)
      └── [Standby 2] (async)
```

**Patroni + etcd (for automatic failover):**
```yaml
# patroni.yml
scope: qamgr-postgres
name: postgres-1

restapi:
  listen: 0.0.0.0:8008
  connect_address: postgres-1:8008

etcd:
  hosts: etcd-1:2379,etcd-2:2379,etcd-3:2379

bootstrap:
  dcs:
    ttl: 30
    loop_wait: 10
    retry_timeout: 10
    maximum_lag_on_failover: 1048576
    postgresql:
      use_pg_rewind: true

postgresql:
  listen: 0.0.0.0:5432
  connect_address: postgres-1:5432
  data_dir: /var/lib/postgresql/data
  pgpass: /tmp/pgpass
  authentication:
    replication:
      username: replicator
      password: ${REPLICATION_PASSWORD}
    superuser:
      username: postgres
      password: ${POSTGRES_PASSWORD}
  parameters:
    max_connections: 200
    shared_buffers: 8GB
```

## Redis Management

### Redis Configuration

**redis.conf:**
```conf
# Memory
maxmemory 4gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# Security
requirepass ${REDIS_PASSWORD}
bind 0.0.0.0
protected-mode yes

# Performance
tcp-backlog 511
timeout 0
tcp-keepalive 300
```

### Redis Sentinel (HA)

```
  [Redis Master]
       |
       ├── [Redis Replica 1]
       └── [Redis Replica 2]
       
  [Sentinel 1] [Sentinel 2] [Sentinel 3]
```

## Monitoring & Observability

### Prometheus Monitoring

**Metrics to Collect:**
- API request rate, latency, errors
- Database connection pool stats
- Redis memory usage
- Celery queue depth
- Test run processing time
- Active user count
- Resource utilization (CPU, memory, disk)

**Prometheus Configuration:**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'qamgr-api'
    static_configs:
      - targets: ['api:8000']
    
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
  
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
  
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
```

### Grafana Dashboards

**Key Dashboards:**
1. **System Overview**
   - Request rate
   - Error rate
   - Response time (p50, p95, p99)
   - Active users

2. **Database Performance**
   - Query latency
   - Connection pool utilization
   - Slow queries
   - Cache hit rate

3. **Test Execution**
   - Test runs per hour
   - Average test duration
   - Failure rate
   - Queue depth

4. **Infrastructure**
   - CPU/Memory/Disk usage
   - Network I/O
   - Container health

### Logging

**Centralized Logging with Loki:**
```yaml
# promtail-config.yml
server:
  http_listen_port: 9080

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: qamgr-api
    static_configs:
      - targets:
          - localhost
        labels:
          job: qamgr-api
          __path__: /app/logs/*.log
```

**Log Levels:**
- DEBUG: Development only
- INFO: General events (startup, shutdown)
- WARNING: Unexpected but handled (rate limits)
- ERROR: Errors that need attention
- CRITICAL: System-threatening issues

## Scaling Strategy

### Horizontal Scaling

**API Pods:**
- Auto-scale based on CPU/memory
- Min: 3 replicas
- Max: 10 replicas
- Target: 70% CPU utilization

**Celery Workers:**
- Scale based on queue depth
- Min: 5 workers
- Max: 20 workers
- Target: <100 pending tasks per worker

### Vertical Scaling

**When to scale vertically:**
- Database reaching memory limits
- Redis cache too small
- Persistent performance issues

**Scaling approach:**
- Add memory first (cheapest)
- Then CPU
- Finally, consider horizontal scaling

### Database Scaling

**Read Replicas:**
- Direct read-only queries to replicas
- Use connection pooling (pgBouncer)
- Implement query caching

**Partitioning:**
- Partition large tables by tenant_id
- Partition by date for time-series data
- Use table inheritance for old data

## Disaster Recovery

### Backup & Restore

**Recovery Time Objective (RTO):** 4 hours
**Recovery Point Objective (RPO):** 1 hour

**Backup Locations:**
- Primary: Local disk
- Secondary: Object storage (S3/MinIO)
- Tertiary: Off-site backup

**Restore Procedure:**
```bash
# 1. Stop application
kubectl scale deployment qamgr-api --replicas=0

# 2. Restore database
pg_restore -h postgres -U qamgr -d qamgr -c /backups/latest.dump

# 3. Verify data integrity
psql -h postgres -U qamgr -d qamgr -c "SELECT COUNT(*) FROM test_runs;"

# 4. Restart application
kubectl scale deployment qamgr-api --replicas=3

# 5. Monitor for issues
kubectl logs -f deployment/qamgr-api
```

### High Availability Testing

**Regular DR Drills:**
- Monthly: Restore from backup
- Quarterly: Full failover test
- Annually: Multi-region failover

## Security Hardening

### OS Level

```bash
# Disable root SSH
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config

# Enable firewall
ufw enable
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp  # SSH
ufw allow 443/tcp # HTTPS

# Keep system updated
apt-get update && apt-get upgrade -y

# Install fail2ban
apt-get install fail2ban -y
```

### Container Security

**Best Practices:**
- Run as non-root user
- Read-only root filesystem
- Drop capabilities
- Scan images for vulnerabilities
- Use distroless or Alpine base images

### Network Policies (Kubernetes)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: qamgr-api-policy
  namespace: qa-manager
spec:
  podSelector:
    matchLabels:
      app: qamgr-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: nginx-ingress
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
```

## CI/CD Pipeline

### Build Pipeline

```yaml
# .gitlab-ci.yml or .github/workflows/deploy.yml
stages:
  - test
  - build
  - deploy

test:
  stage: test
  script:
    - pytest tests/
    - mypy .
    - ruff check .
  
build:
  stage: build
  script:
    - docker build -t company/qamgr-api:${CI_COMMIT_SHA} .
    - docker tag company/qamgr-api:${CI_COMMIT_SHA} company/qamgr-api:latest
    - docker push company/qamgr-api:${CI_COMMIT_SHA}
    - docker push company/qamgr-api:latest

deploy-staging:
  stage: deploy
  script:
    - kubectl set image deployment/qamgr-api api=company/qamgr-api:${CI_COMMIT_SHA} -n qa-manager-staging
    - kubectl rollout status deployment/qamgr-api -n qa-manager-staging
  environment:
    name: staging

deploy-production:
  stage: deploy
  script:
    - kubectl set image deployment/qamgr-api api=company/qamgr-api:${CI_COMMIT_SHA} -n qa-manager
    - kubectl rollout status deployment/qamgr-api -n qa-manager
  environment:
    name: production
  when: manual
```

## Cost Optimization

### Resource Requests vs Limits

**Right-size containers:**
```yaml
resources:
  requests:
    memory: "512Mi"  # Guaranteed
    cpu: "500m"
  limits:
    memory: "1Gi"    # Max allowed
    cpu: "1000m"
```

### Spot/Preemptible Instances

- Use for Celery workers (can tolerate interruption)
- Not for database or API (need stability)

### Storage Optimization

- Use block storage for database (faster)
- Use object storage for artifacts (cheaper)
- Implement data retention policies
- Compress old logs

## Maintenance Windows

**Regular Maintenance:**
- Database vacuuming: Weekly, off-hours
- Log rotation: Daily
- Security updates: Monthly
- Application updates: Bi-weekly
- DR testing: Quarterly

**Zero-downtime Deployments:**
- Rolling updates in Kubernetes
- Blue-green deployments
- Database migrations with backward compatibility

## Open Questions

1. Do we need multi-region deployment for disaster recovery?
2. Should we use managed database (RDS, Cloud SQL) or self-hosted?
3. What's the expected data growth rate for capacity planning?
4. Do we need a CDN for static assets?
5. Should we implement rate limiting at the load balancer level?
6. What's the acceptable downtime for maintenance windows?
7. Do we need a staging environment that mirrors production?
