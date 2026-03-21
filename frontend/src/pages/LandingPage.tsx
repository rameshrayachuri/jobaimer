import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Bot, Zap, Target, FileText, BarChart2, Shield,
  ArrowRight, Check, Star, ChevronRight,
} from "lucide-react";

const FEATURES = [
  {
    icon: Zap,
    title: "Applies every 4 hours",
    desc: "The agent runs on autopilot — discovering, scoring, and submitting while you sleep.",
  },
  {
    icon: Target,
    title: "ATS score matching",
    desc: "Only applies to jobs where your resume scores above 65% — no wasted shots.",
  },
  {
    icon: FileText,
    title: "AI resume tailoring",
    desc: "Claude rewrites your bullets and summary for each specific role and company.",
  },
  {
    icon: BarChart2,
    title: "Full visibility",
    desc: "Track every application, status, ATS score, and interview in real time.",
  },
  {
    icon: Shield,
    title: "Privacy first",
    desc: "Resume files auto-delete after 6 months. You control everything.",
  },
  {
    icon: Bot,
    title: "Multi-portal",
    desc: "LinkedIn, Indeed, Greenhouse, Lever, Workday — we cover them all.",
  },
];

const PLANS = [
  {
    name: "Starter",
    price: 19,
    period: "/mo",
    features: ["20 apps/cycle", "7 portals", "AI tailoring (3 passes)", "Email alerts", "14-day free trial"],
  },
  {
    name: "Pro",
    price: 39,
    period: "/mo",
    popular: true,
    features: ["50 apps/cycle", "All portals", "AI tailoring (5 passes)", "SMS + Email alerts", "14-day free trial"],
  },
  {
    name: "Annual Pro",
    price: 32,
    period: "/mo",
    note: "billed $390/yr",
    features: ["Everything in Pro", "2 months free", "Priority support", "14-day free trial"],
  },
];

const TESTIMONIALS = [
  { name: "Alex Chen", role: "Software Engineer → Series B startup", quote: "I went from 2 apps a week to 50. JobAimer does the legwork so I prep for interviews instead." },
  { name: "Priya Sharma", role: "Product Manager → FAANG", quote: "Honestly couldn't believe how many interviews I got in 3 weeks. The ATS scoring is brilliant." },
  { name: "Marcus Lee", role: "Data Scientist → Fortune 500", quote: "Set it up Saturday, had 3 phone screens by Wednesday. Zero cold-apply anxiety." },
];

