import React, { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { LoaderCircle } from 'lucide-react';
import { authStorage, clearAuth, restoreSession, signIn, signUp } from './api/client.js';
import { AuthContext, useAuth } from './auth/AuthContext.jsx';
import Login from './auth/Login.jsx';
import DashboardLayout from './Pages/DashboardLayout.jsx';

const Dashboard = lazy(() => import('./Pages/Dashboard.jsx'));
const Documents = lazy(() => import('./Pages/Documents.jsx'));
const Upload = lazy(() => import('./Pages/Upload.jsx'));
const Workflow = lazy(() => import('./Pages/Workflow.jsx'));
const Analytics = lazy(() => import('./Pages/Analytics.jsx'));
const AuditLog = lazy(() => import('./Pages/AuditLog.jsx'));

function AuthProvider({ children }) {
  const [user, setUser] = useState(authStorage.user);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    restoreSession().then(setUser).finally(() => setReady(true));
  }, []);

  const value = useMemo(() => ({
    user,
    ready,
    async login(email, password) {
      const profile = await signIn(email, password);
      setUser(profile);
      return profile;
    },
    async register(form) {
      const profile = await signUp(form);
      setUser(profile);
      return profile;
    },
    async logout() {
      clearAuth();
      setUser(null);
    },
  }), [user, ready]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function FullPageLoader() {
  return <div className="min-h-screen grid place-items-center bg-main text-brand-text"><LoaderCircle className="h-7 w-7 animate-spin" aria-label="Loading" /></div>;
}

function Protected({ children }) {
  const { user, ready } = useAuth();
  if (!ready) return <FullPageLoader />;
  return user ? children : <Navigate to="/login" replace />;
}

function PublicOnly() {
  const { user, ready, login, register } = useAuth();
  if (!ready) return <FullPageLoader />;
  if (user) return <Navigate to="/dashboard" replace />;
  return <Login onLogin={login} onRegister={register} />;
}

function AppRoutes() {
  const page = (Component) => <Suspense fallback={<FullPageLoader />}><Component /></Suspense>;
  return (
    <Routes>
      <Route path="/login" element={<PublicOnly />} />
      <Route element={<Protected><DashboardLayout /></Protected>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={page(Dashboard)} />
        <Route path="documents" element={page(Documents)} />
        <Route path="upload" element={page(Upload)} />
        <Route path="workflows" element={page(Workflow)} />
        <Route path="analytics" element={page(Analytics)} />
        <Route path="audit-logs" element={page(AuditLog)} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return <HashRouter><AuthProvider><AppRoutes /></AuthProvider></HashRouter>;
}
