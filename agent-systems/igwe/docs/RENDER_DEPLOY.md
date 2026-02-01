# Deploying IUL Appointment Setter (igwe) on Render

Run the full system on Render: **FastAPI** (web), **Celery worker + beat** (background worker), and **Redis** (add-on or external). Same codebase; you monitor from the Render dashboard and your app dashboard.

## Architecture on Render

| Component   | How it runs |
|------------|--------------|
| **FastAPI** | Web Service (`RUN_MODE=web`) — dashboard, webhooks, API |
| **Celery**  | Background Worker (`RUN_MODE=worker`) — worker + beat in one process |
| **Redis**   | Render Redis add-on or external (e.g. Upstash) — set `REDIS_URL` |
| **Database**| Render Postgres or external — set `DATABASE_URL` |

## 1. Redis

- **Option A:** In Render Dashboard → Add **Redis** (if available). Attach it to your web and worker services so they get `REDIS_URL`.
- **Option B:** Use [Upstash Redis](https://upstash.com/) (or similar). Create a Redis instance, copy the URL, and in Render set **Environment** → `REDIS_URL` = `redis://...` (or `rediss://...` for TLS).

The app **does not** start a local Redis process when `REDIS_URL` points to a non-localhost host; it only connects.

## 2. Database

- Use **Render Postgres** (or any Postgres). Create a database and set **Environment** → `DATABASE_URL` (Render often sets this automatically when you attach Postgres).
- Tables (including `suppressions`) are created on first run via `Base.metadata.create_all`.

## 3. Create two services (or use Blueprint)

### Web Service (FastAPI)

- **Type:** Web Service  
- **Build Command:** `pip install -r requirements.txt`  
- **Start Command:** `python main.py`  
- **Environment:**
  - `RUN_MODE` = `web`
  - `PORT` — leave unset; Render sets it
  - `PYTHONPATH` = `.` (if needed)
  - `REDIS_URL` — from Redis add-on or manual
  - `DATABASE_URL` — from Postgres or manual
  - Plus: `SENDGRID_API_KEY`, `CALENDLY_API_KEY`, `APIFY_API_TOKEN`, etc., as in your local `.env`

### Background Worker (Celery)

- **Type:** Background Worker  
- **Build Command:** `pip install -r requirements.txt`  
- **Start Command:** `python main.py`  
- **Environment:**
  - `RUN_MODE` = `worker`
  - `PYTHONPATH` = `.`
  - Same `REDIS_URL` and `DATABASE_URL` as the web service
  - Same API keys / env vars the tasks need (SendGrid, Calendly, Apify, etc.)

If your repo root is the parent of `agent-systems/igwe`, set **Root Directory** for both services to `agent-systems/igwe`.

## 4. Optional: Blueprint

The repo includes `render.yaml` in this directory. In Render you can:

- Create a **Blueprint** and point it at this repo, then set **Root Directory** to `agent-systems/igwe` so the two services (web + worker) are created from the YAML; then attach Redis and Postgres and add env vars in the Dashboard, **or**
- Create the **Web Service** and **Background Worker** manually and use the same build/start commands and env vars above.

## 5. SendGrid webhook

Point SendGrid Event Webhook URL to your Render web service, e.g.:

`https://<your-render-web-service>.onrender.com/webhooks/sendgrid`

Then delivery/open/bounce events will hit the same app and DB that send the emails.

## 6. Verify

- **Web:** Open `https://<your-app>.onrender.com/dashboard/` — you should see the dashboard.
- **Worker:** In Render → Logs for the worker service — you should see Celery worker and beat starting and tasks running.
- **Redis:** If Redis is unreachable, the app logs an error and exits; fix `REDIS_URL` and redeploy.

You can run the entire system (FastAPI, Celery, Redis, DB) on Render and monitor from the Render dashboard and your app dashboard; no need to run Redis or the app on your laptop for production.