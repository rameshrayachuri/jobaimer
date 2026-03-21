import { useQuery } from "@tanstack/react-query";
import { adminFetch } from "../lib/api";
import { Bot, Zap, ZapOff, Clock, AlertCircle, Loader2 } from "lucide-react";
const fmtDate=(d:string)=>new Date(d).toLocaleString("en-US",{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
export default function AgentPage() {
  const {data,isLoading}=useQuery({queryKey:["admin-agent"],queryFn:()=>adminFetch("/admin/v1/agent"),refetchInterval:10_000});
  const runs=data?.data??[];
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <h1 className="text-xl font-semibold text-white flex items-center gap-2"><Bot size={18} className="text-blue-400"/>Agent Monitor</h1>
      <div className="grid grid-cols-3 gap-3">
        {[{label:"Active Workflows",value:data?.active??0,c:"text-emerald-400"},{label:"Completed Today",value:data?.completed_today??0,c:"text-blue-400"},{label:"Errors Today",value:data?.errors_today??0,c:"text-red-400"}].map(({label,value,c})=>(
          <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500">{label}</p>
            <p className={`text-2xl font-semibold mt-0.5 ${c}`}>{value}</p>
          </div>
        ))}
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-800 text-xs font-medium text-slate-500 uppercase tracking-wide">Recent Workflow Runs</div>
        {isLoading?<div className="flex items-center justify-center py-10"><Loader2 size={20} className="animate-spin text-slate-600"/></div>
        :runs.length===0?<div className="flex flex-col items-center gap-2 py-10 text-slate-600"><AlertCircle size={24} className="opacity-30"/><p className="text-sm">No recent runs</p></div>
        :runs.map((r:any)=>(
          <div key={r.id} className="flex items-center gap-4 px-5 py-3 border-b border-slate-800/50 last:border-0">
            <div className={`w-2 h-2 rounded-full flex-shrink-0 ${r.status==="running"?"bg-blue-400 animate-pulse":r.status==="completed"?"bg-emerald-400":"bg-red-400"}`}/>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-slate-300 truncate">{r.user_email??r.user_id}</p>
              <p className="text-xs text-slate-500">{r.status} · {r.apps_submitted??0} applied · ATS avg {r.avg_ats??0}%</p>
            </div>
            <div className="text-right text-xs text-slate-500">
              <div className="flex items-center gap-1"><Clock size={11}/>{r.started_at?fmtDate(r.started_at):"—"}</div>
              {r.duration_seconds&&<div className="mt-0.5">{r.duration_seconds}s</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
