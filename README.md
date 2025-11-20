# Email Delivery Platform Starter

Production-ready FastAPI backend scaffold for a multi-tenant email delivery platform similar to Mailchimp. It integrates FastAPI, SQLAlchemy (SQLite by default for local testing, PostgreSQL-ready for production), Alembic, Redis + RQ, AWS SES, and templated emails. The repository now also includes a Dockerfile and GitHub Actions workflow so you can containerize the service and push it to AWS without extra boilerplate.

## Features

- FastAPI application with modular routers, CORS, and startup hooks
- SQLAlchemy models + database connection handling via `DATABASE_URL` (defaults to SQLite for local dev)
- Alembic-ready migrations living under `src/db/migrations`
- AWS SES helper with reusable boto3 client
- Redis-backed queues (RQ) with worker + scheduler utilities
- Template rendering via Jinja2
- Configurations powered by environment variables / `.env`
- Example routes for sending emails, managing campaigns, subscribers, and domain verification
- Basic pytest covering the `/send/send-test` route
- Dockerfile for reproducible builds and `.github/workflows/docker-deploy.yml` for CI/CD

## Prerequisites

- Python 3.13 for local development
- Docker (for container builds) and Git
- AWS account with IAM permissions to interact with SES, ECR, ECS/Fargate (or your preferred runtime), RDS/PostgreSQL, and ElastiCache/Redis

## Local Development

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Update the copied values with your credentials:

- `DATABASE_URL=sqlite:///./data/email_delivery.db` works out of the box; point it to PostgreSQL (e.g., `postgresql+psycopg://user:pass@host:5432/db`) in shared environments.
- `REDIS_URL` for queues.
- AWS SES IAM credentials + verified sender address.

### 3. Apply migrations

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

The FastAPI app will also auto-create tables for quick experiments if migrations have not been run yet.

### 4. Run services locally

```bash
uvicorn src.api.app:app --reload
python -m src.queue.worker  # separate terminal
# optional scheduler: python -m src.queue.scheduler
```

### 5. Execute tests

```bash
pytest
```

## Container Image

The included `Dockerfile` builds a minimal image that runs `uvicorn`:

```bash
docker build -t email-delivery .
docker run --env-file .env -p 8000:8000 email-delivery
```

Notes:

- Mount `-v $(pwd)/data:/app/data` if you want SQLite data persisted on the host.
- Replace `.env` with AWS SSM/Secrets Manager or task definitions when running on ECS/Fargate/EKS.

## GitHub Actions CI/CD

`.github/workflows/docker-deploy.yml` performs the following on pushes to `main` (or via manual dispatch):

1. Installs dependencies and runs `pytest -q`.
2. Configures AWS credentials via `aws-actions/configure-aws-credentials`.
3. Logs into Amazon ECR.
4. Builds the Docker image and pushes both the commit SHA tag and `latest`.
5. Forces a new ECS deployment (optional—remove if you target another platform).

### Configure the workflow

1. Create an ECR repository (default name: `email-delivery-service`) and an ECS cluster/service (defaults live in the workflow `env` block). Update the env values if you use different names or regions.
2. Add the following repository secrets:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - (Optional) use GitHub’s OIDC + IAM role instead and remove the long-lived secrets.
3. Push to `main` or trigger the workflow manually. Your new image will be available in ECR and ECS will be told to pull the latest tag.

If you deploy to Elastic Beanstalk, Lambda, or another target replace the final ECS step with the appropriate CLI command.

## AWS Deployment Checklist

- **Database**: Provision PostgreSQL (RDS or Aurora) and set `DATABASE_URL`.
- **Caching/Queues**: Provision ElastiCache Redis and set `REDIS_URL`.
- **Secrets**: Store AWS keys, DB credentials, and other sensitive env vars in Secrets Manager or SSM Parameter Store.
- **SES**: Verify domains/senders, move the account out of the SES sandbox if needed, and create least-privilege IAM policies.
- **Networking**: Ensure ECS tasks or EC2 instances can reach RDS/Redis and SES endpoints (VPC, subnets, security groups).
- **Monitoring**: Wire logs to CloudWatch, add alarms, and configure retries/backoff on the worker if required.

## Project Structure

```
src/
  api/
    app.py                # FastAPI application bootstrap
    routes/               # Modular API routers
      send.py             # /send endpoints including SES test route
      campaigns.py        # CRUD stub for marketing campaigns
      subscribers.py      # Subscriber management
      domains.py          # Domain verification stub
  core/
    config.py             # Environment-driven settings
    rate_limit.py         # Simple in-memory rate limiting helper
  db/
    models.py             # SQLAlchemy ORM models
    session.py            # Engine + SessionLocal + dependency helpers
    migrations/           # Placeholder for Alembic revisions
  queue/
    worker.py             # Redis RQ worker + enqueue helper
    scheduler.py          # rq-scheduler helper for delayed jobs
  services/
    ses.py                # AWS SES wrapper using boto3
    template_engine.py    # Jinja2 template renderer
    bounce_handler.py     # Stub bounce handler
  utils/
    logger.py             # Logging configuration

tests/
  test_send.py            # FastAPI route test
```

## Routes Overview

- `POST /send/send-test` — send or queue a test email through SES
- `POST /campaigns/` — create a campaign draft
- `POST /subscribers/` — add a subscriber to a tenant list
- `POST /domains/verify` — get DNS instructions for domain verification
- `GET /health` — service heartbeat

## Queue Processing

`/send/send-test` can either send immediately or enqueue work by setting `"enqueue": true` in the request body. Workers read jobs from the `emails` queue and call AWS SES in the background. The scheduler helper provides a convenient way to enqueue jobs at a future timestamp.

## Notes

- Keep `.env` files out of version control.
- Replace placeholder AWS credentials with IAM users configured for SES.
- SES sandbox accounts must verify both sender and recipient addresses.
- For production deployments ensure HTTPS, observability, retries, and more advanced rate limiting per tenant.
