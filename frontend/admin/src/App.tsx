import { BrowserRouter as Router, Routes, Route, Navigate, NavLink } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  LayoutDashboard, Users, Bot, LifeBuoy, DollarSign,
  Tag, TrendingDown, Settings2, LogOut, Shield,
} from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

// ─── Auth store ───────────────────────────────────────────────────────────────
interface AdminAuthStore {
  token: string | null;
  email: string | null;
  role: string | null;
  setAuth: (token: string, email: string, role: string) => void;
  clearAuth: () => void;
}
const useAdminAuth = create<AdminAuthStore>()(persist(
  (set) => ({
    token: null, email: null, role: null,
    setAuth: (token, email, role) => set({ token, email, role }),
    clearAuth: () => set({ token: null, email: null, role: null }),
  }),
  { name: "jobaimer-admin-auth" }
));

const cn = (...inputs: any[]) => twMerge(clsx(inputs));

const API = import.meta.env.VITE_ADMIN_API_BASE_URL || "";
const apiReq = async (path: string, options: RequestInit = {}, token?: string | null) => {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
  return res.json();
};

// ─── Nav items ────────────────────────────────────────────────────────────────
const NAV = [
  { to: "/overview",  icon: LayoutDashboard, label: "Overview" },
  { to: "/users",     icon: Users,           label: "Users" },
  { to: "/agent",     icon: Bot,             label: "Agent" },
  { to: "/support",   icon: LifeBuoy,        label: "Support" },
  { to: "/revenue",   icon: DollarSign,      label: "Revenue" },
  { to: "/coupons",   icon: Tag,             label: "Coupons" },
  { to: "/costs",     icon: TrendingDown,    label: "Costs" },
  { to: "/system",    icon: Settings2,       label: "System" },
];

// ─── Login Page ───────────────────────────────────────────────────────────────
function LoginPage() {
  const { setAuth } = useAdminAuth();
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setError("");
    try {
      const data = await apiReq("/admin/auth/sign-in", {
        method: "POST", body: JSON.stringify({ email, password }),
      });
      setAuth(data.access_token, data.email, data.role);
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950">
      <div className="w-full max-w-sm bg-slate-900 rounded-2xl p-8 border border-slate-800">
        <div className="flex items-center gap-2 mb-8">
          <Shield size={20} className="text-blue-400" />
          <span className="font-semibold text-white">JobAimer Admin</span>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input type="email" placeholder="Admin email" value={email} onChange={e => setEmail(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500" />
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button type="submit" disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white rounded-lg py-2.5 text-sm font-medium transition-colors disabled:opacity-50">
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}

// ─── Admin Layout ─────────────────────────────────────────────────────────────
import React, { Suspense, lazy } from "react";
import { Outlet } from "react-router-dom";

const OverviewPage  = lazy(() => import("./pages/OverviewPage"));
const UsersPage     = lazy(() => import("./pages/UsersPage"));
const AgentPage     = lazy(() => import("./pages/AgentPage"));
const SupportPage   = lazy(() => import("./pages/SupportPage"));
const RevenuePage   = lazy(() => import("./pages/RevenuePage"));
const CouponsPage   = lazy(() => import("./pages/CouponsPage"));
const CostsPage     = lazy(() => import("./pages/CostsPage"));
const SystemPage    = lazy(() => import("./pages/SystemPage"));

function AdminLayout() {
  const { email, role, clearAuth } = useAdminAuth();
  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      <aside className="w-56 border-r border-slate-800 flex flex-col">
        <div className="h-14 flex items-center px-5 border-b border-slate-800 gap-2">
          <Shield size={16} className="text-blue-400" />
          <span className="font-semibold text-sm">Admin Panel</span>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to}
              className={({ isActive }) => cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                isActive ? "bg-blue-600/20 text-blue-400" : "text-slate-400 hover:text-slate-100 hover:bg-slate-800"
              )}>
              <Icon size={15} />{label}
            </NavLink>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-slate-800">
          <div className="px-2 py-1.5 mb-1">
            <p className="text-xs text-slate-300 truncate">{email}</p>
            <p className="text-xs text-slate-500">{role}</p>
          </div>
          <button onClick={clearAuth}
            className="flex items-center gap-2 px-3 py-2 w-full rounded-lg text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors">
            <LogOut size={14} />Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Suspense fallback={<div className="flex items-center justify-center h-64 text-slate-500">Loading…</div>}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}

function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { token } = useAdminAuth();
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000 } } });

export default function AdminApp() {
  return (
    <QueryClientProvider client={qc}>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAdmin><AdminLayout /></RequireAdmin>}>
            <Route index element={<Navigate to="/overview" replace />} />
            <Route path="/overview"  element={<OverviewPage />} />
            <Route path="/users"     element={<UsersPage />} />
            <Route path="/agent"     element={<AgentPage />} />
            <Route path="/support"   element={<SupportPage />} />
            <Route path="/revenue"   element={<RevenuePage />} />
            <Route path="/coupons"   element={<CouponsPage />} />
            <Route path="/costs"     element={<CostsPage />} />
            <Route path="/system"    element={<SystemPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </Router>
      <Toaster position="top-right" />
    </QueryClientProvider>
  );
}
