import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "../lib/api";
import { Search, UserX, UserCheck, Zap, ZapOff, Loader2, AlertCircle } from "lucide-react";
import toast from "react-hot-toast";
const fmtDate=(d:string)=>new Date(d).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});
export default function UsersPage() {
  const qc=useQueryClient();
  const [search,setSearch]=useState("");
  const [page,setPage]=useState(1);
  const {data,isLoading}=useQuery({
    queryKey:["admin-users",page,search],
    queryFn:()=>adminFetch(`/admin/v1/users?page=${page}&page_size=25${search?`&search=${encodeURIComponent(search)}`:""}`),
    placeholderData:(p:any)=>p,
  });
  const suspendMut=useMutation({
    mutationFn:({id,suspend}:{id:string;suspend:boolean})=>adminFetch(`/admin/v1/users/${id}/${suspend?"suspend":"unsuspend"}`,{method:"POST"}),
    onSuccess:()=>{toast.success("Updated");qc.invalidateQueries({queryKey:["admin-users"]});},
    onError:(e:any)=>toast.error(e.message),
  });
  const users=data?.users??[];
  return (
    <div className="p-6 max-w-6xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-white">Users</h1>
        <p className="text-sm text-slate-500">{data?.total??"—"} total</p>
      </div>
      <div className="relative max-w-sm">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500"/>
        <input value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}} placeholder="Search by email or name…"
          className="w-full pl-8 pr-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="hidden md:grid grid-cols-[1fr_120px_100px_80px_80px_48px] gap-4 px-5 py-3 border-b border-slate-800 text-[11px] font-medium text-slate-500 uppercase tracking-wide">
          <span>User</span><span>Plan</span><span>Status</span><span>Agent</span><span>Apps</span><span/>
        </div>
        {isLoading?<div className="flex items-center justify-center py-16"><Loader2 size={22} className="animate-spin text-slate-600"/></div>
        :users.length===0?<div className="flex flex-col items-center gap-2 py-14 text-slate-600"><AlertCircle size={28} className="opacity-30"/><p className="text-sm">No users found</p></div>
        :users.map((u:any)=>(
          <div key={u.id} className="grid grid-cols-1 md:grid-cols-[1fr_120px_100px_80px_80px_48px] gap-3 md:gap-4 px-5 py-3.5 border-b border-slate-800/50 last:border-0 hover:bg-slate-800/30 transition-colors items-center">
            <div>
              <p className="text-sm font-medium text-white">{u.full_name||u.email}</p>
              <p className="text-xs text-slate-500 mt-0.5">{u.email} · joined {fmtDate(u.created_at)}</p>
            </div>
            <span className="text-xs text-slate-400">{u.plan_id?.replace(/_/g," ")??"—"}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full w-fit ${u.sub_status==="active"?"bg-emerald-900/40 text-emerald-400":u.sub_status==="trialing"?"bg-blue-900/40 text-blue-400":"bg-slate-700 text-slate-400"}`}>{u.sub_status??"none"}</span>
            <div className="flex items-center gap-1">{u.agent_status==="active"?<Zap size={13} className="text-emerald-400"/>:<ZapOff size={13} className="text-slate-600"/>}<span className="text-xs text-slate-400">{u.agent_status}</span></div>
            <span className="text-sm text-slate-300">{u.total_applications}</span>
            <button onClick={()=>suspendMut.mutate({id:u.id,suspend:!u.is_suspended})} disabled={suspendMut.isPending}
              className={`p-1.5 rounded-lg transition-colors ${u.is_suspended?"hover:bg-emerald-900/30 text-slate-500 hover:text-emerald-400":"hover:bg-red-900/30 text-slate-500 hover:text-red-400"}`}>
              {u.is_suspended?<UserCheck size={14}/>:<UserX size={14}/>}
            </button>
          </div>
        ))}
      </div>
      {data&&(data.users?.length===25||page>1)&&(
        <div className="flex justify-end gap-2">
          <button onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1} className="px-3 py-1.5 text-sm rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-40 transition-colors">Previous</button>
          <button onClick={()=>setPage(p=>p+1)} disabled={data.users?.length<25} className="px-3 py-1.5 text-sm rounded-lg border border-slate-700 text-slate-400 hover:text-white hover:bg-slate-800 disabled:opacity-40 transition-colors">Next</button>
        </div>
      )}
    </div>
  );
}
