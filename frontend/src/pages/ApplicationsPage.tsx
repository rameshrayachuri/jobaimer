import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { applications } from '@/lib/api'
import type { Application } from '@/lib/api'
import { motion, AnimatePresence } from 'framer-motion'
import { Trash2, FileDown, MoreVertical, FileX } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import * as AlertDialog from '@radix-ui/react-alert-dialog'
import toast from 'react-hot-toast'

const HIGH_VALUE_STATUSES = new Set(['interview_scheduled', 'offer_received', 'accepted'])

export default function ApplicationsPage() {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState<string | undefined>()
  const [deleteTarget, setDeleteTarget] = useState<{ app: Application; type: 'full' | 'resume_only' } | null>(null)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['applications', statusFilter],
    queryFn: () => applications.list({ status: statusFilter }),
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => applications.delete(id),
    onSuccess: (_, id) => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      toast.success('Application deleted')
      setDeleteTarget(null)
    },
    onError: (e: Error) => {
      if (e.message.includes('in_progress')) {
        toast.error('Application is being filed — try again in a moment')
      } else {
        toast.error(e.message)
      }
    },
  })

  const deleteResumeMut = useMutation({
    mutationFn: (id: string) => applications.deleteResume(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      toast.success('Resume file deleted')
      setDeleteTarget(null)
    },
  })

  const isHighValue = deleteTarget ? HIGH_VALUE_STATUSES.has(deleteTarget.app.status) : false
  const canConfirm = !isHighValue || deleteConfirmText === 'DELETE'

  const apps = data?.applications ?? []

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-5xl mx-auto space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-2xl font-bold text-white">Applications</h1>

          {/* Status filter */}
          <div className="flex gap-2 flex-wrap">
            {['all', 'applied', 'interview_scheduled', 'offer_received', 'accepted', 'failed'].map(s => (
              <button
                key={s}
                onClick={() => setStatusFilter(s === 'all' ? undefined : s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  (s === 'all' && !statusFilter) || statusFilter === s
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {s === 'all' ? 'All' : s.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-900 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : apps.length === 0 ? (
          <div className="text-center py-20 text-gray-500 text-sm">
            No applications found.
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {apps.map((app, i) => (
              <motion.div
                key={app.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.97 }}
                transition={{ delay: Math.min(i * 0.03, 0.3) }}
                className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-start justify-between gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <p className="font-semibold text-gray-100 truncate">{app.job.title}</p>
                    <StatusBadge status={app.status} />
                  </div>
                  <p className="text-sm text-gray-400">{app.job.company} · {app.job.location}</p>
                  {app.applied_at && (
                    <p className="text-xs text-gray-600 mt-1">
                      Applied {new Date(app.applied_at).toLocaleDateString()}
                      {app.ats_score && <span className="ml-2 text-indigo-500">{app.ats_score}% ATS match</span>}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {/* Resume download */}
                  {app.resume.available && (
                    <a
                      href={`/api/v1/applications/${app.id}/resume`}
                      className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
                      title="Download tailored resume"
                    >
                      <FileDown size={15} />
                    </a>
                  )}

                  {/* Actions dropdown */}
                  <DropdownMenu.Root>
                    <DropdownMenu.Trigger asChild>
                      <button className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white transition-colors">
                        <MoreVertical size={15} />
                      </button>
                    </DropdownMenu.Trigger>
                    <DropdownMenu.Portal>
                      <DropdownMenu.Content
                        className="bg-gray-800 border border-gray-700 rounded-xl p-1 min-w-48 shadow-xl z-50"
                        sideOffset={6}
                        align="end"
                      >
                        {app.resume.available && (
                          <DropdownMenu.Item
                            className="flex items-center gap-2 px-3 py-2 text-sm text-amber-400 rounded-lg hover:bg-gray-700 cursor-pointer"
                            onSelect={() => setDeleteTarget({ app, type: 'resume_only' })}
                          >
                            <FileX size={14} /> Delete resume file
                          </DropdownMenu.Item>
                        )}
                        <DropdownMenu.Item
                          className="flex items-center gap-2 px-3 py-2 text-sm text-red-400 rounded-lg hover:bg-gray-700 cursor-pointer"
                          onSelect={() => { setDeleteConfirmText(''); setDeleteTarget({ app, type: 'full' }) }}
                        >
                          <Trash2 size={14} /> Delete application
                        </DropdownMenu.Item>
                      </DropdownMenu.Content>
                    </DropdownMenu.Portal>
                  </DropdownMenu.Root>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* Delete confirmation dialog */}
      <AlertDialog.Root open={!!deleteTarget} onOpenChange={(o) => { if (!o) setDeleteTarget(null) }}>
        <AlertDialog.Portal>
          <AlertDialog.Overlay className="fixed inset-0 bg-black/70 z-50" />
          <AlertDialog.Content className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-gray-900 border border-gray-700 rounded-2xl p-6 max-w-sm w-full shadow-2xl">
            {deleteTarget && (
              <>
                <AlertDialog.Title className="text-lg font-semibold text-white mb-2">
                  {deleteTarget.type === 'resume_only' ? 'Delete resume file?' : 'Delete application?'}
                </AlertDialog.Title>
                <AlertDialog.Description className="text-sm text-gray-400 mb-4">
                  {deleteTarget.type === 'resume_only'
                    ? 'The tailored resume PDF will be permanently deleted. The application record is kept.'
                    : <>
                        <strong className="text-gray-200">{deleteTarget.app.job.title}</strong> at{' '}
                        <strong className="text-gray-200">{deleteTarget.app.job.company}</strong>
                        {' '}will be soft-deleted and permanently removed after 30 days.
                      </>
                  }
                </AlertDialog.Description>

                {isHighValue && deleteTarget.type === 'full' && (
                  <div className="mb-4">
                    <p className="text-xs text-amber-400 mb-2">
                      This application has status <strong>{deleteTarget.app.status.replace(/_/g, ' ')}</strong>.
                      Type <strong>DELETE</strong> to confirm.
                    </p>
                    <input
                      autoFocus
                      value={deleteConfirmText}
                      onChange={e => setDeleteConfirmText(e.target.value.toUpperCase())}
                      placeholder="Type DELETE to confirm"
                      className="w-full px-3 py-2 rounded-lg bg-gray-800 border border-gray-600 text-sm text-white placeholder-gray-500 outline-none focus:border-red-500"
                    />
                  </div>
                )}

                <div className="flex justify-end gap-3">
                  <AlertDialog.Cancel asChild>
                    <button className="px-4 py-2 text-sm rounded-lg bg-gray-800 text-gray-300 hover:bg-gray-700">
                      Cancel
                    </button>
                  </AlertDialog.Cancel>
                  <button
                    disabled={!canConfirm || deleteMut.isPending || deleteResumeMut.isPending}
                    onClick={() => {
                      if (deleteTarget.type === 'full') deleteMut.mutate(deleteTarget.app.id)
                      else deleteResumeMut.mutate(deleteTarget.app.id)
                    }}
                    className="px-4 py-2 text-sm rounded-lg bg-red-700 hover:bg-red-600 text-white font-medium disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {deleteMut.isPending || deleteResumeMut.isPending ? 'Deleting…' : 'Delete'}
                  </button>
                </div>
              </>
            )}
          </AlertDialog.Content>
        </AlertDialog.Portal>
      </AlertDialog.Root>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    applied: 'bg-blue-900/40 text-blue-400',
    interview_scheduled: 'bg-emerald-900/40 text-emerald-400',
    offer_received: 'bg-amber-900/40 text-amber-400',
    accepted: 'bg-green-900/40 text-green-400',
    rejected: 'bg-red-900/40 text-red-400',
    tailoring_resume: 'bg-purple-900/40 text-purple-400',
    applying: 'bg-cyan-900/40 text-cyan-400',
    failed: 'bg-gray-800 text-gray-500',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || 'bg-gray-800 text-gray-400'}`}>
      {status.replace(/_/g, ' ')}
    </span>
  )
}
