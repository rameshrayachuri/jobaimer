import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "../lib/api";
import { Users, Zap, Send, DollarSign, BarChart2, LifeBuoy, Loader2, TrendingUp } from "lucide-react";
const fmt = (c: number) => new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",minimumFractionDigits:0}).format(c/100);
export default function OverviewPage() {
  const { data: kpis, isLoading } = useQuery({ queryKey:["admin-kpis"], queryFn:()=>adminFetch("/admin/v1/overview/kpis"), refetchInterval:15_000 });
  const { data: status } = useQuery({ queryKey:["admin-status"], queryFn:()=>adminFetch("/admin/v1/overview/status"), refetchInterval:15_000 });
  const stats = kpis ? [
    { label:"Total Users",   value:kpis.total_users?.toLocaleString(),   icon:Users,     c:"text-blue-400",   bg:"bg-blue-500/10" },
    { label:"Active Agents", value:kpis.active_today?.toLocaleString(),  icon:Zap,       c:"text-emerald-400",bg:"bg-emerald-500/10" },
    { label:"Apps / 24h",   value:kpis.apps_last_24h?.toLocaleString(), icon:Send,      c:"text-violet-400", bg:"bg-violet-500/10" },
    { label:"MRR",           value:fmt(kpis.mrr_cents||0),               icon:DollarSign,c:"text-yellow-400", bg:"bg-yellow-500/10" },
    { label:"Avg ATS",       value:`${kpis.avg_ats||0}%`,                icon:BarChart2, c:"text-cyan-400",   bg:"bg-cyan-500/10" },
    { label:"Open Tickets",  value:kpis.open_tickets?.toLocaleString(),  icon:LifeBuoy,  c:"text-red-400",    bg:"bg-red-500/10" },
  ] : [];
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Overview</h1>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <div className={`w-1.5 h-1.5 rounded-full ${status?.database==="healthy"?"bg-emerald-400":"bg-red-400"}`}/>
          DB {status?.database??"…"}
        </div>
      </div>
      {isLoading ? <div className="flex items-center justify-center py-20"><Loader2 size={24} className="animate-spin text-slate-600"/></div> : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
          {stats.map(({label,value,icon:Icon,c,bg})=>(
            <div key={label} className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm text-slate-400">{label}</p>
                <div className={`p-2 rounded-xl ${bg}`}><Icon size={16} className={c}/></div>
              </div>
              <p className="text-3xl font-semibold text-white">{value}</p>
            </div>
          ))}
        </div>
      )}
      {status && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-4"><TrendingUp size={15} className="text-slate-500"/><h2 className="text-sm font-medium text-slate-300">System Health</h2></div>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(status).map(([k,v])=>(
              <div key={k} className="flex items-center justify-between px-3 py-2 bg-slate-800 rounded-lg">
                <span className="text-sm text-slate-400 capitalize">{k.replace(/_/g," ")}</span>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${v==="healthy"?"bg-emerald-900/50 text-emerald-400":"bg-red-900/50 text-red-400"}`}>{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
