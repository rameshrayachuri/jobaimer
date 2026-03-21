import { useQuery } from "@tanstack/react-query";
import { Zap, ZapOff, Pause, Clock } from "lucide-react";
import { cn } from "../../lib/utils";
import { api } from "../../lib/api";

export function AgentStatusBadge() {
  const { data } = useQuery({
    queryKey: ["agent-status"],
    queryFn: () => api.get("/api/v1/agent/status"),
    refetchInterval: 15_000,
  });

  const status = data?.status ?? "inactive";

  const config = {
    active:   { icon: Zap,    label: "Agent active",  color: "text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20" },
    paused:   { icon: Pause,  label: "Agent paused",  color: "text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20" },
    stopped:  { icon: ZapOff, label: "Agent stopped", color: "text-slate-500 bg-muted" },
    inactive: { icon: Clock,  label: "Not running",   color: "text-slate-500 bg-muted" },
  }[status] ?? { icon: Clock, label: status, color: "text-slate-500 bg-muted" };

  const Icon = config.icon;
  return (
    <div className={cn("flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium", config.color)}>
      <Icon size={12} />
      {config.label}
      {status === "active" && data?.next_cycle_at && (
        <span className="ml-auto text-[10px] opacity-70">
          {new Date(data.next_cycle_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      )}
    </div>
  );
}
