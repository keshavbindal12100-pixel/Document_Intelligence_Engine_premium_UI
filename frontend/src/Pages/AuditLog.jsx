import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FileClock, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { apiRequest } from '../api/client.js';

const date = (value) => value ? new Date(value).toLocaleString() : '—';
const pretty = (value) => String(value || 'EVENT').replaceAll('_', ' ').replace(/\b\w/g, (m) => m.toUpperCase());

export default function AuditLog() {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const result = await apiRequest('/api/v1/audit?page=1&page_size=50');
      setEntries(result?.items || []); setTotal(result?.total || 0);
    } catch (err) { setError(err.message); setEntries([]); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return entries.filter((entry) => !term || `${entry.action} ${entry.entity_type} ${entry.document_id || entry.entity_id} ${entry.user_id}`.toLowerCase().includes(term));
  }, [entries, search]);

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-medium text-blue-600">Traceability</p><h1 className="mt-1 text-2xl font-bold text-slate-900">Audit logs</h1><p className="mt-1 text-sm text-slate-500">Immutable activity records returned for the active workspace.</p></div><button onClick={load} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh</button></div>
    {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4"><div className="relative min-w-[240px] flex-1"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search action, document, or user…" className="w-full rounded-lg border border-slate-200 py-2.5 pl-10 pr-3 text-sm outline-none focus:border-blue-500" /></div><span className="text-xs text-slate-500">{total} total event{total === 1 ? '' : 's'} · showing up to 50</span></div>
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">{loading ? <div className="p-12 text-center text-sm text-slate-500">Loading audit records…</div> : filtered.length ? <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-400"><tr><th className="px-5 py-3">Action</th><th className="px-5 py-3">Entity</th><th className="px-5 py-3">Document / entity ID</th><th className="px-5 py-3">Actor</th><th className="px-5 py-3">Timestamp</th></tr></thead><tbody>{filtered.map((entry) => <tr key={entry.id} className="border-t border-slate-100"><td className="px-5 py-4"><span className="inline-flex items-center gap-2 font-semibold text-slate-700"><ShieldCheck className="h-4 w-4 text-emerald-600" />{pretty(entry.action)}</span><p className="mt-1 max-w-56 truncate font-mono text-[10px] text-slate-400">{entry.id}</p></td><td className="px-5 py-4 text-slate-600">{pretty(entry.entity_type)}</td><td className="max-w-56 truncate px-5 py-4 font-mono text-xs text-slate-500" title={entry.document_id || entry.entity_id}>{entry.document_id || entry.entity_id || '—'}</td><td className="max-w-48 truncate px-5 py-4 text-xs text-slate-500">{entry.user_id || 'System'}</td><td className="whitespace-nowrap px-5 py-4 text-xs text-slate-500">{date(entry.created_at)}</td></tr>)}</tbody></table></div> : <div className="p-12 text-center"><FileClock className="mx-auto h-9 w-9 text-slate-300" /><h2 className="mt-3 font-semibold text-slate-700">{entries.length ? 'No matching audit entries' : 'No audit activity yet'}</h2><p className="mt-1 text-sm text-slate-500">Activity appears here after operations are performed through the backend.</p></div>}</div>
    {filtered.some((item) => item.details || item.changes) && <details className="rounded-xl border border-slate-200 bg-white p-4"><summary className="cursor-pointer text-sm font-semibold text-slate-700">Show event details</summary><pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-slate-200">{JSON.stringify(filtered.filter((item) => item.details || item.changes).map((item) => ({ id: item.id, action: item.action, details: item.details || item.changes })), null, 2)}</pre></details>}
  </div>;
}
