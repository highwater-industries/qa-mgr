# Quarion Deployment Guide

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 2GB+ RAM available
- 10GB+ disk space
- Internet connection (for cloning repository)

## Quick Start

### 1. Download Docker Compose Configuration

On your deployment server:

```bash
# Create deployment directory
mkdir -p ~/quarion-deployment
cd ~/quarion-deployment

# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/highwater-industries/qa-mgr/main/docker-compose.yml

# Download environment template
curl -O https://raw.githubusercontent.com/highwater-industries/qa-mgr/main/.env.example
mv .env.example .env
```

### 2. Configure Environment

```bash
# Edit .env with your configuration
nano .env
```

**Important**: Change these values in `.env`:
- `POSTGRES_PASSWORD` - Strong database password
- `RABBITMQ_PASSWORD` - Strong message broker password
- `SECRET_KEY` - Random 64+ character string for JWT tokens

**Generate secure values:**
```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Generate passwords
openssl rand -base64 32
```

### 3. Start Services

The Docker build process will automatically clone the latest code from GitHub.

```bash
# Build and start all services (this will clone the repo automatically)
docker-compose up -d --build

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

**The build process will:**
1. Clone the latest code from GitHub (main branch)
2. Install all dependencies
3. Build the Docker images
4. Start all services

### 4. Initialize Database

```bash
# Run database migrations
docker-compose exec api alembic upgrade head

# Create initial admin user (optional)
docker-compose exec api python -c "
from database.config import get_db
from database.models.user import User
from passlib.context import CryptContext
import asyncio

async def create_admin():
    pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
    async for db in get_db():
        admin = User(
            email='admin@example.com',
            username='admin',
            hashed_password=pwd_context.hash('changeme'),
            is_superuser=True,
            is_active=True
        )
        db.add(admin)
        await db.commit()
        print('Admin user created: admin@example.com / changeme')
        break

asyncio.run(create_admin())
"
```

### 4. Access Application

**Without nginx (default):**
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **RabbitMQ Management**: http://localhost:15672

**With nginx (if started with `--profile with-nginx`):**
- **API**: http://localhost:80
- **API Docs**: http://localhost:80/docs
- **RabbitMQ Management**: http://localhost:15672

## Production Deployment

### SSL/HTTPS Setup

1. Obtain SSL certificates (Let's Encrypt recommended)
2. Place certificates in `./ssl/` directory:
   ```
   ssl/
   ├── certificate.crt
   └── private.key
   ```
3. Uncomment HTTPS server block in `nginx.conf`
4. Update `server_name` with your domain
5. Restart nginx: `docker-compose restart nginx`

### Security Checklist

- [ ] Change all default passwords in `.env`
- [ ] Use strong `SECRET_KEY` (32+ random characters)
- [ ] Enable HTTPS in nginx configuration
- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Configure firewall to allow only ports 80/443
- [ ] Set up automated backups for PostgreSQL
- [ ] Review and adjust rate limits in `nginx.conf`
- [ ] Disable RabbitMQ management port (15672) in production

### Backup and Restore

#### Backup Database
```bash
docker-compose exec postgres pg_dump -U quarion quarion > backup-$(date +%Y%m%d).sql
```

#### Restore Database
```bash
cat backup-20260103.sql | docker-compose exec -T postgres psql -U quarion quarion
```

#### Backup Volumes
```bash
docker run --rm -v quarion_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz -C /data .
```

## Scaling

### Add More Workers

```bash
docker-compose up -d --scale worker=3
```

### Monitor Resources

```bash
# View resource usage
docker stats

# View service logs
docker-compose logs -f api
docker-compose logs -f worker
```

## Updates

### Deploy Specific Branch or Tag

To deploy a specific version:

```bash
# Deploy specific branch
docker-compose build --build-arg GIT_BRANCH=develop api worker
docker-compose up -d

# Deploy specific tag/release
docker-compose build --build-arg GIT_BRANCH=v1.2.0 api worker
docker-compose up -d
```

### Update to Latest Code

```bash
# Rebuild with latest code from main branch
docker-compose down
docker-compose build --no-cache --build-arg GIT_BRANCH=main
docker-compose up -d

# Run any new migrations
docker-compose exec api alembic upgrade head
```

## Troubleshooting

### API won't start
```bash
# Check logs
docker-compose logs api

# Verify database connection
docker-compose exec api python -c "from database.config import engine; print('DB OK')"
```

### Database connection issues
```bash
# Check if postgres is healthy
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U quarion -d quarion -c "SELECT 1"
```

### Worker not processing jobs
```bash
# Check worker logs
docker-compose logs worker

# Verify RabbitMQ connection
docker-compose exec worker python -c "from celery import Celery; app = Celery(); print('Celery OK')"
```

## Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v
```

## Environment Variables

See `.env.example` for all available configuration options.

## Support

For issues or questions, refer to the main README.md or open an issue on GitHub.
