# Coffee Connoisseur Platform

A Python-first, security-conscious web application for coffee enthusiasts to manage collections, document tasting experiences, and receive AI-powered recommendations. Built with production-grade engineering practices: FastAPI microservices, OAuth2 + TOTP MFA, automated security scanning baked into CI/CD, and secrets management via AWS Secrets Manager.

**Status: In Progress — Phase 1 of 6 (Foundation)**

---

## Tech Stack

**Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Celery, Redis  
**Frontend:** Next.js 14, TypeScript, Tailwind CSS, TanStack Query  
**Security Toolchain:** Bandit (SAST), Safety (CVE scanning), Trivy (container scanning), pytest security suite  
**Infrastructure:** Docker, AWS ECS Fargate, RDS PostgreSQL, ElastiCache Redis, AWS Secrets Manager, GitHub Actions  

---

## Architecture

Three core services, each independently containerized:

```
[ Next.js Frontend ]
        |
[ AWS ALB → Rate Limit Middleware ]
        |              |                   |
[ auth-service ]  [ coffee-service ]  [ security-service ]
        |              |                   |
[ RDS PostgreSQL ] [ ElastiCache Redis ] [ AWS Secrets Manager ]
```

| Service | Responsibility |
|---|---|
| auth-service | Registration, login, JWT issuance, refresh token rotation, TOTP MFA |
| coffee-service | Coffee catalog, collections, tasting notes, AI recommendations |
| security-service | Rate limiting, automated vulnerability scanning, anomaly detection |

---

## Security & Automation Highlights

- Sliding window rate limiting with Redis for brute force prevention
- Bandit SAST + Safety CVE scan + Trivy container scan as blocking CI/CD gates
- OAuth2 with JWT rotation and TOTP MFA via pyotp
- Zero hardcoded credentials — all secrets fetched at runtime from AWS Secrets Manager
- Dedicated `tests/security/` pytest module covering auth boundaries, RBAC, and injection resistance

---

## CI/CD Pipeline

Every push runs through four security gates before any code reaches production:

1. Bandit SAST — blocks on HIGH severity findings
2. Safety CVE scan — blocks on CRITICAL dependency vulnerabilities
3. pytest security suite — blocks on any auth or RBAC regression
4. Trivy container scan — blocks on CRITICAL image vulnerabilities

---

## Local Development

_Setup instructions will be added upon Phase 1 completion._

Prerequisites: Docker, Docker Compose, Python 3.12, Node.js 18+

```bash
git clone https://github.com/jamesg8025/coffee.git
cd coffee-connoisseur-platform
# setup instructions coming soon
```

---

## Project Roadmap

- [x] SRD v3.0 — architecture and requirements defined
- [ ] Phase 1 — monorepo structure, Docker Compose, Alembic setup
- [ ] Phase 2 — auth-service with JWT, refresh token rotation, TOTP MFA
- [ ] Phase 3 — coffee-service with catalog, collections, AI recommendations
- [ ] Phase 4 — security-service with rate limiting and automated scanning
- [ ] Phase 5 — CI/CD pipeline with all security gates, ECS deployment
- [ ] Phase 6 — Next.js frontend