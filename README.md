# auto-youtube-screenshot

FastAPI backend + React (MUI, Vite) frontend + Postgres 16, run with Docker Compose.

## Development

```sh
docker compose -f docker-compose.dev.yml up --build
```

| Service  | URL                              | Hot reload                   |
|----------|----------------------------------|------------------------------|
| Frontend | http://localhost:5174            | Vite HMR on `frontend/src`   |
| Backend  | http://localhost:8001/docs       | `uvicorn --reload` on `backend/app` |
| Postgres | `localhost:5433` (user/pass/db: `app`) | —                      |

The frontend proxies `/api/*` to the backend, so call `fetch('/api/...')` from React.

Host ports can be overridden: `BACKEND_HOST_PORT`, `FRONTEND_HOST_PORT`, `POSTGRES_HOST_PORT`.

After changing `requirements.txt` or `package.json`, rebuild that service:

```sh
docker compose -f docker-compose.dev.yml up --build -d backend   # or frontend
```
