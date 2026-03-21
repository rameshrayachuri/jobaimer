import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Bell, Shield, Trash2, AlertTriangle, Loader2, Check,
} from "lucide-react";
import { useAuthStore } from "../lib/store";
import { useNavigate } from "react-router-dom";
import { cn } from "../lib/utils";
import toast from "react-hot-toast";

export function SettingsPage() {
  const navigate = useNavigate();
  const { clearAuth } = useAuthStore();
  const [notifications, setNotifications] = useState({
    sms_on_interview: true,
    sms_on_offer: true,
    email_weekly_summary: true,
    email_application_errors: false,
  });
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const saveNotifMut = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/v1/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notification_preferences: notifications }),
      });
      if (!res.ok) throw new Error("Failed to save");
    },
    onSuccess: () => toast.success("Notifications updated"),
    onError: () => toast.error("Failed to save settings"),
  });

  const deleteAccountMut = useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/v1/profile", { method: "DELETE" });
      if (!res.ok) throw new Error("Failed");
    },
    onSuccess: () => {
      clearAuth();
      navigate("/");
      toast.success("Account deletion scheduled — you have 30 days to restore it.");
    },
    onError: () => toast.error("Deletion failed — please contact support"),
  });

  const sections = [
    {
      id: "notifications",
      icon: Bell,
      title: "Notifications",
      content: (
        <div className="space-y-4">
          {[
            { k: "sms_on_interview", label: "SMS when interview is scheduled", desc: "Get a text the moment an interview request comes in" },
            { k: "sms_on_offer", label: "SMS on offer received", desc: "Immediate SMS when an offer is detected" },
            { k: "email_weekly_summary", label: "Weekly email summary", desc: "A digest of applications, interviews, and offers" },
            { k: "email_application_errors", label: "Email on agent errors", desc: "Be notified if the agent encounters issues" },
          ].map(({ k, label, desc }) => (
            <div key={k} className="flex items-start gap-4">
              <button
                onClick={() => setNotifications((n) => ({ ...n, [k]: !(n as any)[k] }))}
                className={cn(
                  "mt-0.5 w-10 h-6 rounded-full flex-shrink-0 transition-colors relative",
                  (notifications as any)[k] ? "bg-primary" : "bg-muted"
                )}
              >
                <span className={cn(
                  "absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform",
                  (notifications as any)[k] && "translate-x-4"
                )} />
              </button>
              <div>
                <p className="text-sm font-medium">{label}</p>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </div>
            </div>
          ))}
          <button
            onClick={() => saveNotifMut.mutate()}
            disabled={saveNotifMut.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {saveNotifMut.isPending ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
            Save preferences
          </button>
        </div>
      ),
    },
    {
      id: "security",
      icon: Shield,
      title: "Security",
      content: (
        <div className="space-y-3 text-sm text-muted-foreground">
          <p>Your account uses 3-factor authentication: email, phone, and password.</p>
          <p>To change your password or phone number, sign out and use the "Forgot password" flow, or contact support.</p>
          <div className="p-3 rounded-xl bg-muted text-foreground">
            <p className="font-medium text-sm mb-1">Session security</p>
            <p className="text-xs text-muted-foreground">Access tokens expire every 60 minutes and are stored in memory only — never in localStorage or cookies.</p>
          </div>
        </div>
      ),
    },
    {
      id: "danger",
      icon: Trash2,
      title: "Danger zone",
      content: (
        <div className="space-y-4">
          <div className="p-4 rounded-xl border border-destructive/30 bg-destructive/5">
            <div className="flex items-start gap-3">
              <AlertTriangle size={16} className="text-destructive mt-0.5 flex-shrink-0" />
              <div className="space-y-2">
                <p className="text-sm font-medium">Delete account</p>
                <p className="text-xs text-muted-foreground">
                  Immediately stops the agent, removes your billing subscription, and schedules all data (applications, resumes, profile) for permanent deletion after a 30-day grace period. You can restore your account within 30 days by signing back in.
                </p>
              </div>
            </div>
          </div>
          <button
            onClick={() => setShowDeleteDialog(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-xl border border-destructive/50 text-destructive text-sm font-medium hover:bg-destructive/5 transition-colors"
          >
            <Trash2 size={14} />
            Delete my account
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>

      {sections.map(({ id, icon: Icon, title, content }) => (
        <motion.div
          key={id}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-card border border-border rounded-2xl overflow-hidden"
        >
          <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
            <Icon size={16} className="text-muted-foreground" />
            <h2 className="font-semibold text-sm">{title}</h2>
          </div>
          <div className="px-5 py-4">{content}</div>
        </motion.div>
      ))}

      {/* Delete confirmation dialog */}
      {showDeleteDialog && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-card border border-border rounded-2xl p-6 max-w-md w-full space-y-4"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-destructive/10 flex items-center justify-center">
                <AlertTriangle size={18} className="text-destructive" />
              </div>
              <h2 className="font-semibold">Confirm account deletion</h2>
            </div>
            <p className="text-sm text-muted-foreground">
              This will stop your agent and schedule all data for deletion. Type <strong>DELETE</strong> to confirm.
            </p>
            <input
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder="DELETE"
              className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-destructive/30"
            />
            <div className="flex gap-3">
              <button
                onClick={() => { setShowDeleteDialog(false); setDeleteConfirm(""); }}
                className="flex-1 py-2.5 rounded-xl border border-border text-sm font-medium hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteAccountMut.mutate()}
                disabled={deleteConfirm !== "DELETE" || deleteAccountMut.isPending}
                className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-destructive text-destructive-foreground text-sm font-medium hover:bg-destructive/90 disabled:opacity-50"
              >
                {deleteAccountMut.isPending ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                Delete account
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
