import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { adminFetch } from "../lib/api";
import {
  Tag, Plus, ChevronDown, ChevronUp, Shuffle, Power,
  Copy, Check, Receipt, Loader2, AlertCircle, X, Search,
} from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import toast from "react-hot-toast";

const cn = (...i: any[]) => twMerge(clsx(i));

// ─── Types ────────────────────────────────────────────────────────────────────
interface Coupon {
  id: string;
  name: string;
  discount_type: "percent_off" | "amount_off";
  percent_off: number | null;
  amount_off_cents: number | null;
  duration: "once" | "repeating" | "forever";
  duration_in_months: number | null;
  max_redemptions: number | null;
  redemptions_count: number;
  valid_from: string;
  valid_until: string | null;
  is_active: boolean;
  stripe_coupon_id: string;
  promo_code_count: number;
}

interface Redemption {
  id: string;
  user_id: string;
  plan_id: string;
  original: number;
  discount: number;
  final: number;
  redeemed_at: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmt = (cents: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0 }).format(cents / 100);

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

function DiscountLabel({ c }: { c: Coupon }) {
  const val = c.discount_type === "percent_off"
    ? `${c.percent_off}% off`
    : `${fmt(c.amount_off_cents!)} off`;
  const dur = c.duration === "forever" ? "forever"
    : c.duration === "once" ? "once"
    : `${c.duration_in_months}mo`;
  return <span className="font-mono text-emerald-400">{val} · {dur}</span>;
}

