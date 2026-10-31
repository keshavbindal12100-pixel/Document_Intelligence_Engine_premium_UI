# Workflow Automation & Document Intelligence Engine

FastAPI backend and Vite-based QA frontend for document processing, OCR, review, and workflow automation.

## Requirements

- Python 3.12 or newer
- Node.js LTS with npm
- Windows launchers are provided; the same commands can be run manually on other platforms.

## Quick start (Windows)

1. Create `backend/.env` by copying the root `.env.example` and adjust settings if required. Keep secrets local; do not commit `.env`.
2. Run `run_backend.bat`. On first run it creates `.venv`, installs the Python dependencies and starts FastAPI on `127.0.0.1:8000`.
3. In a second terminal, run `run_frontend.bat`. On first run it installs the locked npm dependencies and starts Vite on port `3000`.
4. Open **http://localhost:3000/** for the integrated DocFlow interface, **http://localhost:3000/app.html#/login** as its direct-entry alias, or **http://localhost:3000/qa.html** for the preserved QA dashboard. Keep both terminal windows open.

`start_all.bat` launches both windows. If port 3000 or 8000 is already in use, stop the other process first. The backend readiness endpoint is `http://127.0.0.1:8000/ready`; API docs are at `http://127.0.0.1:8000/docs`.

## API connection behavior

Both frontends use the same Vite proxies for `/api`, `/health`, and `/ready` to `http://127.0.0.1:8000`, avoiding browser CORS and `localhost`/`127.0.0.1` mismatches. The React app uses `VITE_BACKEND_URL` when set; the legacy dashboard also supports entering a full backend base URL in its API field. The frontend must be served by Vite for the development proxy; a plain static HTTP server does not proxy API requests.

The integrated React UI at `/` (also available at `/app.html`) uses the same Vite proxies and the current backend's authentication, workspace, document, workflow, metrics, and audit APIs. Sign-in and account registration require a reachable configured backend. It does not use the reference repository's simulated OCR, local-only records, or mock sign-in actions. The original QA dashboard code is preserved byte-for-byte at `/qa.html`, including its E2E and Workbench behavior.

## Run tests

From the project root:

```bash
python -m pytest -q
ruff check .
ruff format --check .
```

Frontend validation:

```bash
cd frontend
npm ci
npm run build
```

The multi-page production build emits `index.html` and `app.html` for the React interface plus `qa.html` for the legacy dashboard. See [QA_TEST_REPORT.md](QA_TEST_REPORT.md) for the existing baseline verification summary.
