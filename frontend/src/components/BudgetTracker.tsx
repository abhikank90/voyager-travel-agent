import { BudgetBreakdown } from '../types'
import { DollarSign, TrendingUp, TrendingDown } from 'lucide-react'

interface BudgetTrackerProps {
  breakdown: BudgetBreakdown
}

export function BudgetTracker({ breakdown }: BudgetTrackerProps) {
  const items = [
    { label: 'Flights', value: breakdown.flights_usd, color: 'bg-blue-500' },
    { label: 'Hotel', value: breakdown.hotel_usd, color: 'bg-teal-500' },
    { label: 'Activities', value: breakdown.activities_usd, color: 'bg-yellow-500' },
    { label: 'Food', value: breakdown.food_usd, color: 'bg-orange-500' },
    { label: 'Misc', value: breakdown.misc_usd, color: 'bg-gray-400' },
  ]

  const pct = Math.min((breakdown.total_usd / breakdown.budget_usd) * 100, 100)

  return (
    <div className="bg-white rounded-2xl shadow-lg p-6">
      <div className="flex items-center gap-2 mb-4">
        <DollarSign className="w-5 h-5 text-voyager-teal" />
        <h3 className="font-semibold text-gray-800">Budget Breakdown</h3>
      </div>

      <div className="flex items-end justify-between mb-2">
        <span className="text-2xl font-bold text-gray-900">
          ${breakdown.total_usd.toLocaleString()}
        </span>
        <span className="text-sm text-gray-500">of ${breakdown.budget_usd.toLocaleString()}</span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden mb-4">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            breakdown.is_within_budget ? 'bg-green-500' : 'bg-red-500'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Status badge */}
      <div
        className={`flex items-center gap-1.5 text-sm font-medium mb-4 ${
          breakdown.is_within_budget ? 'text-green-600' : 'text-red-600'
        }`}
      >
        {breakdown.is_within_budget ? (
          <>
            <TrendingDown className="w-4 h-4" />
            ${breakdown.savings_usd.toLocaleString()} under budget
          </>
        ) : (
          <>
            <TrendingUp className="w-4 h-4" />
            ${breakdown.overage_usd.toLocaleString()} over budget
          </>
        )}
      </div>

      {/* Line items */}
      <div className="space-y-2">
        {items.map(({ label, value, color }) => (
          <div key={label} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${color}`} />
              <span className="text-gray-600">{label}</span>
            </div>
            <span className="font-medium text-gray-800">${value.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
