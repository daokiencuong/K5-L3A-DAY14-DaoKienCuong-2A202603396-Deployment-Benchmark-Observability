# Day 14 — Deployment Information

> Deploy target: Part 6 production agent in `06-lab-complete/`. Do not record API keys, credential-bearing Redis URLs, or platform tokens here.

## Deployment status

- Platform: Railway (planned)
- Public URL: pending authenticated Railway session and deployment
- Cloud Redis: pending Railway project setup
- Last cloud validation: not run
- Local production readiness: `PASS 12/12` criteria, `41/41` checks; details in `MISSION_ANSWERS.md`

Railway CLI 5.75.0 is installed. The current Windows session is not authenticated (`railway whoami` did not succeed), so no cloud service or public URL has been created yet.

## Required environment variables

Configure these in the cloud platform. Record names only, never values.

- `AGENT_API_KEY` — generated/set as a platform secret
- `REDIS_URL` — internal connection URL for the hosted Redis service
- `RATE_LIMIT_PER_MINUTE` — `10`
- `DAILY_BUDGET_USD` — `10.0`
- `ENVIRONMENT` — `production`
- `PORT` — supplied by the platform or defaulted by the container

The Render Blueprint alternative is `06-lab-complete/render.yaml`; it creates a web service and Key Value Redis, and wires the Redis connection and generated API key. For a repository-root Blueprint, select that file and retain `rootDir: 06-lab-complete`.

## Smoke checks

After deployment, set `BASE` to the public service URL and `AGENT_API_KEY` in the local shell without printing either value. Expected status codes:

| Check | Expected | Actual |
|---|---:|---:|
| `GET /health` | 200 | Pending deployment |
| `GET /ready` | 200 | Pending hosted Redis |
| `POST /ask` without API key | 401 | Pending deployment |
| `POST /ask` with valid API key | 200 | Pending deployment |

PowerShell checks that print only HTTP status codes:

```powershell
curl.exe -sS -o NUL -w "%{http_code}\n" "$env:BASE/health"
curl.exe -sS -o NUL -w "%{http_code}\n" "$env:BASE/ready"
curl.exe -sS -o NUL -w "%{http_code}\n" -X POST "$env:BASE/ask" -H "Content-Type: application/json" -d '{"question":"Hello"}'
curl.exe -sS -o NUL -w "%{http_code}\n" -X POST "$env:BASE/ask" -H "Content-Type: application/json" -H "X-API-Key: $env:AGENT_API_KEY" -d '{"question":"Hello"}'
```

Expected output sequence: `200`, `200`, `401`, `200`.

## Screenshots

Capture these after deployment, with all secret values hidden:

- `screenshots/dashboard.png` — cloud project/service dashboard
- `screenshots/running.png` — successful deployment and running service
- `screenshots/test.png` — four smoke-check status codes
