const API_BASE = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/+$/, '');
const ACCESS_KEY = 'docflow_access_token';
const REFRESH_KEY = 'docflow_refresh_token';
const USER_KEY = 'docflow_user';
const WORKSPACE_KEY = 'docflow_workspace_id';

export const authStorage = {
  get accessToken() { return localStorage.getItem(ACCESS_KEY) || ''; },
  get refreshToken() { return localStorage.getItem(REFRESH_KEY) || ''; },
  get user() {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); }
    catch { return null; }
  },
  get workspaceId() { return localStorage.getItem(WORKSPACE_KEY) || ''; },
};

export function clearAuth() {
  for (const key of [ACCESS_KEY, REFRESH_KEY, USER_KEY, WORKSPACE_KEY]) localStorage.removeItem(key);
}

function storeTokens(data) {
  if (data?.access_token) localStorage.setItem(ACCESS_KEY, data.access_token);
  if (data?.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
}

function apiUrl(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

async function refreshAccessToken() {
  const refreshToken = authStorage.refreshToken;
  if (!refreshToken) return false;
  try {
    const response = await fetch(apiUrl('/api/v1/auth/refresh'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) return false;
    storeTokens(await response.json());
    return Boolean(authStorage.accessToken);
  } catch {
    return false;
  }
}

export async function apiRequest(path, options = {}, allowRefresh = true) {
  const { body, headers: suppliedHeaders = {}, ...rest } = options;
  const headers = new Headers(suppliedHeaders);
  const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
  if (!isForm && body !== undefined && body !== null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  headers.set('Accept', 'application/json');
  if (authStorage.accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authStorage.accessToken}`);
  }
  if (authStorage.workspaceId && !path.startsWith('/api/v1/auth/')) {
    headers.set('X-Workspace-Id', authStorage.workspaceId);
  }

  let response;
  try {
    response = await fetch(apiUrl(path), {
      ...rest,
      headers,
      body: body === undefined || body === null || isForm || typeof body === 'string' ? body : JSON.stringify(body),
    });
  } catch (error) {
    throw new Error(`Could not reach the backend. Check the API server and Vite proxy. ${error.message}`);
  }

  const authActionDoesNotRefresh = ['/api/v1/auth/login', '/api/v1/auth/register', '/api/v1/auth/guest-token', '/api/v1/auth/refresh'].some((route) => path.startsWith(route));
  if (response.status === 401 && allowRefresh && !authActionDoesNotRefresh && await refreshAccessToken()) {
    return apiRequest(path, options, false);
  }

  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : await response.text().catch(() => '');
  if (!response.ok) {
    const detail = payload?.detail || payload?.message || (typeof payload === 'string' ? payload : '');
    throw new Error(detail ? `${response.status}: ${detail}` : `Request failed (${response.status}).`);
  }
  return payload;
}

export async function signIn(email, password) {
  const tokens = await apiRequest('/api/v1/auth/login', { method: 'POST', body: { email, password } }, false);
  storeTokens(tokens);
  const user = await apiRequest('/api/v1/auth/me');
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  await loadWorkspace();
  return user;
}

export async function signUp({ name, email, password }) {
  await apiRequest('/api/v1/auth/register', {
    method: 'POST',
    body: { full_name: name, email, password },
  }, false);
  return signIn(email, password);
}

export async function loadWorkspace() {
  try {
    const workspaces = await apiRequest('/api/v1/workspaces');
    const currentId = authStorage.workspaceId;
    const workspace = Array.isArray(workspaces)
      ? (workspaces.find((item) => item.id === currentId) || workspaces[0])
      : null;
    if (workspace?.id) localStorage.setItem(WORKSPACE_KEY, workspace.id);
    return workspace || null;
  } catch {
    // The backend resolves a user's default workspace when the header is omitted.
    return null;
  }
}

export async function restoreSession() {
  if (!authStorage.accessToken) return null;
  try {
    const user = await apiRequest('/api/v1/auth/me');
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    await loadWorkspace();
    return user;
  } catch {
    clearAuth();
    return null;
  }
}

export function backendHealthUrl() {
  return apiUrl('/health');
}

export function normalizeDocument(doc) {
  const rawStatus = String(doc.status || '').toLowerCase();
  const statusMap = {
    uploaded: 'Pending', queued: 'Pending', processing: 'Processing',
    completed: 'Approved', review_required: 'Pending', rejected: 'Rejected', failed: 'Failed',
  };
  const rawType = String(doc.document_type || 'UNKNOWN');
  const typeMap = {
    INVOICE: 'Invoice', RECEIPT: 'Receipt', PURCHASE_ORDER: 'Purchase Order',
    FORM: 'Form', CONTRACT: 'Contract', ID_CARD: 'ID Card', CUSTOM: 'Custom', UNKNOWN: 'Unknown',
  };
  return {
    ...doc,
    fileName: doc.original_filename || doc.filename || doc.file_name || 'Untitled document',
    fileSize: Number(doc.file_size_bytes ?? doc.file_size ?? 0),
    fileType: doc.mime_type || 'Unknown',
    docType: typeMap[rawType] || rawType,
    status: statusMap[rawStatus] || rawStatus || 'Unknown',
    confidence: Number(doc.ocr_confidence ?? doc.confidence_score ?? 0),
    uploadedAt: doc.created_at || doc.updated_at || null,
    createdAt: doc.created_at || null,
    updatedAt: doc.updated_at || null,
  };
}


export async function downloadApiFile(path, fallbackName = 'download') {
  const headers = new Headers();
  if (authStorage.accessToken) headers.set('Authorization', `Bearer ${authStorage.accessToken}`);
  if (authStorage.workspaceId && !path.startsWith('/api/v1/auth/')) {
    headers.set('X-Workspace-Id', authStorage.workspaceId);
  }

  let response;
  try {
    response = await fetch(apiUrl(path), { headers });
  } catch (error) {
    throw new Error(`Could not reach the backend. Check the API server and Vite proxy. ${error.message}`);
  }

  if (response.status === 401 && await refreshAccessToken()) {
    headers.set('Authorization', `Bearer ${authStorage.accessToken}`);
    response = await fetch(apiUrl(path), { headers });
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || payload?.message || `Download failed (${response.status}).`);
  }

  const disposition = response.headers.get('content-disposition') || '';
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const quotedName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  let filename = encodedName ? decodeURIComponent(encodedName) : (quotedName || fallbackName);
  filename = filename.replace(/[\\/\r\n]/g, '_') || fallbackName;
  return { blob: await response.blob(), filename };
}
