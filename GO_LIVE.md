# JobAimer — Go-Live Guide

Step-by-step instructions to go from zero to live production deployment.
Estimated time: ~3 hours for a developer familiar with AWS.

---

## Prerequisites

- AWS account (3 recommended: dev / test / prod) — or use 1 account with workspaces
- GitHub account + repo created (`your-org/jobaimer`)
- ✅ **DONE** — Cloudflare account with `jobaimer.com` registered
- Supabase account (2 projects: user-facing + admin)
- Stripe account (live + test keys)
- Anthropic API key
- Temporal Cloud account (free tier works)

---

## Step 1 — Clone & Configure

```bash
git clone https://github.com/your-org/jobaimer.git
cd jobaimer

# Copy env file
cp .env.example .env
# Fill in all values in .env
```

---

## Step 2 — Supabase Setup

### 2a — Create user Supabase project
1. Go to https://supabase.com → New Project → name: `jobaimer-prod`
2. Copy: Project URL, `anon` key, `service_role` key, DB connection string
3. Enable Row Level Security (already in migrations)
4. Enable Realtime for `applications` table:
   - Dashboard → Database → Replication → Enable for `applications`

### 2b — Create admin Supabase project  
1. New Project → name: `jobaimer-admin-prod`
2. Copy: URL, `service_role` key
3. Create first admin user manually:
   ```sql
   INSERT INTO admin_users (email, role) VALUES ('your@email.com', 'super_admin');
   ```

### 2c — Run migrations (user project)
```bash
cd backend
export SUPABASE_DB_URL="postgresql://postgres:[password]@[host]:5432/postgres"
alembic upgrade head
```

---

## Step 3 — AWS Setup

### 3a — Bootstrap Terraform state bucket (one-time)
```bash
aws s3api create-bucket \
  --bucket jobaimer-terraform-state-prod \
  --region us-east-1

aws s3api put-bucket-versioning \
  --bucket jobaimer-terraform-state-prod \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket jobaimer-terraform-state-prod \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

### 3b — Uncomment Terraform backend
Edit `infra/terraform/main.tf`, uncomment the `backend "s3"` block and fill in:
```hcl
backend "s3" {
  bucket  = "jobaimer-terraform-state-prod"
  key     = "jobaimer/prod/terraform.tfstate"
  region  = "us-east-1"
  encrypt = true
}
```

### 3c — Apply Terraform
```bash
cd infra/terraform
cp prod.tfvars.example prod.tfvars
# Edit prod.tfvars — fill in all values

terraform init
terraform plan -var-file=prod.tfvars
terraform apply -var-file=prod.tfvars
```

This creates:
- Lambda function (`jobaimer-api-prod`)
- ECS cluster + service (`jobaimer-prod`)
- S3 bucket (`jobaimer-resumes-prod`)
- ECR repos (`jobaimer-api`, `jobaimer-agent`)
- API Gateway HTTP API
- CloudFront distribution
- WAF Web ACL
- Route53 records for `api.jobaimer.com`
- SSM parameters (empty, fill next)
- GitHub Actions OIDC IAM roles

### 3d — Store secrets in SSM
```bash
# Replace values with your actual secrets
aws ssm put-parameter --name "/jobaimer/prod/anthropic_api_key" \
  --value "sk-ant-..." --type SecureString --overwrite

aws ssm put-parameter --name "/jobaimer/prod/supabase_service_role_key" \
  --value "eyJ..." --type SecureString --overwrite

aws ssm put-parameter --name "/jobaimer/prod/stripe_secret_key" \
  --value "sk_live_..." --type SecureString --overwrite

aws ssm put-parameter --name "/jobaimer/prod/jwt_secret_key" \
  --value "$(openssl rand -hex 32)" --type SecureString --overwrite

aws ssm put-parameter --name "/jobaimer/prod/admin_session_secret" \
  --value "$(openssl rand -hex 32)" --type SecureString --overwrite

aws ssm put-parameter --name "/jobaimer/prod/supabase_db_url" \
  --value "postgresql://..." --type SecureString --overwrite
```

---

## Step 4 — GitHub Secrets

Go to GitHub → Settings → Secrets and variables → Actions → New repository secret

### Required secrets:
| Secret | Value |
|---|---|
| `AWS_ACCOUNT_ID` | Your AWS account ID (12 digits) |
| `DEV_API_BASE_URL` | `https://api-dev.jobaimer.com` |
| `TEST_API_BASE_URL` | `https://api-test.jobaimer.com` |
| `PROD_API_BASE_URL` | `https://api.jobaimer.com` |
| `DEV_SUPABASE_URL` | Dev Supabase project URL |
| `TEST_SUPABASE_URL` | Test Supabase project URL |
| `PROD_SUPABASE_URL` | Prod Supabase project URL |
| `DEV_SUPABASE_ANON_KEY` | Dev anon key |
| `TEST_SUPABASE_ANON_KEY` | Test anon key |
| `PROD_SUPABASE_ANON_KEY` | Prod anon key |
| `DEV_SUPABASE_DB_URL` | Dev DB connection string |
| `TEST_SUPABASE_DB_URL` | Test DB connection string |
| `DEV_STRIPE_PUBLISHABLE_KEY` | `pk_test_...` |
| `TEST_STRIPE_PUBLISHABLE_KEY` | `pk_test_...` |
| `PROD_STRIPE_PUBLISHABLE_KEY` | `pk_live_...` |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token (Pages:Edit) |
| `CLOUDFLARE_ACCOUNT_ID` | Your Cloudflare account ID |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook for deploy notifications |
| `TEST_USER_EMAIL` | Test account email for E2E tests |
| `TEST_USER_PASSWORD` | Test account password for E2E tests |
| `PROD_ADMIN_API_BASE_URL` | `https://admin-api.jobaimer.com` |
| `PROD_ADMIN_SUPABASE_ANON_KEY` | Admin Supabase anon key |

