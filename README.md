# CRT Lab — Choice Reaction Time Web Application

A complete web application for running Deary–Liewald-style choice reaction time
(CRT) experiments: researchers configure studies, enroll participants, and
monitor results on a statistics dashboard; participants run precisely-timed
2/3/4-choice reaction time sessions in the browser.

Built to the specification in [02_PRD.md](02_PRD.md).

## Stack

- **Backend** — Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, PostgreSQL 16 (SQLite fallback for no-Docker dev/tests)
- **Frontend** — React 18, TypeScript 5 (strict), Vite 5, Tailwind CSS, Recharts
- **Serving** — nginx serves the built SPA and proxies `/api/` to the backend; the frontend only ever calls the relative path `/api/v1`, so there is no CORS and the same images work on localhost, a tunnel, or a public domain
- **Orchestration** — Docker Compose (`db`, `api`, `web`)

## Quick start

```bash
cp .env.example .env
# edit .env: set SECRET_KEY (>=32 random bytes), ADMIN_EMAIL, ADMIN_PASSWORD
docker compose up --build
```

The app is at **http://localhost:8080** (configurable via `WEB_PORT`). On
first boot the API runs migrations and seeds a single admin account from
`ADMIN_EMAIL`/`ADMIN_PASSWORD`.

Verify the stack end to end:

```bash
python3 scripts/smoke.py          # exits 0 on success
```

## Using the app

1. **Log in** at `/login` → *Researcher* tab with the admin credentials.
2. **Create a study** (`/studies`): name, task type (2/3/4-CRT). All task
   parameters (§5.4 of the PRD) are editable on the study's *Settings* tab
   until the first session starts, after which they are locked (each session
   keeps its own immutable parameter snapshot).
3. **Demographics** tab: define optional demographic fields (text / number /
   single choice / yes-no, asked once or every session).
4. **Participants** tab: bulk-generate participant codes (e.g. `PILOT-A7F3`)
   or enter custom codes; download the code list as CSV.
5. **Sessions** tab: assign 1–50 sessions to selected participants, with
   optional per-assignment task type/parameter overrides.
6. Give each participant the app URL and their code. On first login they set
   their own password (min 6 chars).
7. Participants see `/me` and run sessions strictly in order; the task runs
   fullscreen with rAF-locked stimulus timing, trial batching, and automatic
   resume after a refresh or dropped connection.
8. Monitor the **Dashboard** tab: study header, filterable sessions table,
   and five charts (RT histogram, per-participant trimmed mean RT, IIV-within
   by session, session-mean RT across order, accuracy) — every table/chart has
   a *Download CSV* button. Trial-level CSV exports are available per session,
   per participant, and as a whole-study ZIP.
9. **Preview task** on the study header runs the exact task client (blocks
   capped at 3 trials) without creating any data.

## Development

### Hot-reload dev stack

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# Vite dev server: http://localhost:5173 (proxies /api to the api container)
```

### Without Docker

```bash
# backend (SQLite fallback, no DATABASE_URL needed)
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
SECRET_KEY=dev-secret-key-of-at-least-32-bytes!! ADMIN_EMAIL=admin@example.com \
  ADMIN_PASSWORD=change-me-now-please uvicorn app.main:app --reload

# frontend
cd frontend
npm install
npm run dev        # proxies /api to http://localhost:8000
```

### Tests & checks

```bash
cd backend && source .venv/bin/activate
python -m pytest               # 75 tests (auth, studies, sessions, runtime, statistics, exports)
python -m mypy app tests       # strict, clean

cd frontend
npm test                       # 26 vitest tests (trial engine, sequencing, block runner)
npm run typecheck              # tsc --noEmit, strict, clean
npm run build                  # tsc -b && vite build
```

## Deployment phases (PRD §9)

1. **Local** — `docker compose up`, as above.
2. **Lab testing via tunnel** — run the same stack on one machine and expose
   it with Tailscale (`tailscale serve --bg 8080`) or ngrok (`ngrok http 8080`).
   Nothing changes: cookies are host-relative and the API path is relative.
3. **Public hosting** — deploy the same two images plus managed Postgres to
   Railway/Render/Fly.io. Set `APP_ENV=production`, a real `SECRET_KEY`,
   the managed `DATABASE_URL`, and a strong `ADMIN_PASSWORD`. Migrations run
   automatically on API start.

## Environment variables

All variables are documented inline in [.env.example](.env.example):
`DATABASE_URL`, `SECRET_KEY`, `APP_ENV`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
`REFRESH_TOKEN_EXPIRE_DAYS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`,
`ALLOWED_ORIGINS`, `WEB_PORT`, `POSTGRES_USER/PASSWORD/DB`.

## Repository layout

```
backend/    FastAPI app, SQLAlchemy models, Alembic migrations, pytest suite
frontend/   React SPA: task runner, researcher UI, vitest suite, nginx config
scripts/    smoke.py end-to-end test
02_PRD.md   the product requirements document this implements
DECISIONS_TAKEN.md   small implementation decisions made where the PRD was silent
ACCEPTANCE.md        PRD §10 acceptance-criteria walkthrough with evidence
```

## Documentation for researchers

- Participant codes are globally unique and case-insensitive; anyone holding
  an unclaimed code can claim it by setting a password (PRD D-3), mitigated by
  login rate limiting and researcher-initiated password resets.
- Sessions must be completed strictly in order (D-4).
- A session idle for 30 minutes while in progress is marked *abandoned*;
  reset it from the Sessions tab to let the participant retry (data from
  prior attempts is kept, tagged with its attempt number).
- Concurrent tabs on one session are not actively prevented; idempotent
  trial upserts bound the damage (D-13).
- Participants never see their results (D-12).
