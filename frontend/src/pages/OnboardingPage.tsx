import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import {
  User, Target, FileText, Tag, CreditCard, Zap,
  ArrowRight, ArrowLeft, Check, Loader2, Upload, X,
} from "lucide-react";
import { profile as profileApi, billing as billingApi } from "../lib/api";
import { cn } from "../lib/utils";
import toast from "react-hot-toast";

const STEPS = [
  { id: "profile",  icon: User,       title: "Your profile",      subtitle: "Tell us about yourself" },
  { id: "targets",  icon: Target,     title: "Job targets",        subtitle: "What are you looking for?" },
  { id: "resume",   icon: FileText,   title: "Upload resume",      subtitle: "We'll tailor it for each job" },
  { id: "coupon",   icon: Tag,        title: "Have a promo code?", subtitle: "Optional — skip if none" },
  { id: "billing",  icon: CreditCard, title: "Choose your plan",   subtitle: "14-day free trial on all plans" },
  { id: "activate", icon: Zap,        title: "You're all set!",    subtitle: "Activate the agent to start" },
];

const PLANS = [
  {
    id: "starter_monthly", name: "Starter", price: "$19", period: "/mo",
    features: ["20 applications / cycle", "7 portals", "AI resume tailoring (3 passes)", "Email alerts"],
  },
  {
    id: "pro_monthly", name: "Pro", price: "$39", period: "/mo",
    features: ["50 applications / cycle", "All portals", "AI resume tailoring (5 passes)", "SMS + Email alerts"],
    popular: true,
  },
];