---

## Step 5 — First Manual Deploy (Bootstrap)

Before GitHub Actions works, do first deploy manually:

```bash
# Build & push backend
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

cd backend
docker build -t jobaimer-api .
docker tag jobaimer-api:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/jobaimer-api:prod-latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/jobaimer-api:prod-latest

# Update Lambda
aws lambda update-function-code \
  --function-name jobaimer-api-prod \
  --image-uri $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/jobaimer-api:prod-latest

# Build & push agent
cd ../agent
docker build -t jobaimer-agent .
docker tag jobaimer-agent:latest \
  $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/jobaimer-agent:prod-latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/jobaimer-agent:prod-latest
```

---

## Step 6 — Stripe Setup

1. Go to https://dashboard.stripe.com → Products → Create products:
   - **Starter Monthly**: $19/mo recurring → copy price ID → set `STRIPE_STARTER_MONTHLY_PRICE_ID`
   - **Starter Annual**: $190/yr recurring
   - **Pro Monthly**: $39/mo recurring
   - **Pro Annual**: $390/yr recurring

2. Create free trial coupon:
   - Coupons → Create → 100% off, 14 days, `FREETRIAL14`

3. Set up webhook endpoint:
   - Webhooks → Add endpoint → `https://api.jobaimer.com/webhooks/stripe`
   - Events: `checkout.session.completed`, `customer.subscription.*`, `invoice.*`
   - Copy signing secret → set `STRIPE_WEBHOOK_SECRET` in SSM

---

## Step 7 — Temporal Cloud Setup

1. Go to https://cloud.temporal.io → Create namespace: `jobaimer-prod`
2. Generate API key → copy to `.env` and SSM: `/jobaimer/prod/temporal_api_key`
3. Update `TEMPORAL_HOST` to your Temporal Cloud endpoint (e.g. `jobaimer-prod.a1b2c.tmprl.cloud:7233`)
4. Schedules → Create schedule for `UserCycleScheduler`:
   - Workflow: `UserCycleScheduler`
   - Cron: `0 */4 * * *` (every 4 hours)
5. Schedules → Create for daily cleanup:
   - Workflow: `StorageCleanupWorkflow`
   - Cron: `0 2 * * *` (2am UTC)
6. Create for coupon expiry:
   - Workflow: `CouponExpiryCheckWorkflow`
   - Cron: `0 0 * * *` (midnight UTC)

---

## Step 8 — Cloudflare DNS & Pages

### DNS — jobaimer.com ✅ REGISTERED

Now that the domain is live in Cloudflare, add these DNS records after Terraform runs (Step 3) — you'll need the API Gateway domain name it outputs:

```
Type   Name    Value                                    Proxy  TTL
CNAME  api     [paste API Gateway domain from Terraform] ✅ ON   Auto
CNAME  www     jobaimer.com                              ✅ ON   Auto
```

> **Tip:** The `@` root record for jobaimer.com is handled automatically by Cloudflare Pages when you connect the project (Step 8b below).

### Cloudflare Pages projects (auto-created by CI/CD on first deploy):
- `jobaimer-prod` → `jobaimer.com`
- `jobaimer-admin-prod` → `admin.jobaimer.com`

### Admin IP restriction (Cloudflare Access):
1. Zero Trust → Access → Applications → Add application
2. Self-hosted → Domain: `admin.jobaimer.com`
3. Policy: Allow → IP ranges → add your office/VPN IPs

---

## Step 9 — Verify Production

```bash
# Health check
curl https://api.jobaimer.com/health
# Expected: {"status":"healthy","version":"..."}

# Register test user
curl -X POST https://api.jobaimer.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","phone":"+15551234567","password":"TestPass123!"}'

# Check frontend loads
open https://jobaimer.com
```

---

## Step 10 — Ongoing Deployment Flow

After bootstrap, all deploys are automated:

```
feature/* branch → PR → CI runs (lint + tests + SAST)
PR merged to dev  → deploy-dev.yml → auto-deploys to dev environment
dev merged to test → deploy-test.yml → deploys + integration + E2E + ZAP scan
test merged to main → deploy-prod.yml → canary 10% → health check → 100% rollout
```

**To deploy a fix:**
```bash
git checkout -b fix/my-fix
# make changes
git push origin fix/my-fix
# Open PR → merge to dev → promote through test → main
```

---

## Estimated Monthly Costs at Launch (10 users)

| Service | Cost |
|---|---|
| Supabase (Pro) | $25/mo |
| Temporal Cloud | $0 (free tier) |
| AWS (Lambda + ECS + S3) | ~$15/mo |
| Anthropic API | ~$65/mo (10 users × $6.50) |
| Cloudflare (Pages + Registrar) | ~$1/mo |
| Stripe | 2.9% + 30¢ per transaction |
| **Total infra** | **~$106/mo** |

At $19/mo per user: 10 users = $190 MRR → **$84 net after infra** ✅

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Lambda 500 errors | CloudWatch → `/aws/lambda/jobaimer-api-prod` |
| Agent not applying | ECS → jobaimer-agent-prod → logs |
| Migrations failing | Run `alembic history` + `alembic current` |
| Stripe webhooks failing | Stripe dashboard → Webhooks → event log |
| CORS errors | Lambda env `ALLOWED_ORIGINS` — add your domain |
| Temporal workflows stuck | Temporal Cloud UI → namespace → workflows |
