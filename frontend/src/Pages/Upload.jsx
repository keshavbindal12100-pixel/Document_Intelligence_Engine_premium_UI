import React, { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, Download, FileCheck2, FileText, Info, RefreshCw, Sparkles, UploadCloud, X, XCircle } from 'lucide-react';
import { apiRequest, downloadApiFile, normalizeDocument } from '../api/client.js';
import { useDocuments } from '../hooks/useDocuments.js';

const TYPES = [
  ['INVOICE', 'Bill or invoice'], ['RECEIPT', 'Receipt'], ['PURCHASE_ORDER', 'Purchase order'],
  ['FORM', 'Form'], ['CONTRACT', 'Contract'], ['ID_CARD', 'ID card'], ['UNKNOWN', 'Let DocFlow decide'],
];

const FRIENDLY_NAMES = {
  invoice_number: 'Bill number', invoice_no: 'Bill number', invoice_id: 'Bill number',
  invoice_date: 'Bill date', due_date: 'Payment due date', total_amount: 'Total amount',
  subtotal: 'Amount before tax', tax_amount: 'Tax amount', vendor_name: 'Seller or supplier',
  supplier_name: 'Seller or supplier', customer_name: 'Customer name', purchase_order_number: 'Order number',
  currency: 'Currency', payment_terms: 'Payment terms', email: 'Email address', phone: 'Phone number',
  account_number: 'Account number', address: 'Address', bill_to: 'Billed to', ship_to: 'Ship to',
};

