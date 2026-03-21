# JobAimer 🤖

> Autonomous AI job application agent — applies to jobs 24/7, tailors every resume with AI

**Production:** https://jobaimer.com | **Admin:** https://admin.jobaimer.com

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.12+ |
| Node.js | 20 LTS |
| pnpm | 9+ |
| Docker | 25+ |
| Terraform | 1.8+ |
| AWS CLI | 2+ (configured) |

## Accounts Required
- AWS (billing enabled)
- Supabase (create 2 projects: user + admin)
- Stripe (products + prices created)
- Anthropic API key
- Temporal Cloud account
- Cloudflare account (domain: jobaimer.com)

## Quick Start (Local Dev)

```bash
git clone https://github.com/YOUR_ORG/jobaimer.git && cd jobaimer
cp .env.example .env          # fill in all values
docker compose up --build     # starts API + Worker + Temporal
cd frontend && pnpm install && pnpm dev          # :5173 user app
cd frontend/admin && pnpm install && pnpm dev    # :5174 admin
```

## Branch Strategy

```
feature/* ──▶ dev ──▶ test ──▶ main
                CI        CI+E2E    Canary deploy
               (dev AWS)  (test AWS) (prod AWS → jobaimer.com)
```

## CI/CD
- **GitHub Actions** handles all environments
- Workflows: `.github/workflows/ci.yml`, `deploy-dev.yml`, `deploy-test.yml`, `deploy-prod.yml`
- AWS credentials via OIDC (no static keys stored in GitHub)
- Canary deploy to prod: 10% → health check → 100%

## Infrastructure
```
jobaimer.com (Cloudflare) → CloudFront → API Gateway → Lambda (FastAPI)
                                                      → ECS Fargate Spot (Playwright + Temporal Workers)
S3: jobaimer-resumes-prod (private, lifecycle rules)
Supabase: Postgres + Auth + Realtime + Storage
```
