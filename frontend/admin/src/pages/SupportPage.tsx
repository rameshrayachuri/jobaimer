import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "../lib/api";
import { LifeBuoy, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import toast from "react-hot-toast";
const fmtDate=(d:string)=>new Date(d).toLocaleDateString("en-US",{month:"short",day:"numeric"});
export default function SupportPage() {
  const qc=useQueryClient();
  const [filter,setFilter]=useState("open");
  const {data,isLoading}=useQuery({queryKey:["admin-support",filter],queryFn:()=>adminFetch(`/admin/v1/support/tickets?status=${filter}`),refetchInterval:20_000});
  const closeMut=useMutation({
    mutationFn:(id:string)=>adminFetch(`/admin/v1/support/tickets/${id}/close`,{method:"POST"}),
    onSuccess:()=>{toast.success("Ticket closed");qc.invalidateQueries({queryKey:["admin-support"]});},
    onError:(e:any)=>toast.error(e.message),
  });
  const tickets=data?.tickets??[];
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white flex items-center gap-2"><LifeBuoy size={18} className="text-blue-400"/>Support Tickets</h1>
        <div className="flex gap-1">
          {["open","closed","all"].map(s=>(
            <button key={s} onClick={()=>setFilter(s)} className={`px-3 py-1.5 rounded-lg text-sm capitalize transition-colors ${filter===s?"bg-blue-600 text-white":"text-slate-400 hover:text-white hover:bg-slate-800"}`}>{s}</button>
          ))}
        </div>
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        {isLoading?<div className="flex items-center justify-center py-14"><Loader2 size={20} className="animate-spin text-slate-600"/></div>
        :tickets.length===0?<div className="flex flex-col items-center gap-2 py-14 text-slate-600"><AlertCircle size={24} className="opacity-30"/><p className="text-sm">No {filter} tickets</p></div>
        :tickets.map((t:any)=>(
          <div key={t.id} className="flex items-start gap-4 px-5 py-4 border-b border-slate-800/50 last:border-0">
            <div className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${t.status==="open"?"bg-yellow-400":"bg-slate-600"}`}/>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">{t.subject}</p>
              <p className="text-xs text-slate-500 mt-0.5">{t.user_email} · {fmtDate(t.created_at)}</p>
              <p className="text-sm text-slate-400 mt-2 line-clamp-2">{t.body}</p>
            </div>
            {t.status==="open"&&(
              <button onClick={()=>closeMut.mutate(t.id)} className="flex-shrink-0 p-1.5 rounded-lg hover:bg-emerald-900/30 text-slate-500 hover:text-emerald-400 transition-colors"><CheckCircle2 size={15}/></button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
