import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, FileX, Loader2, RefreshCw } from "lucide-react";
import { applications } from "../../lib/api";
import { cn } from "../../lib/utils";
import toast from "react-hot-toast";

interface ResumeDownloadButtonProps {
  applicationId: string;
  className?: string;
}

export function ResumeDownloadButton({ applicationId, className }: ResumeDownloadButtonProps) {
  const [downloading, setDownloading] = useState(false);

  const { data: status, isLoading } = useQuery({
    queryKey: ["resume-status", applicationId],
    queryFn: () => applications.resumeStatus(applicationId),
  });

  async function handleDownload() {
    if (!status?.available) return;
    setDownloading(true);
    try {
      // Get pre-signed URL from backend
      const res = await fetch(`/api/v1/applications/${applicationId}/resume/download`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("jobaimer-token")}` },
      });
      if (!res.ok) throw new Error("Download failed");
      const { url } = await res.json();
      // Open in new tab — browser handles download
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e: any) {
      toast.error(e.message || "Download failed");
    } finally {
      setDownloading(false);
    }
  }

  if (isLoading) {
    return (
      <button disabled className={cn("inline-flex items-center gap-1.5 text-xs text-muted-foreground", className)}>
        <Loader2 size={12} className="animate-spin" />
        Loading…
      </button>
    );
  }

  if (!status?.available) {
    return (
      <span className={cn("inline-flex items-center gap-1.5 text-xs text-muted-foreground/50", className)}>
        <FileX size={12} />
        Resume deleted
      </span>
    );
  }

  return (
    <button
      onClick={handleDownload}
      disabled={downloading}
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary/80 transition-colors disabled:opacity-50",
        className
      )}
    >
      {downloading
        ? <><Loader2 size={12} className="animate-spin" />Downloading…</>
        : <><Download size={12} />Resume</>
      }
    </button>
  );
}
