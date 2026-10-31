import React, { useCallback, useEffect, useState } from 'react';
import { Activity, GitBranch, Play, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { apiRequest } from '../api/client.js';

const TRIGGERS = ['ON_DOCUMENT_UPLOADED', 'ON_DOCUMENT_EXTRACTED', 'ON_DOCUMENT_APPROVED', 'ON_DOCUMENT_REJECTED', 'ON_LOW_CONFIDENCE', 'SCHEDULED', 'MANUAL'];
const pretty = (text) => String(text || '').replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function Workflow() {
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [form, setForm] = useState({ name: '', description: '', trigger_type: 'ON_DOCUMENT_APPROVED' });

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setWorkflows(await apiRequest('/api/v1/workflows')); }
    catch (err) { setError(err.message); setWorkflows([]); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async (event) => {
    event.preventDefault(); setBusy('create'); setError(''); setMessage('');
    try {
      await apiRequest('/api/v1/workflows', { method: 'POST', body: {
        name: form.name.trim(), description: form.description.trim() || null,
        trigger_type: form.trigger_type, is_active: true, conditions: {},
        actions: [{ type: 'NOTIFICATION', name: 'Document status notification', params: { message: `Workflow ${form.name.trim()} triggered` } }],
      } });
      setForm({ name: '', description: '', trigger_type: 'ON_DOCUMENT_APPROVED' });
      setMessage('Workflow created in the backend.'); await load();
    } catch (err) { setError(err.message); }
    finally { setBusy(''); }
  };

  const toggle = async (workflow) => {
    setBusy(workflow.id); setError(''); setMessage('');
    try { await apiRequest(`/api/v1/workflows/${workflow.id}`, { method: 'PATCH', body: { is_active: !workflow.is_active } }); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusy(''); }
  };

  const remove = async (workflow) => {
    if (!window.confirm(`Delete workflow “${workflow.name}” and its execution history?`)) return;
    setBusy(workflow.id); setError('');
    try { await apiRequest(`/api/v1/workflows/${workflow.id}`, { method: 'DELETE' }); setMessage('Workflow deleted.'); await load(); }
    catch (err) { setError(err.message); }
    finally { setBusy(''); }
  };

  const execute = async (workflow) => {
    setBusy(`run-${workflow.id}`); setError(''); setMessage('');
    try { const result = await apiRequest(`/api/v1/workflows/${workflow.id}/execute`, { method: 'POST' }); setMessage(`Execution ${result.status || 'completed'} · ${result.id || 'record created'}`); }
    catch (err) { setError(err.message); }
    finally { setBusy(''); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-medium text-blue-600">Automation</p><h1 className="mt-1 text-2xl font-bold text-slate-900">Workflows</h1><p className="mt-1 text-sm text-slate-500">Manage persisted workflow rules in the active workspace.</p></div><button onClick={load} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />Refresh</button></div>
      {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}{message && <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</div>}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(300px,.8fr)]"><section className="space-y-3">{loading ? <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">Loading workflows…</div> : workflows.length === 0 ? <div className="rounded-xl border border-slate-200 bg-white p-10 text-center"><GitBranch className="mx-auto h-9 w-9 text-slate-300" /><h2 className="mt-3 font-semibold text-slate-700">No workflows configured</h2><p className="mt-1 text-sm text-slate-500">Create a workflow to add an automation rule to this workspace.</p></div> : workflows.map((workflow) => <article key={workflow.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-3"><div className="flex items-start gap-3"><span className="rounded-lg bg-blue-50 p-2 text-blue-600"><GitBranch className="h-5 w-5" /></span><div><h2 className="font-semibold text-slate-800">{workflow.name}</h2><p className="mt-1 text-xs text-slate-500">{pretty(workflow.trigger_type)} · {workflow.description || 'No description'}</p><p className="mt-2 font-mono text-[10px] text-slate-400">{workflow.id}</p></div></div><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${workflow.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{workflow.is_active ? 'Active' : 'Paused'}</span></div><div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3"><button disabled={!!busy} onClick={() => toggle(workflow)} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50">{workflow.is_active ? 'Pause' : 'Activate'}</button><button disabled={!!busy} onClick={() => execute(workflow)} className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700"><Play className="h-3.5 w-3.5" />{busy === `run-${workflow.id}` ? 'Running…' : 'Run now'}</button><button disabled={!!busy} onClick={() => remove(workflow)} className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50"><Trash2 className="h-3.5 w-3.5" />Delete</button></div></article>)}</section>
        <form onSubmit={create} className="h-fit rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-4 flex items-center gap-2"><Plus className="h-5 w-5 text-blue-600" /><h2 className="font-semibold text-slate-800">Create workflow</h2></div><label className="block text-sm font-medium text-slate-700">Name<input required maxLength={100} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500" placeholder="Invoice approval" /></label><label className="mt-4 block text-sm font-medium text-slate-700">Description<textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={3} className="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm outline-none focus:border-blue-500" placeholder="Optional" /></label><label className="mt-4 block text-sm font-medium text-slate-700">Trigger<select value={form.trigger_type} onChange={(event) => setForm({ ...form, trigger_type: event.target.value })} className="mt-1.5 w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm">{TRIGGERS.map((trigger) => <option key={trigger} value={trigger}>{pretty(trigger)}</option>)}</select></label><p className="mt-3 flex items-start gap-2 text-xs text-slate-400"><Activity className="mt-0.5 h-3.5 w-3.5 shrink-0" />A notification action is added; configure more actions in the backend as needed.</p><button disabled={busy === 'create'} className="mt-5 w-full rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{busy === 'create' ? 'Creating…' : 'Create workflow'}</button></form>
      </div>
    </div>
  );
}
