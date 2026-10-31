# QA Test Report

**Project:** Workflow Automation & Document Intelligence Engine  
**Last tested:** 2026-10-12  
**Result:** **PASS**

## Verification performed

| Check | Result |
|---|---:|
| Backend unit, API, and integration tests | **56 passed** |
| Bundled document pipeline E2E (auth, workspace, upload, process, extraction, approval, workflow, audit) | **PASS** |
| Bundled workflow automation lifecycle E2E (triggered workflows, approval, audit) | **PASS** |
| Ruff lint (`ruff check .`) | **PASS** |
| Ruff formatting (`ruff format --check .`) | **PASS** |
| Clean frontend dependency install (`npm ci`) | **PASS** |
| Frontend production build (`npm run build`) | **PASS** — emits `index.html`, `app.html`, and `qa.html` |
| Full npm dependency audit (`npm audit --audit-level=moderate`) | **PASS** — 0 vulnerabilities |
| Backend `/health` and `/ready` | **PASS** — HTTP 200 |
| Vite API proxy for `/health` and `/ready` | **PASS** — HTTP 200 |
| Frontend root, `/app.html`, and `/qa.html` | **PASS** — HTTP 200 |
| Production preview via sandbox browser | **PASS** — rendered login screen after host-allowlist fix |
| Windows batch launchers | **Static inspection only** — Windows execution unavailable in Sandbox |

Backend E2E checks used a temporary SQLite database and temporary storage directory under `/tmp`; no user database or uploaded project documents were used. The test accounts and uploaded sample invoices were temporary and isolated from the packaged project data.

## Issues found and fixed

### Dependency security advisories

The initial dependency audit identified vulnerable React Router releases, Vite/esbuild tooling, and Tailwind CSS 3 transitive dependencies. The frontend has been updated to React Router DOM **7.18.4**, Vite **6.4.4**, Tailwind CSS **4.3.3**, and `@tailwindcss/postcss` **4.3.3**. Tailwind's PostCSS integration and CSS entry directives were migrated, then a clean install, production build, and full audit were run successfully. The final audit reports **0 vulnerabilities**.

### Sandbox preview host rejected

The production preview initially rejected the current sandbox hostname because the Vite host allowlist contained only stale hostnames from earlier runs. The dev and preview allowlists now permit the sandbox's `sg2.manus.computer` host suffix; the served page was rechecked in the browser and rendered successfully.

### Earlier backend and API/frontend fixes

- Fixed the missing `UserWorkspace` model import in `UserRepository.get_with_workspaces`; the eager-loaded membership regression test passes.
- Kept frontend API traffic on the Vite proxy to prevent `localhost`/`127.0.0.1` mismatches and browser-side CORS issues.
- Removed the misleading Python static-server fallback from the frontend launcher; Vite/npm is required for API proxy behavior.
- The backend launcher validates Python 3.12+ and checks its virtual-environment interpreter before installing dependencies.
- Fixed the pytest storage fixture: it now redirects the imported storage singleton to a per-test temporary directory and restores it afterward. A full-suite rerun confirmed that all 11 supplied storage files remain byte-for-byte unchanged.

## Packaging notes

- No `.env`, local database, Python virtual environment, `node_modules`, or build output is included in the final ZIP.
- The `storage_data/` PDFs were already present in the supplied ZIP and are preserved unchanged; tests used separate temporary storage.
- The source QA dashboard (`frontend/qa.html`) remains byte-identical to the supplied project file.

## Environment limitations

Windows batch files were not executable in the Linux Sandbox. The backend end-to-end tests exercised the document and workflow flows against the isolated local backend, but did not use production OCR credentials or a real Redis worker. The React sign-in screen was rendered, and authentication was exercised through temporary test-only accounts by the local E2E scripts; no real user account was used.
