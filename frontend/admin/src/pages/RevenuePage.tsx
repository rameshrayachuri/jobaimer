import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "../lib/api";
import { DollarSign, TrendingUp, Loader2 } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
const fmt=(c:number)=>new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",minimumFractionDigits:0}).format(c/100);
export default function RevenuePage() {
  const {data,isLoading}=useQuery({queryKey:["admin-revenue"],queryFn:()=>adminFetch("/admin/v1/revenue"),refetchInterval:60_000});
  const metrics=data?.metrics??{};
  const chartData=data?.mrr_history??[];
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <h1 className="text-xl font-semibold text-white flex items-center gap-2"><DollarSign size={18} className="text-blue-400"/>Revenue</h1>
      {isLoading?<div className="flex items-center justify-center py-20"><Loader2 size={22} className="animate-spin text-slate-600"/></div>:(
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              {label:"MRR",value:fmt(metrics.mrr_cents||0)},
              {label:"ARR",value:fmt((metrics.mrr_cents||0)*12)},
              {label:"Active Subs",value:(metrics.active_subscriptions||0).toLocaleString()},
              {label:"Churn Rate",value:`${metrics.churn_rate||0}%`},
            ].map(({label,value})=>(
              <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="text-2xl font-semibold text-white mt-0.5">{value}</p>
              </div>
            ))}
          </div>
          {chartData.length>0&&(
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-4"><TrendingUp size={14} className="text-slate-500"/><span className="text-sm font-medium text-slate-300">MRR History</span></div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b"/>
                  <XAxis dataKey="month" tick={{fill:"#64748b",fontSize:11}} axisLine={false} tickLine={false}/>
                  <YAxis tickFormatter={v=>fmt(v)} tick={{fill:"#64748b",fontSize:11}} axisLine={false} tickLine={false}/>
                  <Tooltip formatter={(v:any)=>fmt(v)} contentStyle={{background:"#0f172a",border:"1px solid #1e293b",borderRadius:8,color:"#e2e8f0"}}/>
                  <Line type="monotone" dataKey="mrr_cents" stroke="#3b82f6" strokeWidth={2} dot={false}/>
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
          {data?.recent_invoices?.length>0&&(
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="px-5 py-3 border-b border-slate-800 text-xs font-medium text-slate-500 uppercase tracking-wide">Recent Invoices</div>
              {data.recent_invoices.map((inv:any)=>(
                <div key={inv.id} className="flex items-center gap-4 px-5 py-3 border-b border-slate-800/50 last:border-0">
                  <div className="flex-1">
                    <p className="text-sm text-slate-300">{inv.user_email}</p>
                    <p className="text-xs text-slate-500">{inv.plan_name} · {new Date(inv.paid_at).toLocaleDateString()}</p>
                  </div>
                  <span className="text-sm font-medium text-emerald-400">{fmt(inv.amount_paid)}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
