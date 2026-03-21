import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2, FileX, AlertTriangle, Loader2, ChevronDown } from "lucide-react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import { applications } from "../../lib/api";
import { cn } from "../../lib/utils";
import toast from "react-hot-toast";

interface DeleteApplicationDialogProps {
  applicationId: string;
  jobTitle: string;
  company: string;
  hasResume: boolean;
  onDeleted?: () => void;
}

type DeleteMode = "full" | "resume_only";

export function ApplicationActionMenu({
  applicationId,
  jobTitle,
  company,
  hasResume,
  onDeleted,
}: DeleteApplicationDialogProps) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<DeleteMode>("full");
  const [confirmText, setConfirmText] = useState("");
  const qc = useQueryClient();

  const deleteMut = useMutation({
    mutationFn: () =>
      mode === "full"
        ? applications.delete(applicationId)
        : applications.deleteResume(applicationId),
    onSuccess: (data) => {
      const label = mode === "full" ? "Application deleted" : "Resume deleted";
      const extra =
        data.bytes_freed
          ? ` · ${(data.bytes_freed / 1024).toFixed(0)} KB freed`
          : "";
      toast.success(label + extra);
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      setOpen(false);
      setConfirmText("");
      onDeleted?.();
    },
    onError: (e: any) => toast.error(e.message || "Delete failed"),
  });

  const confirmRequired = mode === "full" ? company : "";
  const canConfirm =
    mode === "resume_only" || confirmText.trim() === confirmRequired;

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors">
            <ChevronDown size={14} />
          </button>
        </DropdownMenu.Trigger>

        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={4}
            className="z-50 min-w-[180px] rounded-xl border border-border bg-card p-1 shadow-lg text-sm"
          >
            {hasResume && (
              <DropdownMenu.Item
                className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer hover:bg-muted text-muted-foreground hover:text-foreground outline-none"
                onSelect={() => {
                  setMode("resume_only");
                  setOpen(true);
                }}
              >
                <FileX size={14} />
                Delete resume file
              </DropdownMenu.Item>
            )}
            <DropdownMenu.Item
              className="flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer hover:bg-destructive/10 text-destructive outline-none"
              onSelect={() => {
                setMode("full");
                setOpen(true);
              }}
            >
              <Trash2 size={14} />
              Delete application
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>

      <AlertDialog.Root open={open} onOpenChange={(v) => { setOpen(v); setConfirmText(""); }}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm" />
          <AlertDialog.Content className="fixed z-50 left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-card border border-border rounded-2xl p-6 shadow-xl">
            {/* Icon */}
            <div className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center mb-4",
              mode === "full" ? "bg-destructive/10" : "bg-orange-100 dark:bg-orange-900/20"
            )}>
              {mode === "full"
                ? <Trash2 size={22} className="text-destructive" />
                : <FileX size={22} className="text-orange-500" />
              }
            </div>

            {mode === "full" ? (
              <>
                <AlertDialog.Title className="text-lg font-semibold mb-1">
                  Delete this application?
                </AlertDialog.Title>
                <AlertDialog.Description className="text-sm text-muted-foreground mb-4">
                  <strong>{jobTitle}</strong> at <strong>{company}</strong> will be permanently removed, including any tailored resume. This cannot be undone.
                </AlertDialog.Description>

                <div className="bg-muted/60 rounded-xl p-3 mb-4 flex items-start gap-2">
                  <AlertTriangle size={14} className="text-yellow-500 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-muted-foreground">
                    Type <strong className="text-foreground">{company}</strong> to confirm
                  </p>
                </div>

                <input
                  type="text"
                  value={confirmText}
                  onChange={(e) => setConfirmText(e.target.value)}
                  placeholder={company}
                  className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-destructive/30 mb-4"
                  autoFocus
                />
              </>
            ) : (
              <>
                <AlertDialog.Title className="text-lg font-semibold mb-1">
                  Delete resume file?
                </AlertDialog.Title>
                <AlertDialog.Description className="text-sm text-muted-foreground mb-4">
                  The tailored resume for <strong>{jobTitle}</strong> at <strong>{company}</strong> will be permanently deleted from storage. The application record is kept.
                </AlertDialog.Description>
              </>
            )}

            <div className="flex gap-3 justify-end">
              <AlertDialog.Cancel
                className="px-4 py-2 rounded-lg text-sm font-medium border border-border hover:bg-muted transition-colors"
                disabled={deleteMut.isPending}
              >
                Cancel
              </AlertDialog.Cancel>
              <button
                onClick={() => deleteMut.mutate()}
                disabled={!canConfirm || deleteMut.isPending}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed",
                  mode === "full" ? "bg-destructive hover:bg-destructive/90" : "bg-orange-500 hover:bg-orange-600"
                )}
              >
                {deleteMut.isPending && <Loader2 size={14} className="animate-spin" />}
                {mode === "full" ? "Delete application" : "Delete resume"}
              </button>
            </div>
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </>
  );
}
