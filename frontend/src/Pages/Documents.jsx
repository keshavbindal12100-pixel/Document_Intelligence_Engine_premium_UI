import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Download, FileText, Filter, Search, Trash2, UploadCloud } from 'lucide-react';
import { downloadApiFile } from '../api/client.js';
import { useDocuments } from '../hooks/useDocuments.js';

const badge = {
  Approved: 'bg-emerald-50 text-emerald-700 ring-emerald-600/10',
  Pending: 'bg-amber-50 text-amber-700 ring-amber-600/10',
  Processing: 'bg-blue-50 text-blue-700 ring-blue-600/10',
  Rejected: 'bg-rose-50 text-rose-700 ring-rose-600/10',
  Failed: 'bg-rose-50 text-rose-700 ring-rose-600/10',
};
const date = (value) => value ? new Date(value).toLocaleString() : '—';

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function Documents() {
  const { documents, loading, error, reload, removeDocument } = useDocuments();
  const [params] = useSearchParams();
  const [search, setSearch] = useState(params.get('search') || '');
  useEffect(() => { setSearch(params.get('search') || ''); }, [params]);
  const [filter, setFilter] = useState('All');
  const [message, setMessage] = useState('');
  const [downloading, setDownloading] = useState('');
  const filtered = useMemo(() => documents.filter((doc) => {
    const term = search.trim().toLowerCase();
    const matchesTerm = !term || `${doc.fileName} ${doc.docType} ${doc.id}`.toLowerCase().includes(term);
    const matchesStatus = filter === 'All' || doc.status === filter;
    return matchesTerm && matchesStatus;
  }), [documents, search, filter]);

  const handleDelete = async (doc) => {
    if (!window.confirm(`Delete “${doc.fileName}” from the backend? This cannot be undone.`)) return;
    setMessage('');
    try { await removeDocument(doc.id); setMessage('Document deleted.'); }
    catch (err) { setMessage(err.message); }
  };

  const handleDownload = async (doc) => {
    setDownloading(doc.id);
    setMessage('');
    try {
      const { blob, filename } = await downloadApiFile(`/api/v1/documents/${encodeURIComponent(doc.id)}/download`, doc.fileName);
      saveBlob(blob, filename);
      setMessage(`Downloaded ${filename}.`);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setDownloading('');
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-blue-700">Your workspace</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-slate-950">Documents</h1>
          <p className="mt-2 max-w-xl text-sm leading-6 text-slate-600">Find your files, review what was read, or save a copy to your device.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={reload} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50">Refresh list</button>
          <Link to="/upload" className="inline-flex items-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800"><UploadCloud className="h-4 w-4" />Add a document</Link>
        </div>
      </header>

      {(error || message) && <div role="status" className={`rounded-xl border p-3 text-sm ${error || message.includes(':') ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{error || message}</div>}

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm" aria-label="Find documents">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="absolute left-3.5 top-3 h-4 w-4 text-slate-400" />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by file name, type, or ID" className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-100" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-1 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-500"><Filter className="h-4 w-4" />Status</span>
            {['All', 'Pending', 'Processing', 'Approved', 'Rejected', 'Failed'].map((status) => <button key={status} onClick={() => setFilter(status)} aria-pressed={filter === status} className={`rounded-lg px-3 py-2 text-xs font-semibold transition ${filter === status ? 'bg-blue-700 text-white shadow-sm' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>{status}</button>)}
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">Showing <strong className="text-slate-700">{filtered.length}</strong> of {documents.length} {documents.length === 1 ? 'document' : 'documents'}</p>
      </section>

      {loading ? <div className="rounded-2xl border border-slate-200 bg-white p-14 text-center text-sm text-slate-500">Loading your documents…</div> : filtered.length === 0 ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-blue-50 text-blue-700"><FileText className="h-6 w-6" /></span><h2 className="mt-4 text-lg font-semibold text-slate-900">{documents.length ? 'No files match that search' : 'Your document list is empty'}</h2><p className="mx-auto mt-1 max-w-md text-sm leading-6 text-slate-500">{documents.length ? 'Try another name or choose a different status.' : 'Add a document to have it read and organized here.'}</p>{!documents.length && <Link to="/upload" className="mt-5 inline-flex items-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-800"><UploadCloud className="h-4 w-4" />Add your first document</Link>}</div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{filtered.map((doc) => <article key={doc.id} className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3"><span className="rounded-xl bg-blue-50 p-3 text-blue-700"><FileText className="h-5 w-5" /></span><div className="min-w-0"><h2 title={doc.fileName} className="truncate text-sm font-semibold text-slate-900">{doc.fileName}</h2><p className="mt-1 text-xs text-slate-500">{doc.docType} {doc.fileType !== 'Unknown' ? `· ${doc.fileType}` : ''}</p></div></div>
          <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${badge[doc.status] || 'bg-slate-100 text-slate-600 ring-slate-500/10'}`}>{doc.status}</span>
        </div>
        <dl className="mt-5 space-y-3 border-t border-slate-100 pt-4 text-xs">
          <div className="flex justify-between gap-3"><dt className="text-slate-500">Added</dt><dd className="text-right text-slate-700">{date(doc.uploadedAt)}</dd></div>
          <div className="flex justify-between"><dt className="text-slate-500">File size</dt><dd className="text-slate-700">{doc.fileSize ? `${(doc.fileSize / 1024).toFixed(1)} KB` : '—'}</dd></div>
          <div className="flex justify-between"><dt className="text-slate-500">Reading confidence</dt><dd className="font-medium text-slate-700">{doc.confidence ? `${(doc.confidence * (doc.confidence <= 1 ? 100 : 1)).toFixed(0)}%` : 'Not available yet'}</dd></div>
          <div className="flex justify-between gap-3"><dt className="text-slate-500">Reference ID</dt><dd className="max-w-44 truncate font-mono text-[11px] text-slate-500" title={doc.id}>{doc.id}</dd></div>
        </dl>
        <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          <Link to={`/upload?document=${encodeURIComponent(doc.id)}`} className="flex-1 rounded-xl bg-blue-700 px-3 py-2.5 text-center text-xs font-semibold text-white transition hover:bg-blue-800">View results</Link>
          <button onClick={() => handleDownload(doc)} disabled={!!downloading} className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 px-3 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50" aria-label={`Download original ${doc.fileName}`} title="Download original file">{downloading === doc.id ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-blue-700" /> : <Download className="h-4 w-4" />}<span className="hidden sm:inline">Download file</span></button>
          <button onClick={() => handleDelete(doc)} aria-label={`Delete ${doc.fileName}`} title="Delete document" className="rounded-xl border border-rose-100 p-2.5 text-rose-600 transition hover:bg-rose-50"><Trash2 className="h-4 w-4" /></button>
        </div>
      </article>)}</div>}
    </div>
  );
}
