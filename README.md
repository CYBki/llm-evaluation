# RAG Evaluation API

**Production-ready LLM evaluation platform for RAG and Agent systems**

Automatically evaluate RAG (Retrieval-Augmented Generation) and multi-agent system outputs using LLM-as-Judge methodology with 9+ comprehensive metrics.

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green?logo=fastapi)](https://fastapi.tiangolo.com/)

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose installed
- 4GB+ RAM, 2+ CPU cores
- (Optional) OpenAI API key for evaluation

### 1. Development Setup

```bash
# Clone repository
git clone https://github.com/CYBki/llm-evaluation.git
cd llm-evaluation

# Start development environment
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# API available at: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### 2. Test Environment

```bash
# Start test environment
docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d

# Run tests
docker-compose exec api pytest

# Stop
docker-compose -f docker-compose.yml -f docker-compose.test.yml down
```

### 3. Production Deployment

```bash
# Create production environment file
cp .env.prod.template .env.prod

# Edit with real credentials
nano .env.prod

# Start production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check health
curl http://localhost/health
```

---

## 📋 Features

### Evaluation Metrics

| Metric | Description |
|--------|-------------|
| **hallucination_score** | Detects fabricated information not supported by context |
| **answer_relevancy** | Measures answer relevance to the question |
| **context_precision** | Evaluates quality of retrieved context |
| **context_recall** | Checks if all necessary information is present |
| **context_relevancy** | Measures context relevance to the question |
| **faithfulness** | Ensures answer is grounded in provided context |
| **answer_correctness** | Compares answer against ground truth |
| **citation_check** | Validates proper source citations |
| **response_completeness** | Checks if answer is comprehensive |

### System Features

- ✅ **Multi-environment support**: Dev, Test, Production
- ✅ **Docker Compose overlay pattern**: Environment-specific configurations
- ✅ **Nginx reverse proxy**: Single URL management
- ✅ **Network isolation**: Internal/external network separation
- ✅ **Resource limits**: CPU/RAM constraints per service
- ✅ **Health checks**: Automated monitoring
- ✅ **Async evaluation**: Celery background jobs (production)
- ✅ **Webhook callbacks**: Result notifications
- ✅ **API authentication**: API key-based auth
- ✅ **Rate limiting**: DDoS protection
- ✅ **CORS management**: Cross-origin security

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────┐
│         Nginx (Reverse Proxy)           │
│         Port 80/443 (Single URL)        │
└────────────────┬────────────────────────┘
                 │
        ┌────────┴─────────┐
        ↓                  ↓
   [External]         [Internal]
        │                  │
        │          ┌───────┼───────┬────────┐
        │          ↓       ↓       ↓        ↓
        │      ┌─────┐ ┌─────┐ ┌─────┐  ┌────────┐
        │      │ API │ │ DB  │ │Redis│  │ Worker │
        │      └─────┘ └─────┘ └─────┘  └────────┘
        │
   (Public access)    (Internal only - secured)
```

### Technology Stack

- **API**: FastAPI (Python 3.11)
- **Database**: PostgreSQL 15
- **Cache & Queue**: Redis 7
- **Background Jobs**: Celery
- **Web Server**: Gunicorn (production) / Uvicorn (development)
- **Reverse Proxy**: Nginx
- **Container Orchestration**: Docker Compose

---

## 🔧 Configuration

### Environment Variables

All configuration is managed via environment variables. See `.env.example` for full list.

**Key variables:**

```bash
# Database
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname

# OpenAI
OPENAI_API_KEY=sk-your-key-here
STAGE_1_MODEL=gpt-5.2
STAGE_2_MODEL=gpt-4o-mini

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# Evaluation Mode (sync for dev, async for prod)
EVALUATION_MODE=async

# CORS (dev: "*", prod: specific domains)
CORS_ORIGINS=https://app.example.com

# Webhook Security
WEBHOOK_SECRET=your-32-byte-hex-secret

# Production Runtime
WEB_CONCURRENCY=4
CELERY_WORKER_CONCURRENCY=8
```

---

## 📖 API Usage

### Register User

```bash
curl -X POST http://localhost:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password"
  }'
```

### Get API Key

```bash
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "secure_password"
  }'
```

### Submit Trace for Evaluation

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "question": "What is the capital of France?",
    "answer": "The capital of France is Paris.",
    "contexts": ["Paris is the capital and largest city of France."],
    "ground_truth": "Paris",
    "webhook_url": "https://your-app.com/webhook"
  }'
