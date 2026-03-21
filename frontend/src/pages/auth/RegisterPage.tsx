import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Eye, EyeOff, ArrowRight, Loader2, CheckCircle2 } from "lucide-react";
import { auth as authApi } from "../../lib/api";
import { cn } from "../../lib/utils";
import toast from "react-hot-toast";

const PW_RULES = [
  { label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { label: "One uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { label: "One number", test: (p: string) => /\d/.test(p) },
];

export function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ full_name: "", email: "", phone: "", password: "" });
  const [showPw, setShowPw] = useState(false);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const registerMut = useMutation({
    mutationFn: () => authApi.signUp(form),
    onSuccess: () => {
      toast.success("Account created! Please verify your email.");
      navigate(`/verify?email=${encodeURIComponent(form.email)}`);
    },
    onError: (e: any) => toast.error(e.message || "Registration failed"),
  });

  const pwStrength = PW_RULES.filter((r) => r.test(form.password)).length;
  const canSubmit = form.full_name && form.email && form.phone && pwStrength === PW_RULES.length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Start your free trial</h1>
        <p className="text-sm text-muted-foreground mt-1">14 days free — no credit card required</p>
      </div>

      <div className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Full name</label>
          <input
            value={form.full_name}
            onChange={set("full_name")}
            placeholder="Alex Chen"
            className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Email</label>
          <input
            type="email"
            value={form.email}
            onChange={set("email")}
            placeholder="you@example.com"
            className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Phone <span className="text-muted-foreground font-normal">(for OTP login + alerts)</span></label>
          <input
            type="tel"
            value={form.phone}
            onChange={set("phone")}
            placeholder="+1 555 000 0000"
            className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Password</label>
          <div className="relative">
            <input
              type={showPw ? "text" : "password"}
              value={form.password}
              onChange={set("password")}
              placeholder="••••••••"
              className="w-full px-3.5 py-2.5 pr-10 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <button
              type="button"
              onClick={() => setShowPw(!showPw)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            >
              {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>

          {/* Password strength */}
          {form.password && (
            <div className="space-y-1.5 mt-2">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className={cn(
                      "h-1 flex-1 rounded-full transition-colors",
                      i < pwStrength
                        ? pwStrength === 3 ? "bg-emerald-500" : pwStrength === 2 ? "bg-yellow-500" : "bg-red-500"
                        : "bg-muted"
                    )}
                  />
                ))}
              </div>
              <div className="space-y-1">
                {PW_RULES.map((rule) => (
                  <div key={rule.label} className={cn("flex items-center gap-1.5 text-xs", rule.test(form.password) ? "text-emerald-600" : "text-muted-foreground")}>
                    <CheckCircle2 size={11} className={rule.test(form.password) ? "opacity-100" : "opacity-30"} />
                    {rule.label}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <button
          onClick={() => registerMut.mutate()}
          disabled={registerMut.isPending || !canSubmit}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {registerMut.isPending ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
          {registerMut.isPending ? "Creating account…" : "Create account"}
        </button>
      </div>

      <p className="text-center text-xs text-muted-foreground">
        By signing up you agree to our{" "}
        <a href="/terms" className="underline hover:text-foreground">Terms</a> and{" "}
        <a href="/privacy" className="underline hover:text-foreground">Privacy Policy</a>.
      </p>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link to="/login" className="text-primary font-medium hover:underline">Sign in</Link>
      </p>
    </div>
  );
}