function FadeIn({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5, delay }}
    >
      {children}
    </motion.div>
  );
}

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <nav className="sticky top-0 z-50 h-16 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto h-full flex items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Bot size={16} className="text-primary-foreground" />
            </div>
            <span className="font-semibold text-lg">JobAimer</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
              Sign in
            </Link>
            <Link
              to="/register"
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Start free trial <ArrowRight size={13} />
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden pt-24 pb-20 gradient-hero">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <FadeIn>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-medium mb-6">
              <Zap size={11} />
              Now applying to 50+ jobs per cycle
            </div>
          </FadeIn>
          <FadeIn delay={0.05}>
            <h1 className="text-5xl sm:text-6xl font-bold tracking-tight leading-tight mb-6">
              Your AI agent that<br />
              <span className="text-primary">applies while you sleep</span>
            </h1>
          </FadeIn>
          <FadeIn delay={0.1}>
            <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
              JobAimer discovers jobs, scores your ATS match, tailors your resume with Claude AI, and submits applications — every 4 hours, automatically.
            </p>
          </FadeIn>
          <FadeIn delay={0.15}>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                to="/register"
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
              >
                Start 14-day free trial <ArrowRight size={16} />
              </Link>
              <Link
                to="/login"
                className="flex items-center gap-2 px-6 py-3 rounded-xl border border-border text-sm font-medium hover:bg-muted transition-colors"
              >
                Sign in
              </Link>
            </div>
            <p className="text-xs text-muted-foreground mt-3">No credit card required · Cancel anytime</p>
          </FadeIn>
        </div>
      </section>

      {/* Stats bar */}
      <section className="border-y border-border bg-muted/30 py-8">
        <div className="max-w-4xl mx-auto px-6 grid grid-cols-2 sm:grid-cols-4 gap-6 text-center">
          {[
            { value: "50+", label: "Apps per cycle" },
            { value: "4hr", label: "Cycle interval" },
            { value: "65%", label: "Min ATS threshold" },
            { value: "6mo", label: "Resume storage" },
          ].map(({ value, label }) => (
            <div key={label}>
              <div className="text-3xl font-bold text-primary">{value}</div>
              <div className="text-sm text-muted-foreground mt-1">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <FadeIn>
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold mb-3">Everything automated</h2>
              <p className="text-muted-foreground max-w-xl mx-auto">
                From discovery to submission — JobAimer handles the entire application pipeline.
              </p>
            </div>
          </FadeIn>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {FEATURES.map(({ icon: Icon, title, desc }, i) => (
              <FadeIn key={title} delay={i * 0.05}>
                <div className="bg-card border border-border rounded-2xl p-6 card-hover h-full">
                  <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                    <Icon size={18} className="text-primary" />
                  </div>
                  <h3 className="font-semibold mb-2">{title}</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">{desc}</p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="py-20 px-6 bg-muted/20">
        <div className="max-w-5xl mx-auto">
          <FadeIn>
            <h2 className="text-3xl font-bold text-center mb-12">People are getting hired</h2>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {TESTIMONIALS.map(({ name, role, quote }, i) => (
              <FadeIn key={name} delay={i * 0.08}>
                <div className="bg-card border border-border rounded-2xl p-6 space-y-4">
                  <div className="flex gap-0.5">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star key={i} size={13} className="fill-yellow-400 text-yellow-400" />
                    ))}
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">"{quote}"</p>
                  <div>
                    <p className="text-sm font-semibold">{name}</p>
                    <p className="text-xs text-muted-foreground">{role}</p>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-24 px-6">
        <div className="max-w-5xl mx-auto">
          <FadeIn>
            <div className="text-center mb-16">
              <h2 className="text-3xl font-bold mb-3">Simple pricing</h2>
              <p className="text-muted-foreground">14-day free trial on all plans. No credit card required.</p>
            </div>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {PLANS.map(({ name, price, period, note, popular, features }, i) => (
              <FadeIn key={name} delay={i * 0.05}>
                <div className={`relative rounded-2xl border p-6 space-y-5 h-full flex flex-col ${popular ? "border-primary shadow-lg shadow-primary/10" : "border-border"}`}>
                  {popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="px-3 py-1 rounded-full bg-primary text-primary-foreground text-xs font-medium">Most popular</span>
                    </div>
                  )}
                  <div>
                    <h3 className="font-semibold text-lg">{name}</h3>
                    <div className="flex items-baseline gap-1 mt-2">
                      <span className="text-3xl font-bold">${price}</span>
                      <span className="text-muted-foreground text-sm">{period}</span>
                    </div>
                    {note && <p className="text-xs text-muted-foreground mt-1">{note}</p>}
                  </div>
                  <ul className="space-y-2 flex-1">
                    {features.map((f) => (
                      <li key={f} className="flex items-center gap-2.5 text-sm">
                        <Check size={13} className="text-primary flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Link
                    to="/register"
                    className={`flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-medium transition-colors ${popular ? "bg-primary text-primary-foreground hover:bg-primary/90" : "border border-border hover:bg-muted"}`}
                  >
                    Start free trial <ChevronRight size={14} />
                  </Link>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-6 bg-primary text-primary-foreground">
        <FadeIn>
          <div className="max-w-2xl mx-auto text-center space-y-6">
            <h2 className="text-3xl font-bold">Stop applying manually</h2>
            <p className="text-primary-foreground/80 text-lg">
              Let JobAimer handle the volume while you focus on the conversations that matter.
            </p>
            <Link
              to="/register"
              className="inline-flex items-center gap-2 px-8 py-3 rounded-xl bg-white text-primary font-semibold hover:bg-white/90 transition-colors"
            >
              Start free trial <ArrowRight size={16} />
            </Link>
            <p className="text-sm text-primary-foreground/60">No credit card · 14 days free · Cancel anytime</p>
          </div>
        </FadeIn>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-primary/80 flex items-center justify-center">
              <Bot size={11} className="text-primary-foreground" />
            </div>
            <span>JobAimer © 2025</span>
          </div>
          <div className="flex gap-5">
            <a href="/privacy" className="hover:text-foreground transition-colors">Privacy</a>
            <a href="/terms" className="hover:text-foreground transition-colors">Terms</a>
            <a href="mailto:support@jobaimer.com" className="hover:text-foreground transition-colors">Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
