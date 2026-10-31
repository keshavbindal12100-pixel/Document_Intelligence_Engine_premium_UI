import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, AlertCircle, ArrowUpRight, BarChart3, CheckCircle2, Clock3, FileText, RefreshCw, UploadCloud, XCircle } from 'lucide-react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { apiRequest } from '../api/client.js';

const COLORS = ['#4f7dff', '#22c993', '#f7ad45', '#fb7185', '#94a3b8'];
const pretty = (value) => String(value || 'unknown').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function Dashboard() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try { setMetrics(await apiRequest('/api/v1/dashboard/metrics')); }
    catch (err) { setError(err.message); setMetrics(null); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const statuses = metrics?.status_counts || {};
  const count = (key) => Number(statuses[key] ?? metrics?.[key] ?? 0);
  const pending = count('uploaded') + count('queued') + count('review_required');
  const completed = count('completed');
  const rejected = count('rejected');
  const failed = count('failed');
  const types = Object.entries(metrics?.type_counts || {}).map(([name, value]) => ({ name: pretty(name), value: Number(value) })).filter((item) => item.value > 0);
  const statusData = [
    { name: 'Completed', value: completed }, { name: 'Pending', value: pending },
    { name: 'Rejected', value: rejected }, { name: 'Failed', value: failed },
  ].filter((item) => item.value > 0);
  const recent = metrics?.recent_documents || [];
  const stats = [
    { label: 'Total documents', value: metrics?.total_documents ?? '—', detail: 'Files in your workspace', icon: FileText, color: 'text-blue-700', bg: 'bg-blue-50', accent: 'from-blue-500 to-indigo-500' },
    { label: 'Waiting for review', value: pending, detail: 'Ready for your attention', icon: AlertCircle, color: 'text-amber-700', bg: 'bg-amber-50', accent: 'from-amber-400 to-orange-500' },
    { label: 'Completed', value: completed, detail: 'Finished successfully', icon: CheckCircle2, color: 'text-emerald-700', bg: 'bg-emerald-50', accent: 'from-emerald-400 to-teal-500' },
    { label: 'Rejected or failed', value: rejected + failed, detail: 'May need another look', icon: XCircle, color: 'text-rose-700', bg: 'bg-rose-50', accent: 'from-rose-400 to-pink-500' },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-7">
      <section className="dashboard-hero relative overflow-hidden rounded-[28px] p-6 text-white shadow-xl shadow-blue-950/10 sm:p-8 lg:p-9">
        <div className="dashboard-hero-orb dashboard-hero-orb-one" /><div className="dashboard-hero-orb dashboard-hero-orb-two" />
        <div className="relative z-10 flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl"><span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[.08] px-3 py-1.5 text-xs font-semibold text-blue-100"><span className="h-1.5 w-1.5 rounded-full bg-emerald-300" />Workspace command center</span><h1 className="mt-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">Documents, in control.</h1><p className="mt-3 max-w-xl text-sm leading-6 text-blue-100/80 sm:text-base">A clear view of what has arrived, what needs your attention, and what is already done.</p></div>
          <div className="flex flex-wrap gap-2"><button onClick={load} disabled={loading} className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/[.08] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/[.14]"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh</button><Link to="/upload" className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-blue-800 shadow-sm transition hover:bg-blue-50"><UploadCloud className="h-4 w-4" />Upload a document<ArrowUpRight className="h-4 w-4" /></Link></div>
        </div>
        <div className="relative z-10 mt-7 flex flex-wrap gap-x-6 gap-y-2 border-t border-white/10 pt-4 text-xs text-blue-100/70"><span className="inline-flex items-center gap-2"><Activity className="h-3.5 w-3.5" />Live workspace metrics</span><span>Updated from your connected backend</span></div>
      </section>

      {error && <div role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{stats.map(({ label, value, detail, icon: Icon, color, bg, accent }) => <article key={label} className="metric-card relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${accent}`} /><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-medium text-slate-500">{label}</p><p className="mt-4 text-3xl font-bold tracking-tight text-slate-950">{loading ? '…' : value}</p></div><span className={`rounded-xl p-2.5 ${bg}`}><Icon className={`h-5 w-5 ${color}`} /></span></div><p className="mt-2 text-xs text-slate-400">{detail}</p></article>)}</div>

      <div className="grid gap-5 lg:grid-cols-5">
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm lg:col-span-3"><div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-5 sm:px-6"><div><div className="flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-lg bg-blue-50 text-blue-700"><FileText className="h-4 w-4" /></span><h2 className="font-bold text-slate-900">Recent documents</h2></div><p className="mt-1.5 text-xs text-slate-500">The latest files added to this workspace</p></div><Link to="/documents" className="inline-flex items-center gap-1 text-sm font-semibold text-blue-700 hover:text-blue-900">See all files<ArrowUpRight className="h-4 w-4" /></Link></div>
          {loading ? <p className="py-10 text-center text-sm text-slate-400">Loading your latest documents…</p> : recent.length ? <div className="overflow-x-auto"><table className="w-full min-w-[520px] text-left text-sm"><thead className="bg-slate-50/80 text-[10px] font-semibold uppercase tracking-[.12em] text-slate-400"><tr><th className="px-5 py-3 sm:px-6">Document</th><th className="px-3 py-3">Type</th><th className="px-3 py-3">Status</th><th className="px-5 py-3 sm:px-6">Added</th></tr></thead><tbody>{recent.slice(0, 6).map((doc) => <tr key={doc.id} className="border-t border-slate-100 transition hover:bg-slate-50/70"><td className="max-w-56 truncate px-5 py-3.5 font-medium text-slate-800 sm:px-6">{doc.filename || doc.id}</td><td className="px-3 py-3.5 text-xs text-slate-500">{pretty(doc.document_type)}</td><td className="px-3 py-3.5"><span className="inline-flex rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">{pretty(doc.status)}</span></td><td className="whitespace-nowrap px-5 py-3.5 text-xs text-slate-500 sm:px-6">{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '—'}</td></tr>)}</tbody></table></div> : <div className="px-5 py-12 text-center sm:px-6"><span className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-slate-50 text-slate-400"><FileText className="h-5 w-5" /></span><p className="mt-3 text-sm font-semibold text-slate-700">No documents yet</p><p className="mt-1 text-xs text-slate-500">Upload your first file to see activity here.</p><Link to="/upload" className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-800"><UploadCloud className="h-3.5 w-3.5" />Upload a file</Link></div>}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 lg:col-span-2"><div className="flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-50 text-indigo-700"><BarChart3 className="h-4 w-4" /></span><h2 className="font-bold text-slate-900">Processing overview</h2></div><p className="mt-1.5 text-xs text-slate-500">A quick look at each document’s progress</p>{statusData.length ? <><div className="mt-3 h-48"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={statusData} dataKey="value" nameKey="name" innerRadius={52} outerRadius={76} paddingAngle={4} stroke="none">{statusData.map((item, index) => <Cell key={item.name} fill={COLORS[index % COLORS.length]} />)}</Pie><Tooltip contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0', boxShadow: '0 8px 24px rgba(15,23,42,.10)' }} /></PieChart></ResponsiveContainer></div><div className="space-y-3">{statusData.map((item, index) => <div key={item.name} className="flex items-center justify-between text-xs"><span className="flex items-center gap-2.5 text-slate-600"><span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />{item.name}</span><span className="font-semibold text-slate-800">{item.value}</span></div>)}</div></> : <div className="grid h-56 place-items-center text-center text-sm text-slate-400">{loading ? 'Loading status…' : 'No status data yet.'}</div>}</section>
      </div>

      <div className="grid gap-4 sm:grid-cols-3"><Metric label="Processing success" value={`${Number(metrics?.processing_success_rate ?? 0).toFixed(1)}%`} note="Documents processed" icon={CheckCircle2} tone="emerald" /><Metric label="Extraction accuracy" value={`${Number(metrics?.accuracy_rate_percentage ?? 0).toFixed(1)}%`} note="Backend-reported confidence" icon={BarChart3} tone="indigo" /><Metric label="Average processing" value={`${Number(metrics?.avg_processing_time_seconds ?? 0).toFixed(2)} s`} note="Time per document" icon={Clock3} tone="sky" /></div>
      {!!types.length && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6"><div className="flex items-center gap-2"><span className="grid h-8 w-8 place-items-center rounded-lg bg-violet-50 text-violet-700"><FileText className="h-4 w-4" /></span><h2 className="font-bold text-slate-900">Your document mix</h2></div><div className="mt-4 flex flex-wrap gap-2.5">{types.map((item) => <span key={item.name} className="rounded-xl border border-slate-100 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-600">{item.name}<strong className="ml-2 text-slate-950">{item.value}</strong></span>)}</div></section>}
    </div>
  );
}

function Metric({ label, value, note, icon: Icon, tone }) {
  const tones = { emerald: 'bg-emerald-50 text-emerald-700', indigo: 'bg-indigo-50 text-indigo-700', sky: 'bg-sky-50 text-sky-700' };
  return <article className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${tones[tone]}`}><Icon className="h-5 w-5" /></span><div className="min-w-0"><p className="text-xs text-slate-500">{label}</p><p className="mt-0.5 text-lg font-bold text-slate-900">{value}</p><p className="text-[10px] text-slate-400">{note}</p></div></article>;
}