const humanize = (name) => {
  const key = String(name).trim().toLowerCase().replace(/[\s.-]+/g, '_');
  if (FRIENDLY_NAMES[key]) return FRIENDLY_NAMES[key];
  return String(name).replace(/[_-]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
};

function rawFieldValue(field) {
  if (!field || typeof field !== 'object' || Array.isArray(field)) return field;
  return field.field_value ?? field.normalized_value ?? field.value ?? field.text ?? '';
}

function readableValue(value) {
  if (value === null || value === undefined || value === '') return 'Not found in this file';
  if (Array.isArray(value)) return value.map(readableValue).join(', ');
  if (typeof value === 'object') return Object.entries(value).map(([key, item]) => `${humanize(key)}: ${readableValue(item)}`).join(' · ');
  return String(value);
}

function confidencePercent(value) {
  const score = Number(value);
  if (!Number.isFinite(score) || score <= 0) return null;
  return Math.round(score <= 1 ? score * 100 : Math.min(score, 100));
}

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

function exportName(filename, extension) {
  const base = String(filename || 'document').replace(/\.[^.]+$/, '').replace(/[^a-z0-9_-]+/gi, '-').replace(/^-|-$/g, '') || 'document';
  return `${base}-results.${extension}`;
}

function buildPlainSummary(document, extraction, rows) {
  const confident = confidencePercent(extraction.overall_confidence);
  const reviewCount = rows.filter((row) => row.needsReview).length;
  const lines = [
    'DOCFLOW — EASY-TO-READ DOCUMENT SUMMARY',
    '========================================',
    `File: ${document.fileName}`,
    `Document type: ${document.docType || humanize(extraction.document_type || 'document')}`,
    `Current status: ${document.status}`,
    ...(confident ? [`Reading confidence: ${confident}%`] : []),
    '',
    'INFORMATION FOUND',
    '-----------------',
    ...(rows.length ? rows.map(({ label, value, needsReview }) => `${label}: ${value}${needsReview ? ' (please check)' : ''}`) : ['No details have been found yet.']),
    '',
    reviewCount ? `Please review ${reviewCount} item${reviewCount === 1 ? '' : 's'} marked “please check”.` : 'No items have been flagged for an extra check.',
    ...(extraction.validation?.warnings?.length ? ['', 'NOTES', ...extraction.validation.warnings.map((item) => `- ${item}`)] : []),
    '',
    `Document reference: ${document.id}`,
  ];
  return lines.join('\n');
}

export default function Upload() {
  const [params] = useSearchParams();
  const { reload } = useDocuments();
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [docType, setDocType] = useState('UNKNOWN');
  const [document, setDocument] = useState(null);
  const [extraction, setExtraction] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    const id = params.get('document');
    if (!id) return;
    let alive = true;
    apiRequest(`/api/v1/documents/${encodeURIComponent(id)}`)
      .then((data) => { if (alive) setDocument(normalizeDocument(data)); })
      .catch((err) => { if (alive) setError(err.message); });
    return () => { alive = false; };
  }, [params]);

  const run = async (label, action) => {
    setBusy(label); setError(''); setNotice('');
    try { await action(); }
    catch (err) { setError(err.message); }
    finally { setBusy(''); }
  };

  const upload = () => run('upload', async () => {
    if (!file) throw new Error('Choose a document first.');
    const form = new FormData();
    form.append('file', file);
    form.append('document_type', docType);
    const anyFormat = !(/\.(pdf|png|jpe?g|tiff?)$/i.test(file.name));
    const endpoint = anyFormat ? '/api/v1/documents/upload-any' : '/api/v1/documents/upload';
    const result = await apiRequest(endpoint, { method: 'POST', body: form });
    setDocument(normalizeDocument(result));
    setExtraction(null);
    setFile(null);
    setNotice(`“${result.original_filename || result.filename || 'Your file'}” was added. Start reading it below when you are ready.`);
    await reload();
  });

  const process = () => run('process', async () => {
    if (!document?.id) throw new Error('Add or open a document first.');
    const result = await apiRequest(`/api/v1/documents/${encodeURIComponent(document.id)}/process`, { method: 'POST' });
    setDocument(normalizeDocument(result));
    setNotice('Reading started. It can take a little while; select “Show my results” again when processing is complete.');
    await reload();
  });

  const getExtraction = () => run('extract', async () => {
    if (!document?.id) throw new Error('Add or open a document first.');
    setExtraction(await apiRequest(`/api/v1/documents/${encodeURIComponent(document.id)}/extraction`));
  });

  const downloadOriginal = () => run('download', async () => {
    const { blob, filename } = await downloadApiFile(`/api/v1/documents/${encodeURIComponent(document.id)}/download`, document.fileName);
    saveBlob(blob, filename);
    setNotice(`Your original file “${filename}” is ready.`);
  });

  const approve = () => run('approve', async () => {
    const result = await apiRequest(`/api/v1/documents/${encodeURIComponent(document.id)}/approve`, { method: 'POST', body: { notes: 'Approved in DocFlow review.' } });
    setDocument(normalizeDocument(result)); setNotice('Document approved.'); await reload();
  });

  const reject = () => run('reject', async () => {
    if (!rejectReason.trim()) throw new Error('Please say why this document should be sent back.');
    const result = await apiRequest(`/api/v1/documents/${encodeURIComponent(document.id)}/reject`, { method: 'POST', body: { reason: rejectReason.trim() } });
    setDocument(normalizeDocument(result)); setNotice('Document sent back for changes.'); await reload();
  });

  const fields = useMemo(() => {
    const source = extraction?.fields;
    if (!source || typeof source !== 'object') return [];
    return Object.entries(source).map(([name, field]) => {
      const value = rawFieldValue(field);
      const isMissing = Boolean(field && typeof field === 'object' && field.is_missing) || value === '' || value === null || value === undefined;
      const confidence = confidencePercent(field && typeof field === 'object' ? (field.confidence ?? field.confidence_score) : null);
      const valid = !(field && typeof field === 'object' && field.is_valid === false);
      return { name, label: humanize(name), value: readableValue(value), rawValue: value, confidence, isMissing, valid, needsReview: isMissing || !valid || (confidence !== null && confidence < 70) };
    });
  }, [extraction]);

  const reviewCount = fields.filter((field) => field.needsReview).length;
  const overallConfidence = confidencePercent(extraction?.overall_confidence);
  const validationMessages = [...(extraction?.validation?.errors || []), ...(extraction?.validation?.warnings || [])];
  const clear = () => { setDocument(null); setExtraction(null); setNotice(''); setError(''); setRejectReason(''); };

  const downloadSummary = () => {
    const text = buildPlainSummary(document, extraction, fields);
    saveBlob(new Blob([text], { type: 'text/plain;charset=utf-8' }), exportName(document.fileName, 'txt'));
    setNotice('Easy-to-read summary saved to your device.');
  };

  const downloadCsv = () => {
    const rows = [['Information', 'Found in document'], ['File', document.fileName], ['Type', document.docType || 'Unknown'], ...fields.map(({ label, value }) => [label, value])];
    const csv = `\uFEFF${rows.map((row) => row.map((cell) => `"${String(cell ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n')}`;
    saveBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), exportName(document.fileName, 'csv'));
    setNotice('Spreadsheet file saved to your device.');
  };

  const downloadJson = () => {
    const data = { document: { name: document.fileName, type: document.docType, status: document.status, id: document.id }, extraction };
    saveBlob(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' }), exportName(document.fileName, 'json'));
    setNotice('Detailed data file saved to your device.');
  };

  const selectFile = (selected) => { if (selected) { setFile(selected); setError(''); setNotice(''); } };

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-8">
      <header className="overflow-hidden rounded-3xl bg-gradient-to-br from-blue-800 via-blue-700 to-indigo-700 px-6 py-7 text-white shadow-lg shadow-blue-900/10 sm:px-8 sm:py-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-2xl"><span className="inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1.5 text-xs font-semibold text-blue-50"><Sparkles className="h-3.5 w-3.5" />Simple document reading</span><h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">Upload & understand</h1><p className="mt-3 text-sm leading-6 text-blue-100 sm:text-base">Add a bill, receipt, or form. DocFlow finds the important details and explains them in everyday language.</p></div>
          <div className="hidden rounded-2xl border border-white/20 bg-white/10 p-4 sm:block"><FileCheck2 className="h-8 w-8 text-white" /></div>
        </div>
        <div className="mt-7 grid gap-2 text-xs font-medium sm:grid-cols-3 sm:text-sm">
          <Step number="1" title="Choose a file" active={!document} complete={Boolean(document)} />
          <Step number="2" title="Read the details" active={Boolean(document && !extraction)} complete={Boolean(extraction)} />
          <Step number="3" title="Save or review" active={Boolean(extraction)} complete={false} />
        </div>
      </header>

      {error && <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
      {notice && <div role="status" className="flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />{notice}</div>}

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue-50 text-sm font-bold text-blue-800">1</span><div><h2 className="text-lg font-semibold text-slate-950">Choose a file to read</h2><p className="mt-1 text-sm text-slate-600">Pick a file from your device. We’ll keep the original available for download.</p></div></div>
        <div className="mt-5 grid gap-4 md:grid-cols-[1fr_220px]">
          <label htmlFor="document-file" onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); selectFile(event.dataTransfer.files?.[0]); }} className={`flex min-h-44 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-6 text-center transition ${dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50 hover:border-blue-400 hover:bg-blue-50/50'}`}>
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-white text-blue-700 shadow-sm"><UploadCloud className="h-6 w-6" /></span>
            <span className="mt-3 max-w-full truncate text-sm font-semibold text-slate-800">{file?.name || 'Choose a file or drop it here'}</span>
            <span className="mt-1 text-xs text-slate-500">PDF, image, or common document formats</span>
            {file && <span className="mt-1 text-[11px] text-slate-400">{(file.size / 1024).toFixed(1)} KB</span>}
            <input id="document-file" type="file" className="sr-only" onChange={(event) => selectFile(event.target.files?.[0])} />
          </label>
          <div className="flex flex-col">
            <label htmlFor="document-type" className="text-sm font-semibold text-slate-700">What kind of file is it?</label>
            <select id="document-type" value={docType} onChange={(event) => setDocType(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-800 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100">{TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
            <button onClick={upload} disabled={!file || !!busy} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50">{busy === 'upload' ? <RefreshCw className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}{busy === 'upload' ? 'Adding your file…' : 'Add this file'}</button>
            <p className="mt-3 flex items-start gap-1.5 text-xs leading-5 text-slate-500"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />You can check the details before approving anything.</p>
          </div>
        </div>
      </section>

      {document ? <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-indigo-50 text-indigo-700"><FileText className="h-5 w-5" /></span><div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Your selected document</p><h2 className="mt-1 break-words text-lg font-semibold text-slate-950">{document.fileName}</h2><p className="mt-1 text-sm text-slate-600">{document.docType} <span className="mx-1 text-slate-300">·</span> Status: <span className="font-medium text-slate-800">{document.status}</span></p></div></div>
          <div className="flex flex-wrap gap-2"><button onClick={downloadOriginal} disabled={!!busy} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"><Download className="h-4 w-4" />{busy === 'download' ? 'Saving…' : 'Download original'}</button><button onClick={clear} className="rounded-xl p-2.5 text-slate-500 transition hover:bg-slate-100" title="Close this document" aria-label="Close this document"><X className="h-4 w-4" /></button></div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          <button onClick={process} disabled={!!busy} className="inline-flex items-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:opacity-50">{busy === 'process' ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{busy === 'process' ? 'Starting…' : 'Start reading this file'}</button>
          <button onClick={getExtraction} disabled={!!busy} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-50">{busy === 'extract' ? <RefreshCw className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}{busy === 'extract' ? 'Getting results…' : 'Show my results'}</button>
        </div>

        {extraction ? <div className="mt-5 border-t border-slate-100 pt-5">
          <div className="rounded-2xl bg-slate-50 p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3"><div className="flex items-start gap-3"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-blue-700 shadow-sm"><Sparkles className="h-5 w-5" /></span><div><h3 className="text-lg font-bold text-slate-950">Here’s what we found</h3><p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">{fields.length ? `We found ${fields.length} ${fields.length === 1 ? 'detail' : 'details'} in this file.${reviewCount ? ` ${reviewCount} ${reviewCount === 1 ? 'needs' : 'need'} a quick check.` : ' Nothing has been flagged for a second look.'}` : 'No details are available yet. The file may still be processing, or it may not contain readable text.'}</p></div></div>
              {overallConfidence !== null && <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${overallConfidence >= 80 ? 'bg-emerald-100 text-emerald-800' : overallConfidence >= 60 ? 'bg-amber-100 text-amber-800' : 'bg-rose-100 text-rose-800'}`}>{overallConfidence}% reading confidence</span>}
            </div>
            {validationMessages.length > 0 && <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><p className="font-semibold">A few things to check</p><ul className="mt-1 list-inside list-disc space-y-1">{validationMessages.map((item, index) => <li key={`${item}-${index}`}>{typeof item === 'string' ? item : item.message || item.details || 'Please review this detail.'}</li>)}</ul></div>}
          </div>

          {fields.length ? <div className="mt-5"><div className="mb-3 flex flex-wrap items-end justify-between gap-2"><div><h3 className="font-semibold text-slate-900">Important details</h3><p className="mt-1 text-xs text-slate-500">Check anything marked “Please check” against the original file.</p></div><span className="text-xs text-slate-500">{fields.length} {fields.length === 1 ? 'detail' : 'details'}</span></div><div className="grid gap-3 sm:grid-cols-2">{fields.map((field) => <article key={field.name} className={`rounded-xl border p-4 ${field.needsReview ? 'border-amber-200 bg-amber-50/50' : 'border-slate-200 bg-white'}`}><div className="flex items-start justify-between gap-2"><p className="text-xs font-semibold text-slate-500">{field.label}</p>{field.needsReview && <span className="shrink-0 rounded-full bg-amber-100 px-2 py-1 text-[10px] font-semibold text-amber-800">Please check</span>}</div><p className={`mt-2 break-words text-sm font-semibold leading-6 ${field.isMissing ? 'italic text-slate-400' : 'text-slate-900'}`}>{field.value}</p>{field.confidence !== null && <p className="mt-2 text-[11px] text-slate-500">Reading confidence: {field.confidence}%</p>}</article>)}</div></div> : <div className="mt-5 rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">When reading is complete, select “Show my results” to see the details.</div>}

          <div className="mt-5 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5"><div><h3 className="font-semibold text-slate-900">Save a copy of these results</h3><p className="mt-1 text-sm text-slate-600">Choose the format that works for you. The easy-read version is best for sharing or printing.</p></div><div className="mt-4 flex flex-wrap gap-2"><button onClick={downloadSummary} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-3.5 py-2.5 text-xs font-semibold text-white transition hover:bg-emerald-800"><Download className="h-4 w-4" />Easy-read summary (.txt)</button><button onClick={downloadCsv} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"><Download className="h-4 w-4" />Spreadsheet (.csv)</button><button onClick={downloadJson} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3.5 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"><Download className="h-4 w-4" />Detailed data (.json)</button></div></div>

          <details className="mt-4 rounded-xl border border-slate-200 bg-white p-4"><summary className="cursor-pointer text-sm font-semibold text-slate-700">More information for technical users</summary><div className="mt-4 space-y-3 text-xs text-slate-600"><p>Document reference: <span className="font-mono">{document.id}</span></p>{extraction.validation?.status && <p>Validation status: {String(extraction.validation.status)}</p>}{extraction.raw_ocr_text && <div><p className="mb-1 font-semibold">Text read from the document</p><pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans leading-5">{extraction.raw_ocr_text}</pre></div>}<pre className="max-h-64 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-100">{JSON.stringify(extraction, null, 2)}</pre></div></details>

          <div className="mt-5 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-5"><button onClick={approve} disabled={!!busy || !fields.length} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:opacity-50"><CheckCircle2 className="h-4 w-4" />Looks good — approve</button><div className="flex flex-wrap items-end gap-2"><label className="text-xs font-medium text-slate-600">Send back with a note<input value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} className="mt-1 block w-64 max-w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm text-slate-800 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" placeholder="What should be corrected?" /></label><button onClick={reject} disabled={!!busy} className="inline-flex items-center gap-2 rounded-xl border border-rose-200 px-4 py-2.5 text-sm font-semibold text-rose-700 transition hover:bg-rose-50 disabled:opacity-50"><XCircle className="h-4 w-4" />Send back</button></div></div>
        </div> : <div className="mt-5 flex items-start gap-2 rounded-xl bg-blue-50 p-4 text-sm leading-6 text-blue-900"><Info className="mt-1 h-4 w-4 shrink-0" /><p>Start reading this file, then select “Show my results” to view the information DocFlow found. If it is still working, wait a moment and try again.</p></div>}
      </section> : <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-5 py-8 text-center text-sm text-slate-500">Once you add a file, its reading status and results will appear here.</div>}
    </div>
  );
}

function Step({ number, title, active, complete }) {
  return <div className={`flex items-center gap-2 rounded-xl px-3 py-2 ${active ? 'bg-white/20 text-white' : 'bg-white/10 text-blue-100'}`}><span className={`grid h-6 w-6 place-items-center rounded-full text-xs font-bold ${complete ? 'bg-emerald-300 text-emerald-950' : 'bg-white/20 text-white'}`}>{complete ? <CheckCircle2 className="h-4 w-4" /> : number}</span><span>{title}</span></div>;
}
