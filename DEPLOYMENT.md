# Quarion Deployment Guide

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 2GB+ RAM available
- 10GB+ disk space

## Quick Start

### 1. Clone and Configure

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

**Important**: Change these values in `.env`:
- `POSTGRES_PASSWORD` - Strong database password
- `RABBITMQ_PASSWORD` - Strong message broker password
- `SECRET_KEY` - Random 32+ character string for JWT tokens

### 2. Start Services

```bash
# Start core services (API, database, workers)
docker-compose up -d

# OR: Start with nginx reverse proxy
docker-compose --profile with-nginx up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### 3. Initialize Database

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

```bash
# Pull latest code
git pull

# Rebuild containers
docker-compose build

# Apply database migrations
docker-compose exec api alembic upgrade head

# Restart services
docker-compose up -d
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
