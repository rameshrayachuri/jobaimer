import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  User, FileText, Target, Upload, Trash2, Download,
  Loader2, Save, ExternalLink, AlertCircle,
} from "lucide-react";
import { profile as profileApi, applications as appApi } from "../lib/api";
import { cn, formatDate } from "../lib/utils";
import toast from "react-hot-toast";

type Tab = "profile" | "resume" | "targets";

export function ProfilePage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("profile");
  const [form, setForm] = useState<any>({});
  const [dirty, setDirty] = useState(false);

  const { data: prof, isLoading } = useQuery({
    queryKey: ["profile"],
    queryFn: profileApi.get,
  });

  useEffect(() => {
    if (prof) { setForm(prof); setDirty(false); }
  }, [prof]);

  const set = (k: string, v: any) => {
    setForm((f: any) => ({ ...f, [k]: v }));
    setDirty(true);
  };

  const saveMut = useMutation({
    mutationFn: () => profileApi.update(form),
    onSuccess: () => { toast.success("Profile saved"); qc.invalidateQueries({ queryKey: ["profile"] }); setDirty(false); },
    onError: (e: any) => toast.error(e.message || "Save failed"),
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => profileApi.uploadResume(file),
    onSuccess: () => { toast.success("Resume uploaded"); qc.invalidateQueries({ queryKey: ["profile"] }); },
    onError: (e: any) => toast.error(e.message || "Upload failed"),
  });

  const tabs = [
    { id: "profile" as Tab, icon: User, label: "Profile" },
    { id: "resume" as Tab, icon: FileText, label: "Resume" },
    { id: "targets" as Tab, icon: Target, label: "Job Targets" },
  ];

  if (isLoading) {
    return <div className="p-6"><div className="h-96 rounded-2xl bg-muted animate-pulse" /></div>;
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Profile</h1>
        {dirty && (
          <button
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {saveMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Save changes
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-muted p-1 rounded-xl">
        {tabs.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors",
              tab === id ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab panels */}
      <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        {tab === "profile" && (
          <div className="bg-card border border-border rounded-2xl p-6 space-y-5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { k: "full_name", label: "Full name", placeholder: "Alex Chen" },
                { k: "email", label: "Email", placeholder: "you@example.com", disabled: true },
                { k: "phone", label: "Phone", placeholder: "+1 555 000 0000", disabled: true },
                { k: "location", label: "Location", placeholder: "San Francisco, CA" },
                { k: "linkedin_url", label: "LinkedIn", placeholder: "https://linkedin.com/in/..." },
                { k: "github_url", label: "GitHub", placeholder: "https://github.com/..." },
              ].map(({ k, label, placeholder, disabled }) => (
                <div key={k} className="space-y-1.5">
                  <label className="text-sm font-medium">{label}</label>
                  <input
                    value={form[k] || ""}
                    onChange={(e) => !disabled && set(k, e.target.value)}
                    placeholder={placeholder}
                    disabled={disabled}
                    className={cn(
                      "w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30",
                      disabled && "opacity-50 cursor-not-allowed"
                    )}
                  />
                </div>
              ))}
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">Seniority level</label>
              <select
                value={form.seniority_level || "mid"}
                onChange={(e) => set("seniority_level", e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                {["junior", "mid", "senior", "lead", "staff", "principal"].map((l) => (
                  <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {tab === "resume" && (
          <div className="space-y-4">
            {/* Upload zone */}
            <label className={cn(
              "flex flex-col items-center gap-3 p-8 rounded-2xl border-2 border-dashed cursor-pointer transition-colors bg-card",
              "hover:border-primary/50 hover:bg-primary/5"
            )}>
              <input
                type="file"
                accept=".pdf,.docx,.doc"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) uploadMut.mutate(f);
                }}
              />
              {uploadMut.isPending ? (
                <Loader2 size={28} className="text-primary animate-spin" />
              ) : (
                <Upload size={28} className="text-muted-foreground" />
              )}
              <div className="text-center">
                <p className="font-medium text-sm">{uploadMut.isPending ? "Uploading & parsing…" : "Upload new resume"}</p>
                <p className="text-xs text-muted-foreground">PDF or DOCX · Max 10MB</p>
              </div>
            </label>

            {/* Parsed data preview */}
            {form.resume_parsed_at && (
              <div className="bg-card border border-border rounded-2xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">Master resume</p>
                    <p className="text-xs text-muted-foreground">Uploaded {formatDate(form.resume_parsed_at)}</p>
                  </div>
                  <div className="flex gap-2">
                    <button className="p-2 rounded-lg hover:bg-muted transition-colors">
                      <Download size={15} className="text-muted-foreground" />
                    </button>
                  </div>
                </div>
                <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 text-sm">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  <span className="text-emerald-700 dark:text-emerald-400">Parsed and ready for tailoring</span>
                </div>
              </div>
            )}

            <div className="flex items-start gap-3 p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-sm border border-blue-100 dark:border-blue-800">
              <AlertCircle size={15} className="text-blue-600 mt-0.5 flex-shrink-0" />
              <p className="text-blue-700 dark:text-blue-300">
                Tailored resume versions are stored for 6 months then automatically deleted. You can delete them anytime from the Applications page.
              </p>
            </div>
          </div>
        )}

        {tab === "targets" && (
          <div className="bg-card border border-border rounded-2xl p-6 space-y-6">
            {/* Target titles */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Target job titles</label>
              {(form.target_titles || [""]).map((t: string, i: number) => (
                <div key={i} className="flex gap-2">
                  <input
                    value={t}
                    onChange={(e) => {
                      const next = [...(form.target_titles || [])];
                      next[i] = e.target.value;
                      set("target_titles", next);
                    }}
                    placeholder="e.g. Senior Software Engineer"
                    className="flex-1 px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {i > 0 && (
                    <button
                      onClick={() => set("target_titles", form.target_titles.filter((_: any, j: number) => j !== i))}
                      className="p-2 rounded-xl border border-border hover:bg-muted"
                    >
                      <Trash2 size={14} className="text-muted-foreground" />
                    </button>
                  )}
                </div>
              ))}
              {(form.target_titles || []).length < 5 && (
                <button
                  onClick={() => set("target_titles", [...(form.target_titles || []), ""])}
                  className="text-sm text-primary hover:underline"
                >
                  + Add title
                </button>
              )}
            </div>

            {/* Remote */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Remote preference</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { v: "remote_only", l: "Remote only" },
                  { v: "remote_ok", l: "Remote ok" },
                  { v: "onsite_only", l: "On-site" },
                ].map(({ v, l }) => (
                  <button
                    key={v}
                    onClick={() => set("remote_preference", v)}
                    className={cn(
                      "py-2 rounded-xl border text-sm font-medium transition-colors",
                      form.remote_preference === v ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"
                    )}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>

            {/* Salary */}
            <div className="grid grid-cols-2 gap-4">
              {[
                { k: "salary_min", l: "Min salary ($/yr)" },
                { k: "salary_max", l: "Max salary ($/yr)" },
              ].map(({ k, l }) => (
                <div key={k} className="space-y-1.5">
                  <label className="text-sm font-medium">{l}</label>
                  <input
                    type="number"
                    value={form[k] || ""}
                    onChange={(e) => set(k, Number(e.target.value))}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
              ))}
            </div>

            {/* Excluded companies */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Exclude companies <span className="text-muted-foreground font-normal">(comma-separated)</span></label>
              <input
                value={(form.excluded_companies || []).join(", ")}
                onChange={(e) => set("excluded_companies", e.target.value.split(",").map((s: string) => s.trim()).filter(Boolean))}
                placeholder="Acme Corp, MegaCorp..."
                className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
