import { Outlet, Link } from "react-router-dom";
import { Bot } from "lucide-react";

export function AuthLayout() {
  return (
    <div className="min-h-screen flex gradient-hero">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-primary text-primary-foreground">
        <Link to="/" className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center">
            <Bot size={20} className="text-white" />
          </div>
          <span className="text-xl font-semibold">JobAimer</span>
        </Link>

        <div>
          <blockquote className="text-2xl font-light leading-relaxed mb-6">
            "I went from 2 applications a week to 50 — JobAimer does the legwork while I prep for interviews."
          </blockquote>
          <p className="text-primary-foreground/80 font-medium">Alex Chen, Software Engineer</p>
          <p className="text-primary-foreground/60 text-sm">Landed role at Series B startup</p>
        </div>

        <div className="flex gap-8 text-primary-foreground/70 text-sm">
          <div>
            <div className="text-2xl font-bold text-white">50+</div>
            <div>Apps per cycle</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">4hr</div>
            <div>Auto-cycle</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-white">AI</div>
            <div>Resume tailoring</div>
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="lg:hidden mb-8 flex justify-center">
            <Link to="/" className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                <Bot size={17} className="text-primary-foreground" />
              </div>
              <span className="font-semibold text-lg">JobAimer</span>
            </Link>
          </div>
          <Outlet />
        </div>
      </div>
    </div>
  );
}
