import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "../lib/api";
import {
  TrendingDown, Loader2, AlertCircle, RefreshCw,
  Server, Brain, Database, HardDrive, CreditCard, Globe,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Cell, PieChart, Pie, Legend,
} from "recharts";

const fmt$ = (cents: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(cents / 100);

const SERVICE_ICONS: Record<string, any> = {
  anthropic: Brain, aws_lambda: Server, aws_ecs: Server,
  aws_s3: HardDrive, supabase: Database, stripe: CreditCard,
  temporal: Globe, cloudflare: Globe,
};
const SERVICE_COLORS: Record<string, string> = {
  anthropic: "#8b5cf6", aws_lambda: "#f59e0b", aws_ecs: "#f97316",
  aws_s3: "#10b981", supabase: "#3b82f6", stripe: "#6366f1",
  temporal: "#ec4899", cloudflare: "#facc15",
};

const PERIODS = ["current_month", "last_month", "last_3_months"] as const;
type Period = (typeof PERIODS)[number];
const PERIOD_LABELS: Record<Period, string> = {
  current_month: "This Month",
  last_month: "Last Month",
  last_3_months: "Last 3 Months",
};

export default function CostsPage() {
  const [period, setPeriod] = useState<Period>("current_month");
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-costs", period],
    queryFn: () => adminFetch(`/admin/v1/costs?period=${period}`),
    refetchInterval: 120_000,
  });

  const services: any[] = data?.services ?? [];
  const history: any[] = data?.daily_history ?? [];
  const totalCents: number = data?.total_cents ?? 0;
  const pieData = services.map((s) => ({
    name: s.service.replace(/_/g, " "),
    value: s.cost_cents,
    color: SERVICE_COLORS[s.service] ?? "#64748b",
  }));

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <TrendingDown size={18} className="text-red-400" />
            Infrastructure Costs
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">AWS · Anthropic · Supabase · Stripe · Temporal</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {PERIODS.map((p) => (
              <button key={p} onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${period === p ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white hover:bg-slate-800"}`}>
                {PERIOD_LABELS[p]}
              </button>
            ))}
          </div>
          <button onClick={() => refetch()} disabled={isFetching}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors disabled:opacity-50">
            <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20"><Loader2 size={24} className="animate-spin text-slate-600" /></div>
      ) : (
        <>
          {/* Summary */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label: "Total Cost", value: fmt$(totalCents), sub: PERIOD_LABELS[period].toLowerCase() },
              { label: "Cost per User", value: data?.per_user_cents ? fmt$(data.per_user_cents) : "—", sub: "avg per active subscriber" },
              { label: "Projected Month", value: data?.projected_month_cents ? fmt$(data.projected_month_cents) : "—", sub: "at current rate" },
            ].map(({ label, value, sub }) => (
              <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl px-5 py-4">
                <p className="text-xs text-slate-500 mb-1">{label}</p>
                <p className="text-2xl font-semibold text-white">{value}</p>
                <p className="text-xs text-slate-600 mt-0.5">{sub}</p>
              </div>
            ))}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {history.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                <p className="text-sm font-medium text-slate-300 mb-4">Daily Cost Trend</p>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={history}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={(v) => `$${(v / 100).toFixed(0)}`} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} tickLine={false} />
                    <Tooltip formatter={(v: any) => fmt$(v)} contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, color: "#e2e8f0", fontSize: 12 }} />
                    <Bar dataKey="cost_cents" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            {pieData.length > 0 && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
                <p className="text-sm font-medium text-slate-300 mb-4">Cost by Service</p>
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80}>
                      {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                    </Pie>
                    <Tooltip formatter={(v: any) => fmt$(v)} contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, color: "#e2e8f0", fontSize: 12 }} />
                    <Legend formatter={(value) => <span style={{ color: "#94a3b8", fontSize: 11 }}>{value}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Service table */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-800 grid grid-cols-[1fr_120px_120px_80px] gap-4 text-[11px] font-medium text-slate-500 uppercase tracking-wide">
              <span>Service</span><span>Cost</span><span>% of Total</span><span>vs Prior</span>
            </div>
            {services.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-12 text-slate-600">
                <AlertCircle size={24} className="opacity-30" />
                <p className="text-sm">No cost data — check API integrations</p>
              </div>
            ) : (
              [...services].sort((a, b) => b.cost_cents - a.cost_cents).map((s) => {
                const Icon = SERVICE_ICONS[s.service] ?? Server;
                const pct = totalCents > 0 ? ((s.cost_cents / totalCents) * 100).toFixed(1) : "0";
                const delta = s.prior_cost_cents
                  ? (((s.cost_cents - s.prior_cost_cents) / s.prior_cost_cents) * 100).toFixed(0)
                  : null;
                const color = SERVICE_COLORS[s.service] ?? "#64748b";
                return (
                  <div key={s.service} className="px-5 py-3.5 border-b border-slate-800/50 last:border-0 grid grid-cols-[1fr_120px_120px_80px] gap-4 items-center">
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}20` }}>
                        <Icon size={13} style={{ color }} />
                      </div>
                      <div>
                        <p className="text-sm text-slate-200 capitalize">{s.service.replace(/_/g, " ")}</p>
                        {s.note && <p className="text-xs text-slate-600">{s.note}</p>}
                      </div>
                    </div>
                    <span className="text-sm font-medium text-white">{fmt$(s.cost_cents)}</span>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
                      </div>
                      <span className="text-xs text-slate-400 w-10 text-right">{pct}%</span>
                    </div>
                    <span className={`text-xs ${delta === null ? "text-slate-600" : Number(delta) > 0 ? "text-red-400" : "text-emerald-400"}`}>
                      {delta === null ? "—" : `${Number(delta) > 0 ? "+" : ""}${delta}%`}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
}
