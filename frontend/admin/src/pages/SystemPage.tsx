import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { adminFetch } from "../lib/api";
import {
  Settings2, CheckCircle2, XCircle, Loader2, RefreshCw,
  Shield, Key, AlertTriangle, ChevronRight, Clock, Info,
} from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import toast from "react-hot-toast";

const cn = (...i: any[]) => twMerge(clsx(i));

function HealthRow({ name, status, latency }: { name: string; status: string; latency?: number }) {
  const ok = status === "healthy";
  return (
    <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800/50 last:border-0">
      {ok
        ? <CheckCircle2 size={15} className="text-emerald-400 flex-shrink-0" />
        : <XCircle size={15} className="text-red-400 flex-shrink-0" />}
      <span className="flex-1 text-sm text-slate-300">{name}</span>
      {latency != null && (
        <span className="text-xs text-slate-500">{latency}ms</span>
      )}
      <span className={cn(
        "text-xs px-2 py-0.5 rounded-full capitalize",
        ok ? "bg-emerald-900/40 text-emerald-400" : "bg-red-900/40 text-red-400"
      )}>
        {status}
      </span>
    </div>
  );
}

function ConfigRow({ label, value, masked }: { label: string; value: string; masked?: boolean }) {
  const [show, setShow] = useState(false);
  const display = masked && !show ? "•".repeat(Math.min(value.length, 20)) : value;
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-800/50 last:border-0">
      <span className="text-xs text-slate-500 w-48 flex-shrink-0">{label}</span>
      <span className="flex-1 text-xs text-slate-300 font-mono truncate">{display}</span>
      {masked && (
        <button
          onClick={() => setShow((s) => !s)}
          className="text-xs text-slate-600 hover:text-slate-400 transition-colors flex-shrink-0"
        >
          {show ? "hide" : "reveal"}
        </button>
      )}
    </div>
  );
}

