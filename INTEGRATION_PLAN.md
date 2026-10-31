# Frontend Integration Plan

## Scope and inspection findings

- The supplied project is a FastAPI backend plus a Vite 5 frontend. Its original `frontend/index.html` was a single QA dashboard with an API client embedded in its script, an 8-stage E2E runner, document workbench, workflows, analytics, audit views, and backend health checks; that file is now preserved byte-for-byte at `frontend/qa.html`.
- The GitHub reference frontend uses React Router and Tailwind-style UI. Its login/signup actions, OCR extraction, document data, analytics, workflow creation, and audit records are mostly simulated with `localStorage`, fixed IDs, timers, and fabricated data. The live reference currently exposes its sign-in/sign-up screen.
- The supplied ZIP is the only project checkout in the workspace. This integration will be applied to a separate extracted working copy; the source ZIP remains untouched.

## Integration plan

### Reference files/components to reuse or adapt

- Reuse/adapt the DocFlow login visual treatment, navigation shell, and page layouts from `Frontend/src/auth/Login.jsx`, `Frontend/src/Pages/DashboardLayout.jsx`, and the reference page components.
- Add the React app as the default `frontend/index.html` entry, keep `frontend/app.html` as a direct-entry alias, and provide route-based screens for Dashboard, Documents, Upload/Review, Workflows, Analytics, and Audit Logs.
- Port only required logo/style assets and component structure. Rework the data and actions to use the existing FastAPI backend rather than importing local-only demo behavior.

### Existing project files to modify

- `frontend/vite.config.js`: add the React plugin and include `index.html`, `app.html`, and `qa.html` in production build inputs; retain existing host, port, and backend proxy configuration.
- `frontend/package.json` and `frontend/package-lock.json`: add React, React Router, Lucide icons, chart support, Tailwind 3, and its PostCSS dependencies while retaining Vite 5 compatibility.
- `README.md` and `run_frontend.bat`: document DocFlow at `/`, the `/app.html#/login` alias, and the legacy QA dashboard at `/qa.html`.
- Add `frontend/app.html`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, and React files under `frontend/src/` (API client, router, shared layout/auth, and feature pages).
- Preserve the original QA dashboard content byte-for-byte as `frontend/qa.html`; make the integrated DocFlow app the new root `frontend/index.html`. No backend edits are planned.

### Dependencies to add

- Runtime: React, React DOM, React Router DOM, Lucide React, and Recharts.
- Build/style: `@vitejs/plugin-react` compatible with Vite 5, Tailwind CSS 3, PostCSS, and Autoprefixer.
- Do not copy the reference's newer Vite 8 / Tailwind 4 toolchain or add Framer Motion/jsPDF solely to preserve demo animations/exports; use the backend's existing export endpoints where available.

### API and component connections

- Authentication: `/api/v1/auth/register`, `/login`, `/refresh`, and `/me`; persist actual access/refresh tokens and clear them on logout.
- Workspace: `/api/v1/workspaces`; resolve the signed-in user's workspace dynamically and send it through `X-Workspace-Id`.
- Dashboard/analytics: `/api/v1/dashboard/metrics` and `/queue`.
- Documents: `/api/v1/documents` list/upload/upload-any, `/{id}`, `/{id}/process`, `/{id}/reprocess`, `/{id}/extraction`, `/{id}/approve`, `/{id}/reject`, `/{id}/audit`, and ERP/PDF exports.
- Workflows: `/api/v1/workflows` list/create/update/delete and execution actions as supported.
- Audit: `/api/v1/audit` list and per-document audit trail.
- Add a shared fetch client for bearer auth, workspace headers, JSON/multipart requests, API errors, and token refresh; preserve the legacy dashboard's independent existing API behavior.

### Potential conflicts and resolutions

- **Single-page root entry:** preserve the original dashboard content at `/qa.html`, make the integrated React app the root homepage, and keep `/app.html#/login` as a direct-entry alias.
- **UI/API data mismatch:** map FastAPI document fields and status enums into view models at the client boundary; do not keep fake localStorage documents as a second source of truth.
- **Fake actions in reference:** replace sample timers/workflows/audit logs with real API calls, remove hard-coded workspace/user IDs, and do not present Google login as functional without an OAuth backend.
- **Dependency/version conflict:** keep the existing Vite 5 and Node 18+ startup baseline; use the compatible React plugin and Tailwind 3 toolchain rather than upgrading the stack to match the reference repository's Vite 8 setup.

## Validation

1. Run `npm ci` and `npm run build` in `frontend`.
2. Run the existing Python test suite and lint/format checks if the environment supports the project's Python version and dependencies.
3. Smoke-test the Vite DocFlow homepage, `/app.html` alias, and preserved `/qa.html` dashboard, including asset loading and SPA hash routes.
4. Verify backend proxy/health behavior and exercise authentication, workspace lookup, document list/upload path, workflow list, metrics, and audit requests where the local backend can be started.
5. Keep remaining limitations explicit in the final report (for example, no OAuth provider configured, and backend processing services may need local credentials/services).

## Implemented-scope note

The delivered React UI includes document list/upload/process/extraction display/approve/reject/delete, workflow list/create/toggle/delete/run, metrics, and audit history. It does not yet expose inline correction editing, reprocess controls, or PDF/ERP download buttons; those were left out rather than introducing controls without verifying the backend response/download contracts. The legacy dashboard code is preserved byte-for-byte at `/qa.html`, and the backend APIs themselves were not modified.
