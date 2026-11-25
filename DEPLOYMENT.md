# Day 14 — Deployment Information

> Deploy target: Part 6 production agent in `06-lab-complete/`. Do not record API keys, credential-bearing Redis URLs, or platform tokens here.

## Deployment status

- Platform: Render — Blueprint `06-lab-complete/render.yaml` (web service `day14-agent` + Key Value `day14-redis`, region Singapore)
- Public URL: https://day14-agent-179v.onrender.com
- Cloud Redis: Render Key Value service, wired through `REDIS_URL` by the Blueprint
- Last cloud validation: 2026-11-25 — `/health` 200, `/ready` 200, `POST /ask` without key 401, with key 200
- Local production readiness: `PASS 12/12` criteria, `44/44` checks (Ubuntu 24.04 + Docker, including public URL check); details in `MISSION_ANSWERS.md`

## Required environment variables

Configure these in the cloud platform. Record names only, never values.

- `AGENT_API_KEY` — generated/set as a platform secret
- `REDIS_URL` — internal connection URL for the hosted Redis service
- `RATE_LIMIT_PER_MINUTE` — `10`
- `DAILY_BUDGET_USD` — `10.0`
- `ENVIRONMENT` — `production`
- `PORT` — supplied by the platform or defaulted by the container

Render is the deployed platform. The Blueprint `06-lab-complete/render.yaml` creates the web service `day14-agent` and the Key Value service `day14-redis`, wires `REDIS_URL`, and generates `AGENT_API_KEY`. When creating the Blueprint from the repository root, use `06-lab-complete/render.yaml` and keep `rootDir: 06-lab-complete`.

## Smoke checks

After deployment, set `BASE` to the public service URL and `AGENT_API_KEY` in the local shell without printing either value. Expected status codes:

| Check | Expected | Actual |
|---|---:|---:|
| `GET /health` | 200 | 200 |
| `GET /ready` | 200 | 200 |
| `POST /ask` without API key | 401 | 401 |
| `POST /ask` with valid API key | 200 | 200 |

PowerShell checks that print only HTTP status codes (write the JSON body to a file first: PowerShell 5.1 strips the quotes if `-d '{"question":"Hello"}'` is passed directly, which produces a false 422):

```powershell
$body = Join-Path $env:TEMP "ask.json"
'{"question":"Hello"}' | Set-Content -Path $body -Encoding utf8

curl.exe -sS -o NUL -w "%{http_code}`n" "$env:BASE/health"
curl.exe -sS -o NUL -w "%{http_code}`n" "$env:BASE/ready"
curl.exe -sS -o NUL -w "%{http_code}`n" -X POST "$env:BASE/ask" -H "Content-Type: application/json" --data-binary "@$body"
curl.exe -sS -o NUL -w "%{http_code}`n" -X POST "$env:BASE/ask" -H "Content-Type: application/json" -H "X-API-Key: $env:AGENT_API_KEY" --data-binary "@$body"
```

Expected output sequence: `200`, `200`, `401`, `200`.

## Screenshots

Included in `screenshots/`, with all secret values hidden:

- `screenshots/dashboard.png` — Render workspace: `day14-agent` **Deployed** (Docker, Singapore) and `day14-redis` **Available**
- `screenshots/running.png` — service page: **Live**, Blueprint managed, public URL visible
- `screenshots/test.png` — four smoke checks: `/health` 200, `/ready` 200, `/ask` without key 401, `/ask` with key 200 (API key value hidden)
