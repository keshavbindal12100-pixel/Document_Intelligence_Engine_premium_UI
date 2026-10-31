import React, { useCallback, useEffect, useState } from 'react';
import { Activity, CheckCircle2, Clock3, FileText, Gauge, Layers3, RefreshCw, XCircle } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { apiRequest } from '../api/client.js';

const COLORS = ['#2563eb', '#0ea5e9', '#6366f1', '#10b981', '#f59e0b', '#64748b'];
const pretty = (value) => String(value || '').replaceAll('_', ' ').replace(/\b\w/g, (m) => m.toUpperCase());

export default function Analytics() {
  const [metrics, setMetrics] = useState(null);
  const [queue, setQueue] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [updated, setUpdated] = useState(null);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [nextMetrics, nextQueue] = await Promise.all([apiRequest('/api/v1/dashboard/metrics'), apiRequest('/api/v1/dashboard/queue')]);
      setMetrics(nextMetrics); setQueue(nextQueue); setUpdated(new Date());
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  const statuses = metrics?.status_counts || {};
  const cards = [
    { label: 'Total documents', value: metrics?.total_documents ?? 0, icon: FileText, color: 'text-blue-600', caption: 'In this workspace' },
    { label: 'Processing success', value: `${Number(metrics?.processing_success_rate ?? 0).toFixed(1)}%`, icon: CheckCircle2, color: 'text-emerald-600', caption: 'Backend-reported rate' },
    { label: 'Accuracy', value: `${Number(metrics?.accuracy_rate_percentage ?? 0).toFixed(1)}%`, icon: Gauge, color: 'text-indigo-600', caption: 'Extraction confidence' },
    { label: 'Avg. process time', value: `${Number(metrics?.avg_processing_time_seconds ?? 0).toFixed(2)}s`, icon: Clock3, color: 'text-sky-600', caption: 'For processed documents' },
  ];
  const typeData = Object.entries(metrics?.type_counts || {}).map(([name, count]) => ({ name: pretty(name), count }));
  const statusData = Object.entries(statuses).map(([name, count]) => ({ name: pretty(name), count }));

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-medium text-blue-600">Reporting</p><h1 className="mt-1 text-2xl font-bold text-slate-900">Analytics</h1><p className="mt-1 text-sm text-slate-500">Workspace metrics supplied by the backend.</p></div><div className="flex items-center gap-3"><span className="text-xs text-slate-400">{updated ? `Updated ${updated.toLocaleTimeString()}` : ''}</span><button onClick={load} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh</button></div></div>
    {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cards.map(({ label, value, icon: Icon, color, caption }) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-center justify-between"><span className="text-sm text-slate-500">{label}</span><Icon className={`h-5 w-5 ${color}`} /></div><p className="mt-4 text-3xl font-bold text-slate-900">{loading ? '…' : value}</p><p className="mt-1 text-xs text-slate-400">{caption}</p></div>)}</div>
    <div className="grid gap-6 lg:grid-cols-2"><section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-800">Documents by type</h2>{typeData.length ? <div className="mt-4 h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={typeData} margin={{ top: 8, right: 8, bottom: 24, left: -18 }}><CartesianGrid vertical={false} strokeDasharray="3 3" /><XAxis dataKey="name" angle={-18} textAnchor="end" interval={0} tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="count" radius={[5, 5, 0, 0]}>{typeData.map((item, index) => <Cell key={item.name} fill={COLORS[index % COLORS.length]} />)}</Bar></BarChart></ResponsiveContainer></div> : <p className="py-12 text-center text-sm text-slate-400">No type data returned yet.</p>}</section>
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="font-bold text-slate-800">Processing queue</h2><p className="mt-1 text-xs text-slate-400">Live counters from the queue endpoint</p><div className="mt-5 grid grid-cols-2 gap-3">{[['Queued', queue?.queued], ['Processing', queue?.processing], ['Completed', queue?.completed], ['Failed', queue?.failed]].map(([label, value]) => <div key={label} className="rounded-lg bg-slate-50 p-4"><div className="flex items-center gap-2 text-xs text-slate-500"><Activity className="h-4 w-4" />{label}</div><p className="mt-2 text-2xl font-bold text-slate-800">{loading ? '…' : value ?? 0}</p></div>)}</div><p className={`mt-4 text-xs ${queue?.is_healthy ? 'text-emerald-600' : 'text-rose-600'}`}>{queue ? queue.is_healthy ? 'Queue service reports healthy' : 'Queue service reports unhealthy' : 'Queue health unavailable'}</p></section></div>
    <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 flex items-center gap-2"><Layers3 className="h-5 w-5 text-blue-600" /><h2 className="font-bold text-slate-800">Status counts</h2></div>{statusData.length ? <div className="space-y-3">{statusData.map((item, index) => { const max = Math.max(1, ...statusData.map((entry) => Number(entry.count))); return <div key={item.name} className="grid grid-cols-[120px_1fr_40px] items-center gap-3 text-xs"><span className="text-slate-500">{item.name}</span><span className="h-2 overflow-hidden rounded-full bg-slate-100"><span className="block h-full rounded-full" style={{ width: `${Number(item.count) / max * 100}%`, backgroundColor: COLORS[index % COLORS.length] }} /></span><strong className="text-right text-slate-700">{item.count}</strong></div>; })}</div> : <p className="text-sm text-slate-400">No status metrics returned.</p>}</section>
  </div>;
}