export default function SystemPage() {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin-system"],
    queryFn: () => adminFetch("/admin/v1/system"),
    refetchInterval: 60_000,
  });

  const purgeCacheMut = useMutation({
    mutationFn: () => adminFetch("/admin/v1/system/cache/purge", { method: "POST" }),
    onSuccess: () => toast.success("Cache purged"),
    onError: (e: any) => toast.error(e.message),
  });

  const health: any = data?.health ?? {};
  const config: any = data?.config ?? {};
  const buildInfo: any = data?.build_info ?? {};

  const healthChecks = [
    { name: "PostgreSQL (Supabase)", status: health.database ?? "unknown", latency: health.db_latency_ms },
    { name: "Supabase Auth", status: health.supabase_auth ?? "unknown" },
    { name: "AWS S3 (Resumes)", status: health.s3 ?? "unknown", latency: health.s3_latency_ms },
    { name: "Temporal Cloud", status: health.temporal ?? "unknown" },
    { name: "Anthropic API", status: health.anthropic ?? "unknown", latency: health.anthropic_latency_ms },
    { name: "Stripe", status: health.stripe ?? "unknown" },
  ];

  const healthyCount = healthChecks.filter((h) => h.status === "healthy").length;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <Settings2 size={18} className="text-slate-400" />
            System
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {healthyCount}/{healthChecks.length} services healthy
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white text-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw size={13} className={isFetching ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Loader2 size={24} className="animate-spin text-slate-600" />
        </div>
      ) : (
        <>
          {/* Health checks */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
              <CheckCircle2 size={14} className="text-slate-500" />
              <span className="text-sm font-medium text-slate-300">Service Health</span>
              <span className={cn(
                "ml-auto text-xs px-2 py-0.5 rounded-full",
                healthyCount === healthChecks.length
                  ? "bg-emerald-900/40 text-emerald-400"
                  : "bg-yellow-900/40 text-yellow-400"
              )}>
                {healthyCount}/{healthChecks.length} healthy
              </span>
            </div>
            {healthChecks.map((h) => (
              <HealthRow key={h.name} {...h} />
            ))}
          </div>

          {/* Build info */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
              <Info size={14} className="text-slate-500" />
              <span className="text-sm font-medium text-slate-300">Build Info</span>
            </div>
            <div className="divide-y divide-slate-800/50">
              {[
                { label: "Environment", value: buildInfo.environment ?? config.environment ?? "production" },
                { label: "API Version", value: buildInfo.api_version ?? "—" },
                { label: "Commit SHA", value: buildInfo.commit_sha ?? "—" },
                { label: "Deployed At", value: buildInfo.deployed_at ? new Date(buildInfo.deployed_at).toLocaleString() : "—" },
                { label: "Python Version", value: buildInfo.python_version ?? "—" },
                { label: "Region", value: config.aws_region ?? "us-east-1" },
              ].map((r) => (
                <ConfigRow key={r.label} label={r.label} value={String(r.value)} />
              ))}
            </div>
          </div>

          {/* Configuration */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
              <Key size={14} className="text-slate-500" />
              <span className="text-sm font-medium text-slate-300">Configuration</span>
              <span className="ml-auto text-xs text-slate-600 flex items-center gap-1">
                <Shield size={10} /> Sensitive values masked
              </span>
            </div>
            <div className="divide-y divide-slate-800/50">
              {[
                { label: "S3 Bucket", value: config.s3_bucket ?? "—" },
                { label: "Temporal Namespace", value: config.temporal_namespace ?? "—" },
                { label: "Temporal Task Queue", value: config.temporal_task_queue ?? "—" },
                { label: "Supabase URL", value: config.supabase_url ?? "—" },
                { label: "Anthropic Model", value: config.anthropic_model ?? "claude-sonnet-4-20250514" },
                { label: "Stripe Webhook Secret", value: config.stripe_webhook_configured ? "configured" : "not set", masked: false },
                { label: "Admin OIDC Secret", value: "••••••••••••", masked: true },
                { label: "Cycle Interval", value: config.cycle_interval_hours ? `${config.cycle_interval_hours}h` : "4h" },
                { label: "ATS Threshold", value: config.ats_threshold ? `${(config.ats_threshold * 100).toFixed(0)}%` : "65%" },
                { label: "Resume Retention", value: config.resume_retention_months ? `${config.resume_retention_months} months` : "6 months" },
              ].map((r) => (
                <ConfigRow key={r.label} label={r.label} value={r.value} masked={r.masked} />
              ))}
            </div>
          </div>

          {/* Scheduled jobs */}
          {data?.scheduled_jobs && (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
              <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-2">
                <Clock size={14} className="text-slate-500" />
                <span className="text-sm font-medium text-slate-300">Temporal Schedules</span>
              </div>
              {(data.scheduled_jobs as any[]).map((job: any) => (
                <div key={job.id} className="flex items-center gap-3 px-4 py-3 border-b border-slate-800/50 last:border-0">
                  <div className={cn("w-2 h-2 rounded-full flex-shrink-0", job.running ? "bg-emerald-400 animate-pulse" : "bg-slate-700")} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-300">{job.name}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{job.schedule}</p>
                  </div>
                  <div className="text-right text-xs text-slate-500">
                    {job.last_run && <div>Last: {new Date(job.last_run).toLocaleTimeString()}</div>}
                    {job.next_run && <div>Next: {new Date(job.next_run).toLocaleTimeString()}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Danger zone */}
          <div className="bg-slate-900 border border-red-900/40 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-red-900/30 flex items-center gap-2">
              <AlertTriangle size={14} className="text-red-400" />
              <span className="text-sm font-medium text-red-400">Danger Zone</span>
            </div>
            <div className="p-4 space-y-3">
              <div className="flex items-center justify-between gap-4 p-3 rounded-xl border border-slate-800">
                <div>
                  <p className="text-sm text-slate-300">Purge API Cache</p>
                  <p className="text-xs text-slate-500 mt-0.5">Clear all Redis/in-memory caches. Users may see slower responses briefly.</p>
                </div>
                <button
                  onClick={() => {
                    if (confirm("Purge all API caches?")) purgeCacheMut.mutate();
                  }}
                  disabled={purgeCacheMut.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-800 text-red-400 hover:bg-red-900/20 text-sm transition-colors disabled:opacity-50 flex-shrink-0"
                >
                  {purgeCacheMut.isPending
                    ? <><Loader2 size={12} className="animate-spin" /> Purging…</>
                    : <><ChevronRight size={13} /> Purge Cache</>
                  }
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
