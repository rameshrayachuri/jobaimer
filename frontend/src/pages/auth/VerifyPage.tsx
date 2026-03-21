import { useSearchParams, Link } from "react-router-dom";
import { Mail, ArrowLeft } from "lucide-react";

export function VerifyPage() {
  const [params] = useSearchParams();
  const email = params.get("email") || "";

  return (
    <div className="space-y-6 text-center">
      <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto">
        <Mail size={28} className="text-primary" />
      </div>

      <div>
        <h1 className="text-2xl font-semibold">Check your email</h1>
        <p className="text-sm text-muted-foreground mt-2">
          We sent a verification link to{" "}
          {email ? <strong className="text-foreground">{email}</strong> : "your email address"}.
          Click it to activate your account.
        </p>
      </div>

      <div className="bg-muted rounded-xl p-4 text-sm text-muted-foreground text-left space-y-1">
        <p className="font-medium text-foreground">Didn't get it?</p>
        <p>Check your spam folder, or make sure you entered the correct email address.</p>
      </div>

      <Link
        to="/login"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft size={14} />
        Back to sign in
      </Link>
    </div>
  );
}
