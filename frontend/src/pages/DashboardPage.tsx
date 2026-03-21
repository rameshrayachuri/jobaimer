import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { dashboard, agent } from '@/lib/api'
import { motion } from 'framer-motion'
import { Play, Pause, Square, Briefcase, Calendar, TrendingUp, Trophy } from 'lucide-react'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'
import { formatDistanceToNow } from '@/lib/utils'

export default function DashboardPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: dashboard.get })

  const activateMut = useMutation({
    mutationFn: agent.activate,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dashboard'] }); toast.success('Agent activated!') },
    onError: (e: Error) => toast.error(e.message),
  })
  const pauseMut = useMutation({
    mutationFn: agent.pause,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dashboard'] }); toast.success('Agent paused') },
  })
  const stopMut = useMutation({
    mutationFn: agent.stop,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['dashboard'] }); toast.success('Agent stopped') },
  })

  if (isLoading) return <PageSkeleton />

  const d = data!
  const agentStatus = d.agent_status

  const stats = [
    { label: 'Total Applied', value: d.total_applied, icon: Briefcase, color: 'text-indigo-400' },
    { label: 'Interviews', value: d.interviews_scheduled, icon: Calendar, color: 'text-emerald-400' },
    { label: 'Offers', value: d.offers_received, icon: TrendingUp, color: 'text-amber-400' },
    { label: 'Avg ATS Score', value: `${d.avg_ats_score}%`, icon: Trophy, color: 'text-rose-400' },
  ]

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <Link to="/applications" className="text-sm text-indigo-400 hover:text-indigo-300">
            View all applications →
          </Link>
        </div>

        {/* Agent control */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gray-900 border border-gray-800 rounded-xl p-6"
        >
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <p className="text-sm text-gray-400 mb-1">Agent Status</p>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${
                  agentStatus === 'active' ? 'bg-emerald-500 animate-pulse' :
                  agentStatus === 'paused' ? 'bg-amber-500' : 'bg-gray-600'
                }`} />
                <span className="text-lg font-semibold capitalize">{agentStatus}</span>
                {d.next_cycle_at && agentStatus === 'active' && (
                  <span className="text-xs text-gray-500 ml-2">
                    Next cycle {formatDistanceToNow(new Date(d.next_cycle_at))}
                  </span>
                )}
              </div>
            </div>

            <div className="flex gap-2">
              {agentStatus !== 'active' && (
                <button
                  onClick={() => activateMut.mutate()}
                  disabled={activateMut.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  <Play size={14} /> Start Agent
                </button>
              )}
              {agentStatus === 'active' && (
                <button
                  onClick={() => pauseMut.mutate()}
                  disabled={pauseMut.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm font-medium transition-colors"
                >
                  <Pause size={14} /> Pause
                </button>
              )}
              {agentStatus !== 'stopped' && (
                <button
                  onClick={() => stopMut.mutate()}
                  disabled={stopMut.isPending}
                  className="flex items-center gap-2 px-4 py-2 bg-red-900/40 hover:bg-red-900/60 text-red-400 rounded-lg text-sm font-medium transition-colors"
                >
                  <Square size={14} /> Stop
                </button>
              )}
            </div>
          </div>
        </motion.div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5"
            >
              <s.icon size={18} className={`${s.color} mb-3`} />
              <p className="text-2xl font-bold text-white">{s.value}</p>
              <p className="text-xs text-gray-500 mt-1">{s.label}</p>
            </motion.div>
          ))}
        </div>

        {/* Recent applications */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-800">
            <h2 className="font-semibold text-gray-200">Recent Applications</h2>
          </div>
          <div className="divide-y divide-gray-800">
            {d.recent_applications.length === 0 ? (
              <div className="p-8 text-center text-gray-500 text-sm">
                No applications yet — activate the agent to get started.
              </div>
            ) : (
              d.recent_applications.map(app => (
                <Link
                  key={app.id}
                  to={`/applications?highlight=${app.id}`}
                  className="flex items-center justify-between px-6 py-4 hover:bg-gray-800/50 transition-colors"
                >
                  <div>
                    <p className="font-medium text-gray-200 text-sm">{app.title}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{app.company}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {app.ats_score && (
                      <span className="text-xs text-indigo-400">{app.ats_score}% ATS</span>
                    )}
                    <StatusBadge status={app.status} />
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      </div>
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
    failed: 'bg-gray-800 text-gray-500',
    skipped: 'bg-gray-800 text-gray-500',
  }
  const label = status.replace(/_/g, ' ')
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] || 'bg-gray-800 text-gray-400'}`}>
      {label}
    </span>
  )
}

function PageSkeleton() {
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-6xl mx-auto space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-gray-800 rounded" />
        <div className="h-28 bg-gray-900 rounded-xl" />
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-24 bg-gray-900 rounded-xl" />)}
        </div>
        <div className="h-64 bg-gray-900 rounded-xl" />
      </div>
    </div>
  )
}
