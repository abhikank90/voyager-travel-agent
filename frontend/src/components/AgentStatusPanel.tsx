import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle, Loader, Circle } from 'lucide-react'
import { AgentStatus } from '../types'

interface AgentStep {
  id: string
  label: string
  status: AgentStatus
  message?: string
}

interface AgentStatusPanelProps {
  steps: AgentStep[]
}

const ICON_MAP: Record<AgentStatus, React.ReactNode> = {
  pending: <Circle className="w-5 h-5 text-gray-300" />,
  running: <Loader className="w-5 h-5 text-voyager-teal animate-spin" />,
  done: <CheckCircle className="w-5 h-5 text-green-500" />,
  error: <CheckCircle className="w-5 h-5 text-red-500" />,
}

export function AgentStatusPanel({ steps }: AgentStatusPanelProps) {
  return (
    <div className="bg-white rounded-2xl shadow-lg p-6 w-full max-w-sm">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-widest mb-4">
        AI Agents at work
      </h3>
      <div className="space-y-3">
        <AnimatePresence>
          {steps.map((step) => (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-start gap-3"
            >
              <div className="mt-0.5 shrink-0">{ICON_MAP[step.status]}</div>
              <div>
                <p
                  className={`text-sm font-medium ${
                    step.status === 'running'
                      ? 'text-voyager-teal'
                      : step.status === 'done'
                        ? 'text-gray-700'
                        : 'text-gray-400'
                  }`}
                >
                  {step.label}
                </p>
                {step.message && step.status === 'running' && (
                  <p className="text-xs text-gray-400 mt-0.5">{step.message}</p>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
