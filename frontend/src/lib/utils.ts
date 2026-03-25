import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date | null | undefined): string {
  if (!date) return "â";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(date));
}

export function formatRelativeTime(date: string | Date | null | undefined): string {
  if (!date) return "â";
  const d = new Date(date);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return formatDate(date);
}

export function formatCurrency(cents: number, currency = "usd"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
    minimumFractionDigits: 0,
  }).format(cents / 100);
}

export const APPLICATION_STATUS_LABELS: Record<string, string> = {
  discovered: "Discovered",
  tailoring_resume: "Tailoring",
  applying: "Applying",
  applied: "Applied",
  under_review: "Under Review",
  interview_scheduled: "Interview",
  offer_received: "Offer",
  accepted: "Accepted",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
  low_match_skipped: "Skipped",
};

export const APPLICATION_STATUS_COLORS: Record<string, string> = {
  discovered: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  tailoring_resume: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  applying: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  applied: "bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400",
  under_review: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  interview_scheduled: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  offer_received: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  accepted: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  rejected: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  withdrawn: "bg-slate-100 text-slate-500",
  low_match_skipped: "bg-slate-100 text-slate-400",
};

export function formatDistanceToNow(date: Date | string | null | undefined): string {
  if (!date) return 'unknown';
  const d = new Date(date);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return diffMins + 'm ago';
  if (diffHours < 24) return diffHours + 'h ago';
  if (diffDays < 7) return diffDays + 'd ago';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
