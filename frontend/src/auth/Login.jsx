import React, { useEffect, useState } from 'react';
import { AlertCircle, CheckCircle2, Eye, EyeOff, FileText, Lock, Mail, User } from 'lucide-react';
import { backendHealthUrl } from '../api/client.js';

function explainLoginError(error) {
  const message = error?.message || '';
  if (/could not reach the backend|failed to fetch|networkerror|load failed/i.test(message)) {
    return 'DocFlow could not reach its server. Check that the backend is running, then try again.';
  }
  if (/incorrect email or password/i.test(message)) {
    return 'That email and password do not match. Check them, or create a new account below.';
  }
  if (/already exists|already registered/i.test(message)) {
    return 'An account already uses this email. Choose “Sign in” and use that account’s password.';
  }
  return message || 'We could not sign you in. Please try again.';
}

export default function Login({ onLogin, onRegister }) {
  const [mode, setMode] = useState('login');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [backendOnline, setBackendOnline] = useState(null);
  const [login, setLogin] = useState({ email: '', password: '' });
  const [signup, setSignup] = useState({ name: '', email: '', password: '' });

  useEffect(() => {
    let active = true;
    const checkBackend = async () => {
      try {
        const response = await fetch(backendHealthUrl());
        if (active) setBackendOnline(response.ok);
      } catch {
        if (active) setBackendOnline(false);
      }
    };
    checkBackend();
    const timer = setInterval(checkBackend, 15000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      if (mode === 'login') await onLogin(login.email.trim(), login.password);
      else await onRegister({ ...signup, email: signup.email.trim() });
    } catch (err) {
      setError(explainLoginError(err));
    } finally {
      setBusy(false);
    }
  };

  const createDemoWorkspace = async () => {
    setError('');
    setBusy(true);
    try {
      const id = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const password = `${globalThis.crypto?.randomUUID?.() || Math.random().toString(36)}-${globalThis.crypto?.randomUUID?.() || Math.random().toString(36)}!`;
      await onRegister({ name: 'My DocFlow Workspace', email: `demo-${id}@example.com`, password });
    } catch (err) {
      setError(explainLoginError(err));
    } finally {
      setBusy(false);
    }
  };

  const toggleMode = () => {
    setMode((current) => current === 'login' ? 'signup' : 'login');
    setError('');
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <div className="grid min-h-[620px] w-full max-w-5xl overflow-hidden rounded-2xl bg-white shadow-2xl md:grid-cols-2">
        <section className="relative hidden flex-col justify-center overflow-hidden bg-slate-950 p-12 md:flex">
          <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-blue-600/20 blur-3xl" />
          <div className="relative z-10">
            <div className="mb-12 flex items-center gap-3"><div className="rounded-xl bg-blue-600 p-2.5 text-white"><FileText className="h-6 w-6" /></div><span className="text-xl font-bold tracking-tight text-white">DocFlow</span></div>
            <div className="mb-9 flex h-40 items-center justify-center"><div className="relative h-36 w-44"><div className="absolute left-5 top-4 h-28 w-20 -rotate-12 rounded-xl border border-blue-400/30 bg-blue-900/60" /><div className="absolute left-14 top-2 h-32 w-24 rotate-6 rounded-xl border border-blue-300/40 bg-blue-700/70 shadow-xl shadow-blue-500/20" /><div className="absolute left-24 top-5 h-28 w-20 rotate-12 rounded-xl border border-blue-200/40 bg-blue-500/80" /></div></div>
            <h1 className="text-3xl font-bold text-white">Make documents easier to handle</h1>
            <p className="mt-3 text-slate-400">Read, review, and organize documents in one place.</p>
            <ul className="mt-8 space-y-4 text-sm text-slate-200">{['Find important details', 'Check results before approving', 'Save the original or a simple summary'].map((item) => <li key={item} className="flex items-center gap-3"><CheckCircle2 className="h-5 w-5 text-emerald-400" />{item}</li>)}</ul>
          </div>
        </section>

        <section className="flex items-center justify-center p-7 sm:p-12">
          <div className="w-full max-w-md">
            <div className="mb-8 flex items-center gap-2 md:hidden"><div className="rounded-lg bg-blue-600 p-1.5 text-white"><FileText className="h-5 w-5" /></div><span className="text-xl font-bold text-slate-800">DocFlow</span></div>
            <div role="status" className="mb-6 flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs"><span className={`h-2.5 w-2.5 rounded-full ${backendOnline === true ? 'bg-emerald-500' : backendOnline === false ? 'bg-rose-500' : 'bg-amber-400'}`} /><span className="font-medium text-slate-700">{backendOnline === true ? 'Server is ready' : backendOnline === false ? 'Server is not responding' : 'Checking server connection…'}</span>{backendOnline === false && <span className="ml-auto text-slate-500">Sign-in needs the server</span>}</div>
            <p className="text-xs font-semibold uppercase tracking-[.2em] text-blue-600">Document Intelligence Engine</p>
            <h2 className="mt-3 text-3xl font-bold text-slate-900">{mode === 'login' ? 'Sign in to DocFlow' : 'Create your account'}</h2>
            <p className="mt-2 text-sm text-slate-500">{mode === 'login' ? 'Use your email and password, or create a separate workspace to try it.' : 'Set up your own workspace in a few seconds.'}</p>

            {error && <div role="alert" className="mt-5 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-5 text-red-700"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{error}</span></div>}

            <form onSubmit={submit} className="mt-6 space-y-4">
              {mode === 'signup' && <label className="block text-sm font-medium text-slate-700">Your name<div className="relative mt-1.5"><User className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input required autoComplete="name" value={signup.name} onChange={(event) => setSignup({ ...signup, name: event.target.value })} className="w-full rounded-lg border border-slate-200 py-2.5 pl-10 pr-3 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" placeholder="Your name" /></div></label>}
              <label className="block text-sm font-medium text-slate-700">Email address<div className="relative mt-1.5"><Mail className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input required type="email" autoComplete="email" value={mode === 'login' ? login.email : signup.email} onChange={(event) => mode === 'login' ? setLogin({ ...login, email: event.target.value }) : setSignup({ ...signup, email: event.target.value })} className="w-full rounded-lg border border-slate-200 py-2.5 pl-10 pr-3 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" placeholder="you@company.com" /></div></label>
              <label className="block text-sm font-medium text-slate-700">Password<div className="relative mt-1.5"><Lock className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input required type={showPassword ? 'text' : 'password'} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={8} value={mode === 'login' ? login.password : signup.password} onChange={(event) => mode === 'login' ? setLogin({ ...login, password: event.target.value }) : setSignup({ ...signup, password: event.target.value })} className="w-full rounded-lg border border-slate-200 py-2.5 pl-10 pr-11 text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100" placeholder="At least 8 characters" /><button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((value) => !value)} className="absolute right-3 top-3 text-slate-400 hover:text-slate-700">{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></label>
              <button disabled={busy} className="w-full rounded-lg bg-blue-700 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-700/20 transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60">{busy ? 'Connecting…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
            </form>

            {mode === 'login' && <><div className="my-5 flex items-center gap-3"><span className="h-px flex-1 bg-slate-200" /><span className="text-xs text-slate-400">OR</span><span className="h-px flex-1 bg-slate-200" /></div><button type="button" disabled={busy || backendOnline === false} onClick={createDemoWorkspace} className="w-full rounded-lg border border-blue-200 bg-blue-50 py-3 text-sm font-semibold text-blue-800 transition hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50">{busy ? 'Setting up your workspace…' : 'Continue with a new workspace'}</button><p className="mt-2 text-center text-xs leading-5 text-slate-500">No existing account or password needed. This creates a separate workspace just for you.</p></>}

            <p className="mt-6 text-center text-sm text-slate-500">{mode === 'login' ? "Already have an account?" : 'Already have an account?'} <button type="button" onClick={toggleMode} className="font-semibold text-blue-700 hover:text-blue-800">{mode === 'login' ? 'Create an account' : 'Sign in instead'}</button></p>
            <p className="mt-5 text-center text-xs text-slate-400">Your workspace uses the connected DocFlow backend.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
