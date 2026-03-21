import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Eye, EyeOff, Mail, Phone, ArrowRight, Loader2 } from "lucide-react";
import { auth as authApi, setAccessToken } from "../../lib/api";
import { useAuthStore } from "../../lib/store";
import { cn } from "../../lib/utils";
import toast from "react-hot-toast";

type LoginMethod = "email" | "phone";

export function LoginPage() {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [method, setMethod] = useState<LoginMethod>("email");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");

  const signInMut = useMutation({
    mutationFn: () => authApi.signIn(identifier, password),
    onSuccess: (data) => {
      setAccessToken(data.access_token);
      setAuth(data.user, data.access_token, data.refresh_token);
      navigate("/dashboard");
    },
    onError: (e: any) => toast.error(e.message || "Sign in failed"),
  });

  const sendOtpMut = useMutation({
    mutationFn: () => authApi.sendOtp(identifier),
    onSuccess: () => { setOtpSent(true); toast.success("OTP sent to your phone"); },
    onError: (e: any) => toast.error(e.message || "Failed to send OTP"),
  });

  const verifyOtpMut = useMutation({
    mutationFn: () => authApi.verifyOtp(identifier, otp),
    onSuccess: (data) => {
      setAccessToken(data.access_token);
      navigate("/dashboard");
    },
    onError: (e: any) => toast.error(e.message || "Invalid OTP"),
  });

  const isEmail = method === "email";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Welcome back</h1>
        <p className="text-sm text-muted-foreground mt-1">Sign in to your JobAimer account</p>
      </div>

      {/* Method toggle */}
      <div className="flex rounded-xl border border-border p-1 gap-1">
        {(["email", "phone"] as LoginMethod[]).map((m) => (
          <button
            key={m}
            onClick={() => { setMethod(m); setOtpSent(false); setIdentifier(""); }}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors",
              method === m ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            {m === "email" ? <Mail size={14} /> : <Phone size={14} />}
            {m === "email" ? "Email" : "Phone / OTP"}
          </button>
        ))}
      </div>

      {isEmail ? (
        /* ── Email + password flow ── */
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Email</label>
            <input
              type="email"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && signInMut.mutate()}
              placeholder="you@example.com"
              className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Password</label>
            <div className="relative">
              <input
                type={showPw ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && signInMut.mutate()}
                placeholder="••••••••"
                className="w-full px-3.5 py-2.5 pr-10 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>
          <button
            onClick={() => signInMut.mutate()}
            disabled={signInMut.isPending || !identifier || !password}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {signInMut.isPending ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
            {signInMut.isPending ? "Signing in…" : "Sign in"}
          </button>
        </div>
      ) : (
        /* ── Phone + OTP flow ── */
        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Phone number</label>
            <input
              type="tel"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="+1 555 000 0000"
              className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          {otpSent && (
            <div className="space-y-1.5">
              <label className="text-sm font-medium">One-time code</label>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                placeholder="123456"
                className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm tracking-widest text-center focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          )}
          {!otpSent ? (
            <button
              onClick={() => sendOtpMut.mutate()}
              disabled={sendOtpMut.isPending || !identifier}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {sendOtpMut.isPending ? <Loader2 size={15} className="animate-spin" /> : <Phone size={15} />}
              {sendOtpMut.isPending ? "Sending…" : "Send OTP"}
            </button>
          ) : (
            <button
              onClick={() => verifyOtpMut.mutate()}
              disabled={verifyOtpMut.isPending || otp.length < 6}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {verifyOtpMut.isPending ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
              {verifyOtpMut.isPending ? "Verifying…" : "Verify & Sign in"}
            </button>
          )}
        </div>
      )}

      <p className="text-center text-sm text-muted-foreground">
        Don't have an account?{" "}
        <Link to="/register" className="text-primary font-medium hover:underline">Start free trial</Link>
      </p>
    </div>
  );
}
