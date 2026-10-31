import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Activity, BarChart3, Check, FileClock, FileText, LayoutDashboard, LogOut, Search, UploadCloud, Workflow as WorkflowIcon } from 'lucide-react';
import { authStorage, backendHealthUrl } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';

const links = [
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Documents', path: '/documents', icon: FileText },
  { label: 'Upload & Review', path: '/upload', icon: UploadCloud },
  { label: 'Workflows', path: '/workflows', icon: WorkflowIcon },
  { label: 'Analytics', path: '/analytics', icon: BarChart3 },
  { label: 'Audit Logs', path: '/audit-logs', icon: FileClock },
];

export default function DashboardLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [online, setOnline] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const workspaceId = authStorage.workspaceId;
  const displayName = user?.full_name || user?.email?.split('@')[0] || 'User';
  const initials = displayName.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase();

  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const response = await fetch(backendHealthUrl());
        if (active) setOnline(response.ok);
      } catch {
        if (active) setOnline(false);
      }
    };
    check();
    const timer = setInterval(check, 30000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const handleSearch = (event) => {
    event.preventDefault();
    const query = searchQuery.trim();
    navigate(`/documents${query ? `?search=${encodeURIComponent(query)}` : ''}`);
  };

  return (
    <div className="app-layout min-h-screen text-slate-800">
      <aside className="app-sidebar fixed inset-y-0 left-0 z-30 hidden w-64 flex-col px-4 py-5 text-slate-300 md:flex">
        <div className="flex items-center gap-3 px-2 pb-8 pt-1"><div className="brand-mark grid h-11 w-11 place-items-center rounded-2xl text-white"><FileText className="h-5 w-5" /></div><div><span className="block text-lg font-bold tracking-tight text-white">DocFlow</span><span className="mt-0.5 block text-[10px] font-semibold uppercase tracking-[.19em] text-blue-200/70">Intelligence suite</span></div></div>
        <div className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[.18em] text-slate-500">Workspace</div>
        <nav className="flex-1 space-y-1 overflow-y-auto">
          {links.map(({ label, path, icon: Icon }) => <NavLink key={path} to={path} className={({ isActive }) => `sidebar-link group flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-medium transition ${isActive ? 'sidebar-link-active' : 'text-slate-400 hover:bg-white/[.06] hover:text-white'}`}><span className="grid h-8 w-8 place-items-center rounded-lg transition group-hover:bg-white/[.07]"><Icon className="h-[18px] w-[18px]" /></span><span>{label}</span></NavLink>)}
        </nav>

        <div className="sidebar-status mt-5 rounded-2xl border border-white/[.08] p-4"><div className="flex items-center justify-between"><span className="text-[10px] font-bold uppercase tracking-[.16em] text-slate-500">System status</span><span className={`h-2 w-2 rounded-full ${online ? 'bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,.8)]' : online === false ? 'bg-rose-400' : 'bg-amber-400'}`} /></div><p className="mt-2 text-sm font-semibold text-white">{online ? 'All systems ready' : online === false ? 'Connection needed' : 'Checking status'}</p><p className="mt-1 text-xs leading-5 text-slate-500">{workspaceId ? `Workspace ${workspaceId.slice(0, 8)}` : 'Personal workspace'}</p></div>

        <div className="mt-4 border-t border-white/[.08] pt-4"><div className="flex items-center gap-3 px-1"><div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-500 text-xs font-bold text-white shadow-lg shadow-blue-950/40">{initials}</div><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-white">{displayName}</p><p className="truncate text-xs text-slate-500">{user?.email}</p></div><button onClick={handleLogout} aria-label="Sign out" title="Sign out" className="rounded-lg p-2 text-slate-500 transition hover:bg-rose-500/10 hover:text-rose-300"><LogOut className="h-4 w-4" /></button></div></div>
      </aside>

      <div className="md:ml-64">
        <header className="app-topbar sticky top-0 z-20 flex min-h-[76px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-7 lg:px-9">
          <form onSubmit={handleSearch} className="top-search flex min-w-0 flex-1 items-center gap-3 md:max-w-xl"><Search className="h-[18px] w-[18px] shrink-0 text-slate-400" /><input aria-label="Search documents" type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search documents, types, or reference IDs" className="w-full bg-transparent py-1 text-sm text-slate-700 outline-none placeholder:text-slate-400" /><kbd className="hidden rounded-md border border-slate-200 bg-slate-50 px-1.5 py-1 text-[10px] text-slate-400 sm:block">↵</kbd><button type="submit" aria-label="Search" className="rounded-lg p-2 text-blue-700 transition hover:bg-blue-50"><Search className="h-4 w-4" /></button></form>
          <div className="flex items-center gap-3"><span className={`connection-pill hidden items-center gap-2 rounded-full px-3 py-2 text-xs font-semibold sm:inline-flex ${online ? 'connection-online' : online === false ? 'connection-offline' : 'connection-checking'}`}><span className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-emerald-500' : online === false ? 'bg-rose-500' : 'bg-amber-500'}`} />{online ? 'Connected' : online === false ? 'Offline' : 'Connecting'}</span><div className="grid h-9 w-9 place-items-center rounded-xl border border-slate-200 bg-white text-xs font-bold text-slate-700 shadow-sm md:hidden">{initials}</div></div>
        </header>

        <nav aria-label="Main navigation" className="mobile-nav flex gap-1.5 overflow-x-auto px-3 py-2.5 md:hidden">{links.map(({ label, path, icon: Icon }) => <NavLink key={path} to={path} className={({ isActive }) => `mobile-link inline-flex shrink-0 items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-semibold transition ${isActive ? 'mobile-link-active' : 'text-slate-500 hover:bg-white hover:text-slate-900'}`}><Icon className="h-4 w-4" />{label}</NavLink>)}<button onClick={handleLogout} className="inline-flex shrink-0 items-center gap-2 rounded-xl px-3 py-2.5 text-xs font-semibold text-rose-600 hover:bg-rose-50"><LogOut className="h-4 w-4" />Sign out</button></nav>
        <main className="app-content min-h-[calc(100vh-76px)] px-4 py-6 sm:px-7 sm:py-8 lg:px-9 lg:py-9"><Outlet /></main>
        <footer className="hidden px-9 pb-6 text-[11px] text-slate-400 md:block">DocFlow <span className="mx-1.5 text-slate-300">/</span> Document intelligence, made clear.</footer>
      </div>
    </div>
  );
}