export function OnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [profileData, setProfileData] = useState({
    full_name: "", location: "", linkedin_url: "", seniority_level: "mid",
  });
  const [targets, setTargets] = useState({
    target_titles: [""], preferred_locations: ["Remote"], remote_preference: "remote_ok",
    salary_min: 80000, salary_max: 150000,
  });
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [promoCode, setPromoCode] = useState("");
  const [couponValidation, setCouponValidation] = useState<any>(null);
  const [selectedPlan, setSelectedPlan] = useState("pro_monthly");

  const saveProfMut = useMutation({
    mutationFn: () => profileApi.update({ ...profileData, ...targets }),
    onSuccess: () => next(),
    onError: (e: any) => toast.error(e.message),
  });

  const uploadResumeMut = useMutation({
    mutationFn: () => profileApi.uploadResume(resumeFile!),
    onSuccess: () => next(),
    onError: (e: any) => toast.error(e.message),
  });

  const validateCouponMut = useMutation({
    mutationFn: () => billingApi.validateCoupon(promoCode, selectedPlan),
    onSuccess: (data) => { setCouponValidation(data); toast.success(`Discount applied: ${data.savings_label}`); },
    onError: () => toast.error("Invalid or expired code"),
  });

  const checkoutMut = useMutation({
    mutationFn: () => billingApi.checkout(selectedPlan, couponValidation?.valid ? promoCode : undefined),
    onSuccess: (data) => { window.location.href = data.checkout_url; },
    onError: (e: any) => toast.error(e.message),
  });

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const prev = () => setStep((s) => Math.max(s - 1, 0));

  const currentStep = STEPS[step];

  const handleStepAction = () => {
    if (step === 0) saveProfMut.mutate();
    else if (step === 1) saveProfMut.mutate();
    else if (step === 2) resumeFile ? uploadResumeMut.mutate() : next();
    else if (step === 3) next();
    else if (step === 4) checkoutMut.mutate();
    else navigate("/dashboard");
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Progress bar */}
      <div className="h-1 bg-muted">
        <motion.div
          className="h-full bg-primary"
          animate={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          transition={{ duration: 0.4 }}
        />
      </div>

      {/* Step indicators */}
      <div className="flex justify-center pt-8 pb-4 gap-2">
        {STEPS.map((s, i) => (
          <div
            key={s.id}
            className={cn(
              "w-2 h-2 rounded-full transition-all duration-300",
              i < step ? "bg-primary" : i === step ? "bg-primary w-6" : "bg-muted"
            )}
          />
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-4 py-8">
        <div className="w-full max-w-lg">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25 }}
              className="space-y-6"
            >
              {/* Header */}
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <currentStep.icon size={22} className="text-primary" />
                </div>
                <div>
                  <h1 className="text-xl font-semibold">{currentStep.title}</h1>
                  <p className="text-sm text-muted-foreground">{currentStep.subtitle}</p>
                </div>
              </div>

              {/* Step content */}
              {step === 0 && (
                <div className="space-y-4">
                  {[
                    { key: "full_name", label: "Full name", placeholder: "Alex Chen" },
                    { key: "location", label: "Current city", placeholder: "San Francisco, CA" },
                    { key: "linkedin_url", label: "LinkedIn URL (optional)", placeholder: "https://linkedin.com/in/..." },
                  ].map(({ key, label, placeholder }) => (
                    <div key={key} className="space-y-1.5">
                      <label className="text-sm font-medium">{label}</label>
                      <input
                        value={(profileData as any)[key]}
                        onChange={(e) => setProfileData((p) => ({ ...p, [key]: e.target.value }))}
                        placeholder={placeholder}
                        className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                      />
                    </div>
                  ))}
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Seniority level</label>
                    <select
                      value={profileData.seniority_level}
                      onChange={(e) => setProfileData((p) => ({ ...p, seniority_level: e.target.value }))}
                      className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    >
                      {["junior", "mid", "senior", "lead", "staff", "principal"].map((l) => (
                        <option key={l} value={l}>{l.charAt(0).toUpperCase() + l.slice(1)}</option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {step === 1 && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Target job titles</label>
                    {targets.target_titles.map((t, i) => (
                      <div key={i} className="flex gap-2">
                        <input
                          value={t}
                          onChange={(e) => {
                            const next = [...targets.target_titles];
                            next[i] = e.target.value;
                            setTargets((p) => ({ ...p, target_titles: next }));
                          }}
                          placeholder="e.g. Senior Software Engineer"
                          className="flex-1 px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                        />
                        {i > 0 && (
                          <button
                            onClick={() => setTargets((p) => ({ ...p, target_titles: p.target_titles.filter((_, j) => j !== i) }))}
                            className="p-2 rounded-xl border border-border hover:bg-muted"
                          >
                            <X size={14} />
                          </button>
                        )}
                      </div>
                    ))}
                    {targets.target_titles.length < 5 && (
                      <button
                        onClick={() => setTargets((p) => ({ ...p, target_titles: [...p.target_titles, ""] }))}
                        className="text-sm text-primary hover:underline"
                      >
                        + Add another title
                      </button>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Remote preference</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: "remote_only", label: "Remote only" },
                        { value: "remote_ok", label: "Remote ok" },
                        { value: "onsite_only", label: "On-site" },
                      ].map(({ value, label }) => (
                        <button
                          key={value}
                          onClick={() => setTargets((p) => ({ ...p, remote_preference: value }))}
                          className={cn(
                            "py-2 rounded-xl border text-sm font-medium transition-colors",
                            targets.remote_preference === value
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border hover:bg-muted"
                          )}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { key: "salary_min", label: "Min salary ($)" },
                      { key: "salary_max", label: "Max salary ($)" },
                    ].map(({ key, label }) => (
                      <div key={key} className="space-y-1.5">
                        <label className="text-sm font-medium">{label}</label>
                        <input
                          type="number"
                          value={(targets as any)[key]}
                          onChange={(e) => setTargets((p) => ({ ...p, [key]: Number(e.target.value) }))}
                          className="w-full px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className="space-y-4">
                  <label
                    className={cn(
                      "flex flex-col items-center justify-center gap-3 p-8 rounded-2xl border-2 border-dashed cursor-pointer transition-colors",
                      resumeFile ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"
                    )}
                  >
                    <input
                      type="file"
                      accept=".pdf,.docx,.doc"
                      className="hidden"
                      onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
                    />
                    {resumeFile ? (
                      <>
                        <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
                          <FileText size={22} className="text-primary" />
                        </div>
                        <div className="text-center">
                          <p className="font-medium text-sm">{resumeFile.name}</p>
                          <p className="text-xs text-muted-foreground">{(resumeFile.size / 1024).toFixed(0)} KB</p>
                        </div>
                        <button
                          onClick={(e) => { e.preventDefault(); setResumeFile(null); }}
                          className="text-xs text-destructive hover:underline"
                        >
                          Remove
                        </button>
                      </>
                    ) : (
                      <>
                        <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center">
                          <Upload size={22} className="text-muted-foreground" />
                        </div>
                        <div className="text-center">
                          <p className="font-medium text-sm">Drop your resume here</p>
                          <p className="text-xs text-muted-foreground">PDF or DOCX · Max 10MB</p>
                        </div>
                      </>
                    )}
                  </label>
                  <p className="text-xs text-muted-foreground text-center">
                    You can skip this and upload later from your profile page.
                  </p>
                </div>
              )}

              {step === 3 && (
                <div className="space-y-4">
                  <div className="flex gap-2">
                    <input
                      value={promoCode}
                      onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
                      placeholder="PROMO CODE"
                      className="flex-1 px-3.5 py-2.5 rounded-xl border border-border bg-background text-sm font-mono tracking-widest focus:outline-none focus:ring-2 focus:ring-primary/30"
                    />
                    <button
                      onClick={() => validateCouponMut.mutate()}
                      disabled={!promoCode || validateCouponMut.isPending}
                      className="px-4 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                    >
                      {validateCouponMut.isPending ? <Loader2 size={14} className="animate-spin" /> : "Apply"}
                    </button>
                  </div>
                  {couponValidation?.valid && (
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 text-sm">
                      <Check size={16} className="text-emerald-600 flex-shrink-0" />
                      <div>
                        <p className="font-medium text-emerald-800 dark:text-emerald-300">Code applied!</p>
                        <p className="text-emerald-700 dark:text-emerald-400">{couponValidation.savings_label}</p>
                      </div>
                    </div>
                  )}
                  <p className="text-xs text-center text-muted-foreground">No code? Skip this step — you can add one on the billing page.</p>
                </div>
              )}

              {step === 4 && (
                <div className="space-y-3">
                  {PLANS.map((plan) => (
                    <button
                      key={plan.id}
                      onClick={() => setSelectedPlan(plan.id)}
                      className={cn(
                        "w-full text-left p-5 rounded-2xl border-2 transition-all",
                        selectedPlan === plan.id ? "border-primary bg-primary/5" : "border-border hover:border-primary/30"
                      )}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">{plan.name}</span>
                          {plan.popular && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-primary text-primary-foreground font-medium">
                              Popular
                            </span>
                          )}
                        </div>
                        <div className="flex items-baseline gap-0.5">
                          <span className="text-2xl font-bold">
                            {couponValidation?.valid && selectedPlan === plan.id
                              ? `$${Math.round(couponValidation.discounted_price_cents / 100)}`
                              : plan.price}
                          </span>
                          <span className="text-sm text-muted-foreground">{plan.period}</span>
                        </div>
                      </div>
                      <ul className="space-y-1">
                        {plan.features.map((f) => (
                          <li key={f} className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Check size={12} className="text-primary flex-shrink-0" />
                            {f}
                          </li>
                        ))}
                      </ul>
                    </button>
                  ))}
                  <p className="text-xs text-center text-muted-foreground">
                    14-day free trial · Cancel anytime · Billed via Stripe
                  </p>
                </div>
              )}

              {step === 5 && (
                <div className="text-center space-y-4 py-4">
                  <div className="w-20 h-20 rounded-3xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mx-auto">
                    <Zap size={36} className="text-emerald-600" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">JobAimer is ready!</h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      Activate the agent and it will start finding and applying for jobs every 4 hours.
                    </p>
                  </div>
                </div>
              )}
            </motion.div>
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex gap-3 mt-8">
            {step > 0 && (
              <button
                onClick={prev}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-border text-sm font-medium hover:bg-muted transition-colors"
              >
                <ArrowLeft size={14} />
                Back
              </button>
            )}
            <button
              onClick={handleStepAction}
              disabled={saveProfMut.isPending || uploadResumeMut.isPending || checkoutMut.isPending}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {(saveProfMut.isPending || uploadResumeMut.isPending || checkoutMut.isPending) ? (
                <Loader2 size={14} className="animate-spin" />
              ) : step === STEPS.length - 1 ? (
                <><Zap size={14} /> Activate Agent</>
              ) : step === 4 ? (
                <><CreditCard size={14} /> Start free trial</>
              ) : (
                <><ArrowRight size={14} /> {step === 2 && !resumeFile ? "Skip for now" : "Continue"}</>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
