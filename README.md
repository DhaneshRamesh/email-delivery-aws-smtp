# Email Delivery Platform Starter

Production-ready FastAPI backend scaffold for a multi-tenant email delivery platform similar to Mailchimp. It integrates FastAPI, SQLAlchemy (SQLite by default for local testing, PostgreSQL-ready for production), Alembic, Redis + RQ, AWS SES, templated emails, and a growing set of operational endpoints. The repository includes a Dockerfile, GitHub Actions workflow, and migration scaffolding so you can containerize, deploy, and evolve the service quickly.

This document is intentionally verbose and comprehensive. It is a practical runbook that explains what the system does, how to run it locally, how to deploy it to AWS, and how to operate and extend it safely.

## System Verification (Completed)
- Neon PostgreSQL configured; Alembic migrations applied successfully (PostgresqlImpl) and tables exist: tenants, campaigns, subscribers, email_logs, suppressed_emails, alembic_version.
- Redis running locally; RQ worker starts (`Worker rq:worker:... started`, `Listening on emails…`, `Cleaning registries for queue: emails`).
- Queued send-test works end-to-end: `POST /send/send-test` with `"enqueue": true` returns a valid job ID (e.g., `b1a6f92b-ac77-440d-87bc-2cda672a5ada`).
- Worker processes queued jobs via AWS SES (sandbox recipient limits apply).

## Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [Environment Variables](#environment-variables)
- [Local Development](#local-development)
- [Migrations](#migrations)
- [Running the Stack](#running-the-stack)
- [Queues and Background Jobs](#queues-and-background-jobs)
- [API Surface](#api-surface)
- [Email Flow](#email-flow)
- [Domain Verification Flow](#domain-verification-flow)
- [Campaign Execution Flow](#campaign-execution-flow)
- [Suppression Handling](#suppression-handling)
- [Bounce/Complaint Handling](#bouncecomplaint-handling)
- [Container Image](#container-image)
- [CI/CD via GitHub Actions](#cicd-via-github-actions)
- [AWS Deployment Guide](#aws-deployment-guide)
- [Observability and Operations](#observability-and-operations)
- [Security and Hardening](#security-and-hardening)
- [Rate Limiting](#rate-limiting)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Common Tasks](#common-tasks)
- [Project Structure](#project-structure)

## Features
- FastAPI application with modular routers, CORS, startup hooks, and health checks
- SQLAlchemy models + database connection handling via `DATABASE_URL` (SQLite for local, PostgreSQL recommended for production)
- Alembic migrations (initial schema plus suppression list) ready to apply and extend
- AWS SES helper with reusable boto3 client
- Redis-backed queues (RQ) with worker + scheduler utilities, plus a campaign runner
- Template rendering via Jinja2
- Configurations powered by environment variables / `.env`
- Routers for tenants, campaigns, subscribers (with bulk import), suppression lists, domain verification, email logs, admin triggers, and SES/SNS events
- Dockerfile for reproducible builds and `.github/workflows/docker-deploy.yml` for CI/CD
- Basic pytest covering the `/send/send-test` route; easy to extend with more tests

## Architecture
- **API Layer (FastAPI)**: Defines HTTP routes for tenants, campaigns, subscribers, domains, email logs, suppression, admin triggers, and event webhooks. Uses Pydantic models for validation and response shaping.
- **Service Layer**: SESService for email delivery, CampaignService for campaign validation and enqueueing helpers. Keeps business logic separate from routes.
- **Persistence Layer**: SQLAlchemy ORM models mapped to PostgreSQL/SQLite. Session handling provided via dependency injection.
- **Queue Layer**: Redis + RQ. Worker runs `process_email_job` for single sends and `_run_campaign_job` for bulk campaign sends. Scheduler optional.
- **Migrations**: Alembic tracks schema evolution. Initial migration plus suppression list addition; future changes via `alembic revision --autogenerate`.
- **Infrastructure Glue**: Dockerfile for containerization; GitHub Actions workflow to build/test/push image and force ECS deploy; env-driven configuration for cloud portability.

## Data Model
- **Tenant**: `id`, `name` (unique), `contact_email`, `ses_verified`, timestamps. Relationships to Campaign, Subscriber, SuppressedEmail.
- **Campaign**: `id`, `tenant_id`, `name`, `subject`, `body`, `status` (draft/scheduled/sending/completed), `scheduled_at`, timestamps. Relationship to EmailLog.
- **Subscriber**: `id`, `tenant_id`, `email`, `first_name`, `last_name`, `status`, timestamps.
- **EmailLog**: `id`, `tenant_id`, `campaign_id`, `subscriber_id`, `message_id`, `status` (queued/bounced/complaint/delivered/etc.), `sent_at`, `created_at`.
- **SuppressedEmail**: `id`, `tenant_id`, `email`, `reason`, `created_at`.

## Environment Variables
Copy `.env.example` to `.env` and set:
- `APP_NAME` – display name in OpenAPI docs (default CourierX)
- `ENVIRONMENT` – development/staging/production
- `API_VERSION` – API version string
- `DATABASE_URL` – required; e.g., your Neon URL `postgresql+psycopg://...` (quoted values are stripped automatically; keep `sslmode=require`)
- `REDIS_URL` – e.g., `redis://localhost:6379/0` or ElastiCache endpoint
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` – optional for local dev; omit in ECS/Lambda when using IAM roles
- `AWS_REGION_NAME` – required region for SES (e.g., `us-east-1`)
- `SES_SENDER_EMAIL` – verified sender in SES (e.g., `no-reply@chachamailer.com`)
- `ALLOWED_ORIGINS` – comma-separated CORS origins
- `RATE_LIMIT_PER_MINUTE` – simple in-memory rate limit for the send-test endpoint

Notes:
- No SQLite fallback remains; a valid PostgreSQL URL is required.
- Quoted URLs in `.env` are handled by config.
- In production, prefer AWS Secrets Manager or SSM Parameter Store and inject via task definitions/EB env vars rather than shipping a `.env`.
- For ECS/EC2/Lambda with an IAM role, leave `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` unset so boto3 uses the role automatically.

## Local Development
1) **Install deps**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2) **Configure env**
```bash
cp .env.example .env
```
Update DB/Redis/AWS values as needed.

### Local AWS/SES setup
- Local testing works if either (a) AWS credentials are present in `.env` or (b) the AWS CLI is configured via `aws configure`. Do not leave empty `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` entries; blank values override boto3's provider chain.
- Ensure `AWS_REGION_NAME` matches your verified SES identities; for this project use `ap-southeast-2` (Sydney).

### Local SES Authentication (Required)
- When running locally (outside AWS), boto3 needs credentials from either `.env` (`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`) or the AWS CLI (`aws configure`). If neither is set, SES calls will fail with `InvalidClientTokenId`.
- This does not apply to ECS/Lambda, where IAM roles supply credentials automatically; do not set static keys there.
- Example `.env` snippet for local testing:
```
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION_NAME=ap-southeast-2
```

3) **Apply migrations**
```bash
alembic upgrade head
```
The app will auto-create tables for quick prototyping if migrations aren’t applied yet, but use Alembic for real databases.

4) **Run services**
```bash
uvicorn src.api.app:app --reload
python3 -m src.queue.worker  # in a separate terminal (requires Redis)
# optional scheduler
# python -m src.queue.scheduler
```
Redis options: `brew install redis && brew services start redis`, or run a container `docker run --name redis -p 6379:6379 -d redis:7`.

5) **Run tests**
```bash
pytest
```

### Local validation checklist
- Redis running locally (`redis-cli ping` → PONG).
- `.env` present with `AWS_REGION_NAME=ap-southeast-2` and optional AWS credentials removed if unused.
- API and worker start without errors (`uvicorn ...` and `python -m src.queue.worker`).
- `/send/send-test` with `{"enqueue": true}` returns a job ID and the worker logs a send attempt.

## macOS Local Development (RQ Worker)
- On macOS, Python's fork plus Objective-C frameworks can crash RQ workers with `objc: initialize may have been in progress in another thread when fork() was called`.
- Workaround (macOS-only): set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` before starting the worker.
- Example:
```bash
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
python3 -m src.queue.worker
```
- This is not required in ECS/production (Linux).

## Migrations
- Autogenerate a new migration after model changes:
```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
- The template lives at `alembic/script.py.mako`. Metadata is pulled from `src.db.models.Base`.
- Keep migrations committed so environments stay in sync. On first deploy, run `alembic upgrade head` against your target DB (ECS task, EB app, etc.).
- Alembic reads `settings.database_url`, so it will target the same Neon/PostgreSQL database as the app.
- Status: confirmed working against Neon (PostgresqlImpl) with all revisions applied and tables present.

## Running the Stack
- **API**: `uvicorn src.api.app:app --reload`
- **Worker**: `python -m src.queue.worker` (requires Redis reachable at `REDIS_URL`)
- **Scheduler** (optional): `python -m src.queue.scheduler`
- **Health**: `GET /health`
- **Docs**: `GET /docs` (Swagger UI) or `/redoc`

## Queues and Background Jobs
- **Single send**: `/send/send-test` can enqueue if `"enqueue": true`; worker executes `process_email_job`.
- **Campaign send**: `/campaigns/{id}/send-now` runs synchronously; `/admin/enqueue-campaign/{id}` enqueues `_run_campaign_job` via RQ. Worker pulls from the default `emails` queue.
- **EmailLog**: Each enqueued campaign email inserts a log with `status="queued"` and the RQ job ID as `message_id`. SNS events can update status to bounced/complaint/delivered.
- End-to-end verified: queued send-test returns a job ID and the running worker processes it successfully via SES (sandbox rules apply).

## API Surface
- Tenants: `POST/GET/LIST/PATCH/DELETE /tenants`
- Campaigns: CRUD at `/campaigns`; send/schedule/cancel/preview via `/campaigns/{id}/...`
- Subscribers: CRUD + bulk import CSV at `/subscribers/bulk-import`
- Suppression: `POST/GET/DELETE /suppression`
- Domains: request verification, mark verified, status at `/domains/...`
- Email logs: `GET /email-logs/`, `GET /email-logs/campaign/{id}`, `GET /email-logs/{id}`
- Admin tools: manual campaign run/enqueue at `/admin/...`
- Events: `POST /events/sns` for SES→SNS webhooks
- Send test: `POST /send/send-test`
- Health: `GET /health`

## Email Flow
1. Client calls `/send/send-test` or campaign send endpoints.
2. If enqueued, RQ job dispatches `SESService.send_email`.
3. Worker picks up the queued job from Redis and calls SES.
4. SES returns `MessageId`; stored in `EmailLog`.
5. SNS notifications (bounce/complaint) call `/events/sns` and update `EmailLog.status`.
6. Suppressed emails are excluded from campaign sends.

## Domain Verification Flow
1. `POST /domains/request-verification` returns SES-style TXT/CNAME records.
2. Add DNS records with your DNS provider.
3. After SES validates, call `PATCH /domains/mark-verified` to set `tenant.ses_verified=True`.
4. `GET /domains/status?tenant_id=` returns current flag.

## Campaign Execution Flow
1. Create campaign via `/campaigns/`.
2. Optional: schedule via `/campaigns/{id}/schedule` (sets `scheduled_at`, `status=scheduled`).
3. Execute now via `/campaigns/{id}/send-now` (sync) or enqueue via `/admin/enqueue-campaign/{id}` (async).
4. `campaign_runner` loads active subscribers (minus suppression), enqueues email jobs, writes EmailLog rows, updates status to sending → completed.

## Suppression Handling
- Add suppressed email via `POST /suppression/` with `tenant_id`, `email`, `reason`.
- Suppressed addresses are excluded from `campaign_runner` recipient selection.
- List/remove entries via `GET/DELETE /suppression`.

## Bounce/Complaint Handling
- SES should publish to SNS; configure SNS subscription to your `/events/sns` endpoint.
- Handler parses SNS payload, maps `notificationType` to statuses (bounce/complaint/delivered default), and updates `EmailLog` by `message_id`.
- If a log is not found, a warning is logged.

## Container Image
Build and run locally:
```bash
docker build -t email-delivery .
docker run --env-file .env -p 8000:8000 email-delivery
```
Notes:
- Mount `-v $(pwd)/data:/app/data` to persist SQLite.
- In ECS, supply env vars via task definition; avoid shipping `.env`.
- The Dockerfile installs build-essential/libpq-dev for psycopg wheels.

## CI/CD via GitHub Actions
Workflow: `.github/workflows/docker-deploy.yml`
- Triggers: push to `main` or manual dispatch.
- Steps: checkout → setup Python 3.13 → install deps → run pytest → configure AWS creds → login to ECR → build/push image (SHA + latest) → optional ECS force deploy.
- Configure secrets:
  - `AWS_ACCESS_KEY_ID`
  - `AWS_SECRET_ACCESS_KEY`
  - (Optionally use OIDC + IAM role instead of static keys)
- Update `AWS_REGION`, `ECR_REPOSITORY`, `ECS_CLUSTER`, `ECS_SERVICE` envs as needed. For this repo use `ap-southeast-2` (Sydney) for SES/ECS/SSM.

## AWS Deployment Guide
1) **Provision resources**
   - RDS/Aurora PostgreSQL; grab connection string for `DATABASE_URL`
   - ElastiCache Redis for RQ; set `REDIS_URL`
   - ECR repository for images
   - ECS cluster + Fargate service (or EC2/EKS/EB) for API + worker; ensure two task definitions if you want separate worker service
   - SES: verify domain/sender; request production access to exit sandbox
   - SNS: topic + subscription pointing to your `/events/sns` endpoint (HTTPS)
2) **Secrets and config**
   - Store DB creds, Redis URL, SES creds, and app settings in Secrets Manager/SSM
   - Map secrets/env vars into ECS task definitions
3) **Build and push**
   - Use the GitHub Actions workflow or run locally: `docker build` + `docker push` to ECR
4) **Migrations**
   - Run `alembic upgrade head` once per environment (in a one-off task or CI job) before starting services
5) **Deploy services**
   - API service: run uvicorn command from Dockerfile
   - Worker service: run `python -m src.queue.worker` (separate task/service)
   - Scheduler (optional): `python -m src.queue.scheduler`
6) **Networking**
   - Place RDS/Redis in private subnets; allow ECS tasks security group to reach them
   - Expose API via ALB with HTTPS; allow SNS to reach `/events/sns`
7) **IAM**
   - Task role with SES send permissions; least privilege to SNS if posting; CloudWatch logs

## Production on ECS (Fargate)
- Use two task definitions (see `deploy/ecs/taskdef-api.json` and `deploy/ecs/taskdef-worker.json`): API runs uvicorn; worker runs `python -m src.queue.worker`. Each task definition uses its own Task Role (e.g., backend-role vs worker-role). Region: `ap-southeast-2`.
- Task Execution Role: only for ECR image pulls and CloudWatch Logs. Task Role: runtime permissions (SES, SNS, etc.). Do not grant app permissions to the execution role.
- Credentials: do **not** set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in ECS; rely on the Task Role so boto3 uses the default credential provider chain.
- Required env (both containers): `APP_NAME`, `ENVIRONMENT`, `API_VERSION`, `AWS_REGION_NAME=ap-southeast-2`, `DATABASE_URL` (secret), `REDIS_URL` (secret), `SES_SENDER_EMAIL` (secret/parameter). API-only extras: `ALLOWED_ORIGINS`, `RATE_LIMIT_PER_MINUTE` as needed.
- Secrets: place sensitive values in Secrets Manager or SSM Parameter Store and reference them via `secrets` entries in the task definitions (paths like `/email-delivery/DATABASE_URL` in ap-southeast-2). Non-secret config can use plain `environment` entries.
- Logging: configure awslogs per the templates, ensure the log groups exist in ap-southeast-2, and point services to them.

## Minimal IAM permissions
- Task Execution Role: ECR pull (ecr:GetAuthorizationToken, ecr:BatchCheckLayerAvailability, ecr:GetDownloadUrlForLayer, ecr:BatchGetImage), CloudWatch Logs (logs:CreateLogStream/PutLogEvents), and if using SSM/Secrets in `secrets`, allow ssm:GetParameters / secretsmanager:GetSecretValue and kms:Decrypt for the CMK used.
- backend-role (API Task Role): CloudWatch Logs write, SSM read for config (and kms:Decrypt if CMK), optional SES send if the API calls SES directly. Avoid broader permissions.
- worker-role (Worker Task Role): SES SendEmail/SendRawEmail, CloudWatch Logs write, SSM read (and kms:Decrypt if CMK). Add S3 read only if attachments/templates are stored there.
- SNS Webhooks: Configure SNS → HTTPS subscription to `https://<api-domain>/events/sns`; restrict via WAF/ALB rules and/or implement SNS signature validation.

## ECS deploy/run checklist
1) Create ECR repository and push the image tag you want to run (ap-southeast-2).
2) Create SSM Parameter Store (or Secrets Manager) entries in ap-southeast-2: `/email-delivery/DATABASE_URL`, `/email-delivery/REDIS_URL`, `/email-delivery/SES_SENDER_EMAIL` (and any others as needed).
3) Create CloudWatch log groups: `/ecs/email-delivery-api`, `/ecs/email-delivery-worker` in ap-southeast-2.
4) Register task definitions for API and worker from `deploy/ecs/taskdef-api.json` and `deploy/ecs/taskdef-worker.json` (update ARNs/placeholders first).
5) Create ECS services: API behind an HTTPS ALB target group (port 8000); worker as a separate service without ALB.
6) Wire SNS topics (delivery/bounce/complaint) to `https://<api-domain>/events/sns` and confirm the subscription.
7) Run sandbox `/send/send-test` with `enqueue=true` and verify: email received, `email_logs` updated, SNS events received/logged.

## Observability and Operations
- **Logging**: Configured via `src.utils.logger`. In ECS, ensure stdout/err ship to CloudWatch.
- **Health checks**: `/health`
- **Metrics**: Not included; add a lightweight exporter or CloudWatch EMF if needed.
- **Alarms**: Recommend alarms on 5xx rates, worker queue depth, DB connections, and RDS storage/CPU.
- **Retries/Backoff**: Add RQ retry logic as needed; current worker does simple enqueue.
- **Runbooks**:
  - Stuck jobs: check Redis queue `emails`; requeue or purge as appropriate.
  - Failed sends: inspect `EmailLog.status` and SNS events; suppress problematic emails.
  - DB migrations: always backup before running; use `alembic upgrade head`.

## Security and Hardening
- Never commit `.env` or secrets.
- Use IAM roles for ECS tasks; avoid long-lived keys.
- Enforce HTTPS via ALB/CloudFront.
- Limit CORS origins with `ALLOWED_ORIGINS`.
- Apply DB user with least privilege; separate reader vs writer if needed.
- Rotate SES/IAM keys and DB credentials regularly.
- Consider WAF rules for API protection.

## Rate Limiting
- Simple in-memory limiter for `/send/send-test` via `RateLimiter`. For production, use a distributed limiter (Redis/leaky bucket) if you expose public endpoints.

## Testing
- Unit/integration tests live in `tests/`. Current coverage includes `/send/send-test`.
- Run `pytest` locally and in CI.
- For new routes, add tests that cover happy path and failure cases (404/409/validation).
- Consider adding mocked SES/Redis fixtures for offline testing.

## Troubleshooting
- **Missing boto3/botocore**: Install deps (`pip install -r requirements.txt`).
- **204 response assertion**: Ensure delete endpoints use `response_class=Response` and return no body (already set).
- **Alembic template missing**: `alembic/script.py.mako` is included; regenerate if removed.
- **Pydantic warnings**: v2 deprecates `orm_mode`; switch to `from_attributes=True` in models to silence warnings.
- **SNS signature validation**: Not implemented; add if exposing publicly.
- **SES sandbox**: Verify both sender and recipient or request production access.

## Common Tasks
- Create tenant:
```bash
curl -X POST http://localhost:8000/tenants/ -H "Content-Type: application/json" \
  -d '{"name":"Acme","contact_email":"ops@acme.com"}'
```
- Create and send campaign immediately:
```bash
# create
curl -X POST http://localhost:8000/campaigns/ -H "Content-Type: application/json" \
  -d '{"tenant_id":1,"name":"Launch","subject":"Hello","body":"Welcome!"}'
# send
curl -X POST http://localhost:8000/campaigns/1/send-now
```
- Bulk import subscribers (CSV):
```bash
curl -X POST http://localhost:8000/subscribers/bulk-import -H "Content-Type: application/json" \
  -d '{"tenant_id":1,"csv_text":"email,first_name,last_name\nalice@example.com,Alice,\nbob@example.com,Bob,"}'
```
- Add suppression:
```bash
curl -X POST http://localhost:8000/suppression/ -H "Content-Type: application/json" \
  -d '{"tenant_id":1,"email":"bad@example.com","reason":"bounce"}'
```
- Request domain verification:
```bash
curl -X POST http://localhost:8000/domains/request-verification -H "Content-Type: application/json" \
  -d '{"tenant_id":1,"domain":"example.com"}'
```
- Handle SNS locally (example payload):
```bash
curl -X POST http://localhost:8000/events/sns -H "Content-Type: application/json" -d @sns.json
```

## Project Structure

```
src/
  api/
    app.py                # FastAPI application bootstrap
    routes/               # Modular API routers
      send.py             # /send endpoints including SES test route
      campaigns.py        # Campaign CRUD + send/schedule/preview
      subscribers.py      # Subscriber management + bulk import
      tenants.py          # Tenant CRUD
      domains.py          # Domain verification + status updates
      email_logs.py       # Email log queries
      events.py           # SES/SNS bounce/complaint webhook
      admin_tools.py      # Manual campaign triggers
      suppression.py      # Suppression list management
  core/
    config.py             # Environment-driven settings
    rate_limit.py         # Simple in-memory rate limiting helper
  db/
    models.py             # SQLAlchemy ORM models
    session.py            # Engine + SessionLocal + dependency helpers
    migrations/           # Placeholder for Alembic revisions (if used)
  queue/
    worker.py             # Redis RQ worker + enqueue helper
    scheduler.py          # rq-scheduler helper for delayed jobs
    campaign_runner.py    # Bulk campaign enqueue/run helpers
  services/
    ses.py                # AWS SES wrapper using boto3
    campaign_service.py   # Campaign validation + enqueuing helpers
    template_engine.py    # Jinja2 template renderer
    bounce_handler.py     # Stub bounce handler
  utils/
    logger.py             # Logging configuration

tests/
  test_send.py            # FastAPI route test
alembic/
  env.py                  # Alembic environment config
  versions/               # Generated migration scripts
Dockerfile
.github/workflows/docker-deploy.yml
```

## Notes
- Keep `.env` files out of version control.
- Replace placeholder AWS credentials with IAM users/roles configured for SES.
- SES sandbox accounts must verify both sender and recipient addresses.
- For production deployments ensure HTTPS, observability, retries, and more advanced rate limiting per tenant.
- Prefer distributed rate limiting and centralized logging/metrics for high traffic.