// ─── Create Coupon Modal ──────────────────────────────────────────────────────
function CreateCouponModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    name: "",
    description: "",
    discount_type: "percent_off" as "percent_off" | "amount_off",
    percent_off: "20",
    amount_off_cents: "1900",
    currency: "usd",
    duration: "once" as "once" | "repeating" | "forever",
    duration_in_months: "3",
    max_redemptions: "",
    valid_until: "",
    promo_codes: "",
  });

  const mut = useMutation({
    mutationFn: () =>
      adminFetch("/admin/v1/coupons", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          description: form.description || null,
          discount_type: form.discount_type,
          percent_off: form.discount_type === "percent_off" ? parseFloat(form.percent_off) : null,
          amount_off_cents: form.discount_type === "amount_off" ? parseInt(form.amount_off_cents) : null,
          currency: form.currency,
          duration: form.duration,
          duration_in_months: form.duration === "repeating" ? parseInt(form.duration_in_months) : null,
          max_redemptions: form.max_redemptions ? parseInt(form.max_redemptions) : null,
          valid_until: form.valid_until ? new Date(form.valid_until).toISOString() : null,
          promo_codes: form.promo_codes
            .split(/[\s,]+/)
            .map((s) => s.trim().toUpperCase())
            .filter(Boolean),
        }),
      }),
    onSuccess: () => {
      toast.success("Coupon created");
      onCreated();
      onClose();
    },
    onError: (e: any) => toast.error(e.message),
  });

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl overflow-y-auto max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Tag size={16} className="text-blue-400" />
            <h2 className="font-semibold text-white">New Coupon</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors">
            <X size={16} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {/* Name */}
          <Field label="Coupon Name *">
            <input value={form.name} onChange={set("name")} placeholder="e.g. LAUNCH50 — 50% off first month"
              className={inputCls} />
          </Field>

          {/* Discount type */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Discount Type">
              <select value={form.discount_type} onChange={set("discount_type")} className={inputCls}>
                <option value="percent_off">Percent Off</option>
                <option value="amount_off">Amount Off</option>
              </select>
            </Field>
            {form.discount_type === "percent_off" ? (
              <Field label="Percent Off">
                <input type="number" min="1" max="100" value={form.percent_off} onChange={set("percent_off")}
                  placeholder="20" className={inputCls} />
              </Field>
            ) : (
              <Field label="Amount Off (cents)">
                <input type="number" min="1" value={form.amount_off_cents} onChange={set("amount_off_cents")}
                  placeholder="1900 = $19" className={inputCls} />
              </Field>
            )}
          </div>

          {/* Duration */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Duration">
              <select value={form.duration} onChange={set("duration")} className={inputCls}>
                <option value="once">Once</option>
                <option value="repeating">Repeating</option>
                <option value="forever">Forever</option>
              </select>
            </Field>
            {form.duration === "repeating" && (
              <Field label="Duration (months)">
                <input type="number" min="1" value={form.duration_in_months} onChange={set("duration_in_months")}
                  placeholder="3" className={inputCls} />
              </Field>
            )}
          </div>

          {/* Limits */}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Max Redemptions" hint="Leave blank for unlimited">
              <input type="number" min="1" value={form.max_redemptions} onChange={set("max_redemptions")}
                placeholder="Unlimited" className={inputCls} />
            </Field>
            <Field label="Expires" hint="Leave blank = never">
              <input type="date" value={form.valid_until} onChange={set("valid_until")} className={inputCls} />
            </Field>
          </div>

          {/* Promo codes */}
          <Field label="Promo Codes" hint="Space or comma separated. Leave blank to auto-generate later.">
            <textarea value={form.promo_codes} onChange={set("promo_codes") as any}
              placeholder="LAUNCH50 BETA20 FRIEND10"
              rows={2}
              className={cn(inputCls, "resize-none")} />
          </Field>
        </div>

        <div className="px-6 pb-5 flex gap-3 justify-end">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
            Cancel
          </button>
          <button
            onClick={() => mut.mutate()}
            disabled={!form.name || mut.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors disabled:opacity-40"
          >
            {mut.isPending && <Loader2 size={14} className="animate-spin" />}
            Create Coupon
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Coupon Row ───────────────────────────────────────────────────────────────
function CouponRow({ coupon, onRefresh }: { coupon: Coupon; onRefresh: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [generatedCode, setGeneratedCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const deactivateMut = useMutation({
    mutationFn: () => adminFetch(`/admin/v1/coupons/${coupon.id}/deactivate`, { method: "POST" }),
    onSuccess: () => { toast.success("Coupon deactivated"); onRefresh(); },
    onError: (e: any) => toast.error(e.message),
  });

  const generateMut = useMutation({
    mutationFn: () => adminFetch(`/admin/v1/coupons/${coupon.id}/promo-codes/generate`, { method: "POST" }),
    onSuccess: (data) => {
      setGeneratedCode(data.code);
      onRefresh();
    },
    onError: (e: any) => toast.error(e.message),
  });

  const { data: redemptions, refetch: fetchRedemptions, isFetching: loadingRedemptions } = useQuery({
    queryKey: ["coupon-redemptions", coupon.id],
    queryFn: () => adminFetch(`/admin/v1/coupons/${coupon.id}/redemptions`),
    enabled: false,
  });

  function handleExpand() {
    setExpanded((e) => !e);
    if (!expanded) fetchRedemptions();
  }

  async function copyCode(code: string) {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  const usagePercent = coupon.max_redemptions
    ? Math.round((coupon.redemptions_count / coupon.max_redemptions) * 100)
    : null;

  return (
    <div className="border border-slate-800 rounded-xl overflow-hidden">
      {/* Header row */}
      <div className="flex items-center gap-4 px-5 py-4 bg-slate-900 hover:bg-slate-800/50 transition-colors">
        {/* Active indicator */}
        <div className={cn("w-2 h-2 rounded-full flex-shrink-0", coupon.is_active ? "bg-emerald-400" : "bg-slate-600")} />

        {/* Name + discount */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-white text-sm">{coupon.name}</p>
            <DiscountLabel c={coupon} />
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            {coupon.promo_code_count} code{coupon.promo_code_count !== 1 ? "s" : ""}
            {coupon.valid_until && ` · expires ${fmtDate(coupon.valid_until)}`}
            {coupon.stripe_coupon_id && (
              <span className="ml-2 font-mono opacity-50">{coupon.stripe_coupon_id}</span>
            )}
          </p>
        </div>

        {/* Redemptions */}
        <div className="text-right text-sm hidden sm:block">
          <p className="text-white font-medium">{coupon.redemptions_count}</p>
          {coupon.max_redemptions && (
            <p className="text-xs text-slate-500">/ {coupon.max_redemptions}</p>
          )}
        </div>

        {/* Usage bar */}
        {usagePercent !== null && (
          <div className="w-20 hidden md:block">
            <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className={cn("h-full rounded-full", usagePercent >= 90 ? "bg-red-400" : usagePercent >= 70 ? "bg-yellow-400" : "bg-emerald-400")}
                style={{ width: `${usagePercent}%` }}
              />
            </div>
            <p className="text-[10px] text-slate-500 mt-0.5">{usagePercent}%</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-1">
          {coupon.is_active && (
            <>
              <button
                onClick={() => generateMut.mutate()}
                disabled={generateMut.isPending}
                title="Generate promo code"
                className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
              >
                {generateMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Shuffle size={14} />}
              </button>
              <button
                onClick={() => {
                  if (confirm(`Deactivate "${coupon.name}"?`)) deactivateMut.mutate();
                }}
                disabled={deactivateMut.isPending}
                title="Deactivate coupon"
                className="p-1.5 rounded-lg hover:bg-red-900/40 text-slate-400 hover:text-red-400 transition-colors"
              >
                {deactivateMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Power size={14} />}
              </button>
            </>
          )}
          <button
            onClick={handleExpand}
            className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      </div>

      {/* Generated code flash */}
      {generatedCode && (
        <div className="flex items-center gap-3 px-5 py-2.5 bg-emerald-900/20 border-t border-emerald-800/40">
          <Check size={14} className="text-emerald-400" />
          <span className="text-sm text-slate-300">Generated: </span>
          <code className="font-mono text-emerald-300 font-bold">{generatedCode}</code>
          <button
            onClick={() => copyCode(generatedCode)}
            className="ml-auto flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Copied!" : "Copy"}
          </button>
          <button onClick={() => setGeneratedCode(null)} className="text-slate-600 hover:text-slate-400">
            <X size={12} />
          </button>
        </div>
      )}

      {/* Expanded: redemptions */}
      {expanded && (
        <div className="border-t border-slate-800 px-5 py-4">
          <div className="flex items-center gap-2 mb-3">
            <Receipt size={13} className="text-slate-500" />
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wide">Redemptions</span>
          </div>
          {loadingRedemptions ? (
            <div className="flex items-center gap-2 text-slate-500 text-sm py-3">
              <Loader2 size={14} className="animate-spin" /> Loading…
            </div>
          ) : redemptions?.redemptions?.length === 0 ? (
            <p className="text-sm text-slate-600 py-3">No redemptions yet.</p>
          ) : (
            <div className="space-y-1 max-h-56 overflow-y-auto">
              <div className="grid grid-cols-[1fr_80px_80px_80px_100px] gap-2 text-[11px] text-slate-500 uppercase tracking-wide pb-1 border-b border-slate-800">
                <span>User</span><span>Plan</span><span>Original</span><span>Discount</span><span>Redeemed</span>
              </div>
              {redemptions?.redemptions?.map((r: Redemption) => (
                <div key={r.id} className="grid grid-cols-[1fr_80px_80px_80px_100px] gap-2 text-xs text-slate-300 py-1">
                  <span className="font-mono text-slate-400 truncate">{r.user_id.slice(0, 8)}…</span>
                  <span>{r.plan_id.replace("_", " ")}</span>
                  <span>{fmt(r.original)}</span>
                  <span className="text-emerald-400">-{fmt(r.discount)}</span>
                  <span className="text-slate-500">{fmtDate(r.redeemed_at)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Field helper ─────────────────────────────────────────────────────────────
const inputCls = "w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500";

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-medium text-slate-400">{label}</label>
      {children}
      {hint && <p className="text-[11px] text-slate-600">{hint}</p>}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function CouponsPage() {
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-coupons"],
    queryFn: () => adminFetch("/admin/v1/coupons"),
    refetchInterval: 30_000,
  });

  const coupons: Coupon[] = data?.coupons ?? [];
  const filtered = coupons
    .filter((c) => showInactive || c.is_active)
    .filter(
      (c) =>
        !search ||
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.stripe_coupon_id.toLowerCase().includes(search.toLowerCase())
    );

  const totalRedemptions = coupons.reduce((s, c) => s + c.redemptions_count, 0);
  const activeCoupons = coupons.filter((c) => c.is_active).length;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-white flex items-center gap-2">
            <Tag size={18} className="text-blue-400" />
            Coupons
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {activeCoupons} active · {totalRedemptions} total redemptions
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors"
        >
          <Plus size={15} />
          New Coupon
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Active Coupons", value: activeCoupons },
          { label: "Total Codes", value: coupons.reduce((s, c) => s + c.promo_code_count, 0) },
          { label: "Redemptions", value: totalRedemptions },
        ].map(({ label, value }) => (
          <div key={label} className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="text-2xl font-semibold text-white mt-0.5">{value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search coupons…"
            className="w-full pl-8 pr-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-slate-600 bg-slate-800 text-blue-500 focus:ring-blue-500" />
          Show inactive
        </label>
      </div>

      {/* List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={24} className="animate-spin text-slate-600" />
        </div>
      ) : error ? (
        <div className="flex items-center gap-2 text-red-400 py-8 justify-center">
          <AlertCircle size={16} />
          <span className="text-sm">Failed to load coupons</span>
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-slate-600">
          <Tag size={36} className="opacity-30" />
          <p className="text-sm">{search ? "No matching coupons" : "No coupons yet — create your first"}</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((c) => (
            <CouponRow key={c.id} coupon={c} onRefresh={() => qc.invalidateQueries({ queryKey: ["admin-coupons"] })} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateCouponModal
          onClose={() => setShowCreate(false)}
          onCreated={() => qc.invalidateQueries({ queryKey: ["admin-coupons"] })}
        />
      )}
    </div>
  );
}