```

### Get Evaluation Results

```bash
curl http://localhost:8000/api/traces/{trace_id} \
  -H "X-API-Key: your-api-key"
```

---

## 🚢 Deployment

### Docker Compose Overlay Pattern

The project uses Docker Compose overlay pattern for multi-environment support:

```
docker-compose.yml          → Base configuration (common services)
docker-compose.dev.yml      → Development overrides
docker-compose.test.yml     → Test overrides
docker-compose.prod.yml     → Production overrides
```

### Environment-Specific Commands

**Development:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
# Features: hot-reload, all ports open, debug mode
```

**Test:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d
# Features: isolated DB, no hot-reload, ports closed
```

**Production:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# Features: Nginx, network isolation, resource limits, async mode
```

### Network Configuration

**Production network isolation:**

- **Internal Network**: DB, Redis, Worker (no external access)
- **External Network**: Nginx, API (public access)
- **Security**: DB and Redis are not accessible from outside

### Resource Limits

| Service | CPU Limit | Memory Limit |
|---------|-----------|--------------|
| API | 0.5 core | 512MB |
| Worker | 1.0 core | 1GB |
| DB | 1.0 core | 1GB |
| Redis | 0.25 core | 256MB |
| Nginx | 0.25 core | 128MB |

**Recommended server:** 4+ CPU cores, 4GB+ RAM

---

## 📊 Monitoring

### Health Check

```bash
# Via Nginx (production)
curl http://localhost/health

# Direct API (development)
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "ok",
  "details": {
    "api": "ok",
    "database": "ok",
    "redis": "ok"
  }
}
```

### Container Stats

```bash
# Real-time resource usage
docker stats

# Service status
docker compose ps

# Logs
docker compose logs -f api
docker compose logs -f worker
```

---

## 🔐 Security

### Secret Management

- ✅ `.env.prod` is git-ignored (never committed)
- ✅ Use `.env.prod.template` as reference
- ✅ Generate secure webhook secret: `openssl rand -hex 32`
- ✅ Use strong database passwords in production
- ✅ Restrict CORS origins in production

### Network Security

- ✅ DB and Redis are not exposed to external network
- ✅ Nginx handles SSL termination (HTTPS)
- ✅ Rate limiting enabled (10 req/s with burst of 20)
- ✅ Security headers automatically added

---

## 📚 Documentation

- **System Documentation**: [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md)
  - Section 18: Production Deployment Architecture
- **Integration Guide**: [docs/Entegrasyon Rehberi.md](docs/Entegrasyon%20Rehberi.md)
- **API Docs**: http://localhost:8000/docs (when running)
- **Metrics Reference**: [SYSTEM_DOCUMENTATION.md#9-metrikler](SYSTEM_DOCUMENTATION.md#9-metrikler)

---

## 🛠️ Development

### Project Structure

```
llm-evaluation/
├── app/                          # Application code
│   ├── routers/                  # API endpoints
│   ├── services/                 # Business logic
│   ├── evaluation/               # LLM evaluation engine
│   ├── models/                   # Database models
│   └── schemas/                  # Pydantic schemas
├── docker-compose.yml            # Base Docker config
├── docker-compose.dev.yml        # Development overrides
├── docker-compose.test.yml       # Test overrides
├── docker-compose.prod.yml       # Production overrides
├── nginx.conf                    # Reverse proxy config
├── .env.example                  # Environment template
├── .env.prod.template            # Production template
├── Dockerfile                    # Multi-stage build
└── SYSTEM_DOCUMENTATION.md       # Complete technical docs
```

### Running Tests

```bash
# Start test environment
docker-compose -f docker-compose.yml -f docker-compose.test.yml up -d

# Run all tests
docker-compose exec api pytest

# Run with coverage
docker-compose exec api pytest --cov=app

# Stop test environment
docker-compose -f docker-compose.yml -f docker-compose.test.yml down
```

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'feat: add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📝 License

MIT License

---

## 🆘 Support

For issues and questions:
- GitHub Issues: [Create an issue](https://github.com/CYBki/llm-evaluation/issues)
- Documentation: [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md)

---

## 🎯 Roadmap

- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Monitoring dashboard (Prometheus + Grafana)
- [ ] SSL certificate automation (Let's Encrypt)
- [ ] Kubernetes deployment manifests
- [ ] Multi-region deployment support
- [ ] Evaluation result caching optimization
- [ ] Custom LLM provider support (beyond OpenAI)

---

**Made with ❤️**
