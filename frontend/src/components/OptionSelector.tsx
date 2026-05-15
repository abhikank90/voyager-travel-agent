import React, { useState } from 'react'
import { TripOption } from '../types'
import { TripOptionCard } from './TripOptionCard'
import { Sparkles } from 'lucide-react'

interface OptionSelectorProps {
  options: TripOption[]
  onSelectOption: (optionId: number) => void
  onViewDetails: (optionId: number) => void
}

export const OptionSelector: React.FC<OptionSelectorProps> = ({
  options,
  onSelectOption,
  onViewDetails
}) => {
  const [selectedOptionId, setSelectedOptionId] = useState<number | null>(null)

  const handleSelect = (optionId: number) => {
    setSelectedOptionId(optionId)
    onSelectOption(optionId)
  }

  if (options.length === 0) {
    return null
  }

  return (
    <div className="w-full max-w-7xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="flex items-center justify-center mb-4">
          <Sparkles className="w-8 h-8 text-yellow-500 mr-2" />
          <h2 className="text-3xl font-bold text-gray-900">
            Your Personalized Trip Options
          </h2>
        </div>
        <p className="text-lg text-gray-600 max-w-2xl mx-auto">
          We've created 3 distinct itineraries tailored to different priorities.
          Choose the one that fits your style, or view details to see the full plan.
        </p>
      </div>

      {/* Comparison Header */}
      <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
        <p className="text-sm text-blue-900 text-center">
          💡 <strong>Tip:</strong> Budget focuses on savings, Balanced offers the best value,
          and Premium provides luxury and convenience.
        </p>
      </div>

      {/* Options Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {options.map((option) => (
          <TripOptionCard
            key={option.option_id}
            option={option}
            onSelect={handleSelect}
            onViewDetails={onViewDetails}
            isSelected={selectedOptionId === option.option_id}
          />
        ))}
      </div>

      {/* Comparison Table */}
      <div className="mt-8 bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Feature
              </th>
              {options.map((option) => (
                <th
                  key={option.option_id}
                  className={`px-6 py-3 text-left text-xs font-medium uppercase tracking-wider ${
                    selectedOptionId === option.option_id
                      ? 'bg-blue-100 text-blue-900'
                      : 'text-gray-500'
                  }`}
                >
                  {option.style}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            <tr>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                Total Cost
              </td>
              {options.map((option) => (
                <td
                  key={option.option_id}
                  className={`px-6 py-4 whitespace-nowrap text-sm ${
                    selectedOptionId === option.option_id
                      ? 'bg-blue-50 font-bold text-blue-900'
                      : 'text-gray-700'
                  }`}
                >
                  ${option.total_cost_usd.toLocaleString()}
                </td>
              ))}
            </tr>
            <tr>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                Flight
              </td>
              {options.map((option) => (
                <td
                  key={option.option_id}
                  className={`px-6 py-4 text-sm ${
                    selectedOptionId === option.option_id ? 'bg-blue-50' : ''
                  }`}
                >
                  <div className="text-gray-700">{option.flight.airline}</div>
                  <div className="text-gray-500 text-xs">
                    {option.flight.stops === 0 ? 'Direct' : `${option.flight.stops} stop(s)`}
                  </div>
                </td>
              ))}
            </tr>
            <tr>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                Hotel
              </td>
              {options.map((option) => (
                <td
                  key={option.option_id}
                  className={`px-6 py-4 text-sm ${
                    selectedOptionId === option.option_id ? 'bg-blue-50' : ''
                  }`}
                >
                  <div className="text-gray-700">{option.hotel.rating}★ Hotel</div>
                  <div className="text-gray-500 text-xs">
                    ${option.hotel.price_per_night_usd}/night
                  </div>
                </td>
              ))}
            </tr>
            <tr>
              <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                Experiences
              </td>
              {options.map((option) => (
                <td
                  key={option.option_id}
                  className={`px-6 py-4 whitespace-nowrap text-sm ${
                    selectedOptionId === option.option_id
                      ? 'bg-blue-50 text-gray-700'
                      : 'text-gray-700'
                  }`}
                >
                  {option.experiences.length} activities
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      {/* CTA for selected option */}
      {selectedOptionId !== null && (
        <div className="mt-8 p-6 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg text-white text-center">
          <h3 className="text-2xl font-bold mb-2">
            Ready to see the full itinerary?
          </h3>
          <p className="mb-4">
            View day-by-day plans and booking links for your selected option.
          </p>
          <button
            onClick={() => onViewDetails(selectedOptionId)}
            className="px-8 py-3 bg-white text-blue-600 rounded-lg font-semibold hover:bg-gray-100 transition-colors"
          >
            View Full Details →
          </button>
        </div>
      )}
    </div>
  )
}
