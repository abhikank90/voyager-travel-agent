import { motion } from 'framer-motion'
import { Sun, Moon, Sunset, UtensilsCrossed, Lightbulb } from 'lucide-react'
import { ItineraryDay } from '../types'

interface ItineraryCardProps {
  day: ItineraryDay
  index: number
}

export function ItineraryCard({ day, index }: ItineraryCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="bg-white rounded-2xl shadow-md border border-gray-100 overflow-hidden"
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-voyager-ocean to-voyager-blue px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-white/60 text-xs font-medium uppercase tracking-wider">
              Day {day.day_number}
            </p>
            <p className="text-white font-semibold text-lg">{day.theme}</p>
          </div>
          <div className="text-right">
            <p className="text-white/60 text-xs">{day.date}</p>
            <p className="text-white font-medium">${day.estimated_cost_usd}</p>
          </div>
        </div>
      </div>

      {/* Schedule */}
      <div className="p-5 space-y-3">
        <TimeBlock icon={<Sun className="w-4 h-4 text-yellow-500" />} label="Morning" text={day.morning} />
        <TimeBlock icon={<Sunset className="w-4 h-4 text-orange-500" />} label="Afternoon" text={day.afternoon} />
        <TimeBlock icon={<Moon className="w-4 h-4 text-indigo-500" />} label="Evening" text={day.evening} />

        {day.meals && day.meals.length > 0 && (
          <div className="flex gap-2 items-start pt-1">
            <UtensilsCrossed className="w-4 h-4 text-voyager-teal mt-0.5 shrink-0" />
            <p className="text-sm text-gray-600">{day.meals.join(' · ')}</p>
          </div>
        )}

        {day.tips && day.tips.length > 0 && (
          <div className="flex gap-2 items-start bg-amber-50 rounded-xl p-3">
            <Lightbulb className="w-4 h-4 text-amber-500 mt-0.5 shrink-0" />
            <p className="text-sm text-amber-800">{day.tips[0]}</p>
          </div>
        )}
      </div>
    </motion.div>
  )
}

function TimeBlock({ icon, label, text }: { icon: React.ReactNode; label: string; text: string }) {
  return (
    <div className="flex gap-2 items-start">
      <div className="mt-0.5 shrink-0">{icon}</div>
      <div>
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{label} </span>
        <span className="text-sm text-gray-700">{text}</span>
      </div>
    </div>
  )
}
