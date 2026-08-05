# LexiAct — AI-Powered Intelligent Personal Assistant

[![CI](https://github.com/Vikhyath1608/LexiAct/actions/workflows/ci.yml/badge.svg)](https://github.com/Vikhyath1608/LexiAct/actions)

A production-grade AI personal assistant backend built with **FastAPI**, **PostgreSQL**, **Redis**, **Celery**, and **Groq LLaMA 3.3-70B**.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Vikhyath1608/LexiAct.git && cd LexiAct

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env — set GROQ_API_KEY, SECRET_KEY, FROM_EMAIL, FROM_PASSWORD
# For OAuth: set GOOGLE_CLIENT_ID/SECRET and GITHUB_CLIENT_ID/SECRET

# 3. Start everything
docker-compose up --build

# 4. Open
# App:          http://localhost
# API docs:     http://localhost/docs
# Health check: http://localhost/health/ready
# Metrics:      http://localhost/metrics
# Celery UI:    http://localhost:5555
```

---

## Architecture

```
Client (React + TypeScript)
        │
      Nginx (reverse proxy, SSE buffering)
        │
   FastAPI (async Python 3.11)
   ├── Auth: JWT + refresh tokens + OTP + OAuth
   ├── Chat: Groq LLaMA 3.3-70B + context window
   ├── Automation: Strategy pattern dispatcher
   └── Agent: Playwright browser automation (SSE)
        │
   ┌────┼──────────────┐
   │    │              │
PostgreSQL  Redis    Celery Worker
(ORM 2.0)  (cache,  (email, timer,
           tokens,   alarm, TTS)
           rate limit)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API Framework | FastAPI 0.115 (async) |
| Language | Python 3.11 |
| LLM | Groq API — LLaMA 3.3-70B + tenacity retries |
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Cache / Rate Limiting | Redis 7 |
| Background Tasks | Celery 5 + Celery Beat |
| Auth | JWT (python-jose) + bcrypt + OTP + OAuth 2.0 |
| Observability | structlog + Prometheus + health checks |
| Browser Agent | Playwright |
| Frontend | React 18 + TypeScript + Vite + Tailwind |
| Container | Docker Compose (8 services) + Nginx |
| CI/CD | GitHub Actions |

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register (sends OTP email) |
| POST | `/api/v1/auth/verify-otp` | Activate account with OTP |
| POST | `/api/v1/auth/resend-otp` | Resend verification code |
| POST | `/api/v1/auth/login` | Login → JWT + refresh cookie |
| POST | `/api/v1/auth/refresh` | Rotate refresh token |
| POST | `/api/v1/auth/logout` | Invalidate refresh token |
| POST | `/api/v1/auth/logout-all` | Logout all devices |
| POST | `/api/v1/auth/forgot-password` | Send reset email |
| POST | `/api/v1/auth/reset-password` | Apply new password |
| POST | `/api/v1/auth/change-password` | Change password (auth) |
| GET  | `/api/v1/auth/me` | Current user profile |
| GET  | `/api/v1/auth/oauth/google/login` | Google OAuth redirect |
| GET  | `/api/v1/auth/oauth/github/login` | GitHub OAuth redirect |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat/message` | Send message |
| GET  | `/api/v1/chat/history` | Paginated history |
| DELETE | `/api/v1/chat/history` | Clear session |
| GET  | `/api/v1/chat/sessions` | Paginated sessions |

### Browser Agent
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/agent/run` | Start agent (SSE stream) |
| POST | `/api/v1/agent/input/{id}` | Human input |
| GET  | `/api/v1/agent/status/{id}` | Session status |
| DELETE | `/api/v1/agent/session/{id}` | Terminate |

---

## Automation Commands

| Say / Type | What happens |
|-----------|-------------|
| `what time is it` | Returns current time |
| `set timer for 5 minutes` | Celery countdown timer |
| `set alarm for 7:30 AM` | Celery scheduled alarm |
| `send email to John about meeting` | Groq drafts → confirm → Celery SMTP |
| `add contact John john@x.com` | Saves to contacts.json |
| `show tech news` | Opens Google News |
| `launch chrome` | Opens app via subprocess |

---

## Run Tests

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Author

**Vikhyath Rai** — [GitHub](https://github.com/Vikhyath1608) · [Portfolio](https://vikhyath-rai.vercel.app)
