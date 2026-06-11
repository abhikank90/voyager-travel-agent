import React from 'react'
import { TripOption } from '../types'
import { Plane, Hotel, MapPin, CheckCircle, AlertCircle } from 'lucide-react'

interface TripOptionCardProps {
  option: TripOption
  onSelect: (optionId: number) => void
  onViewDetails: (optionId: number) => void
  isSelected?: boolean
}

export const TripOptionCard: React.FC<TripOptionCardProps> = ({
  option,
  onSelect,
  onViewDetails,
  isSelected = false
}) => {
  const styleColors = {
    budget: {
      bg: 'bg-green-50',
      border: 'border-green-300',
      badge: 'bg-green-100 text-green-800',
      button: 'bg-green-600 hover:bg-green-700'
    },
    balanced: {
      bg: 'bg-blue-50',
      border: 'border-blue-300',
      badge: 'bg-blue-100 text-blue-800',
      button: 'bg-blue-600 hover:bg-blue-700'
    },
    premium: {
      bg: 'bg-purple-50',
      border: 'border-purple-300',
      badge: 'bg-purple-100 text-purple-800',
      button: 'bg-purple-600 hover:bg-purple-700'
    }
  }

  const colors = styleColors[option.style]

  return (
    <div
      className={`rounded-lg border-2 p-6 transition-all ${colors.bg} ${
        isSelected ? 'border-4 border-blue-600 shadow-xl' : colors.border
      } hover:shadow-lg`}
    >
      {/* Header */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${colors.badge}`}>
            {option.style.charAt(0).toUpperCase() + option.style.slice(1)}
          </span>
          {isSelected && (
            <CheckCircle className="w-6 h-6 text-blue-600" />
          )}
        </div>
        <h3 className="text-2xl font-bold text-gray-900 mb-2">{option.title}</h3>
        <p className="text-gray-600">{option.description}</p>
      </div>

      {/* Price */}
      <div className="mb-6 p-4 bg-white rounded-lg">
        <div className="flex items-center justify-between">
          <span className="text-gray-600 font-medium">Total Cost</span>
          <span className="text-3xl font-bold text-gray-900">
            ${option.total_cost_usd.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Quick Info */}
      <div className="space-y-3 mb-6">
        <div className="flex items-center text-sm text-gray-700">
          <Plane className="w-4 h-4 mr-2 text-gray-500" />
          <span className="font-medium">{option.flight.airline}</span>
          <span className="mx-2">•</span>
          <span>${option.flight.price_usd}</span>
          <span className="mx-2">•</span>
          <span>{option.flight.stops === 0 ? 'Direct' : `${option.flight.stops} stop(s)`}</span>
        </div>

        <div className="flex items-center text-sm text-gray-700">
          <Hotel className="w-4 h-4 mr-2 text-gray-500" />
          <span className="font-medium">{option.hotel.name}</span>
          <span className="mx-2">•</span>
          <span>{option.hotel.rating}★</span>
          <span className="mx-2">•</span>
          <span>${option.hotel.price_per_night_usd}/night</span>
        </div>

        <div className="flex items-center text-sm text-gray-700">
          <MapPin className="w-4 h-4 mr-2 text-gray-500" />
          <span>{option.experiences.length} experiences included</span>
        </div>
      </div>

      {/* Highlights */}
      <div className="mb-4">
        <h4 className="font-semibold text-gray-900 mb-2 flex items-center">
          <CheckCircle className="w-4 h-4 mr-1 text-green-600" />
          Highlights
        </h4>
        <ul className="space-y-1">
          {option.highlights.slice(0, 3).map((highlight, idx) => (
            <li key={idx} className="text-sm text-gray-700 flex items-start">
              <span className="text-green-600 mr-2">✓</span>
              <span>{highlight}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* Trade-offs */}
      {option.trade_offs.length > 0 && (
        <div className="mb-6">
          <h4 className="font-semibold text-gray-900 mb-2 flex items-center">
            <AlertCircle className="w-4 h-4 mr-1 text-orange-600" />
            Trade-offs
          </h4>
          <ul className="space-y-1">
            {option.trade_offs.slice(0, 2).map((tradeOff, idx) => (
              <li key={idx} className="text-sm text-gray-600 flex items-start">
                <span className="text-orange-600 mr-2">→</span>
                <span>{tradeOff}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Budget Breakdown */}
      <div className="mb-6 p-3 bg-white rounded-lg">
        <h4 className="font-semibold text-gray-900 mb-2 text-sm">Budget Breakdown</h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex justify-between">
            <span className="text-gray-600">Flight</span>
            <span className="font-medium">${option.itinerary.breakdown.flight}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Hotel</span>
            <span className="font-medium">${option.itinerary.breakdown.hotel}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Activities</span>
            <span className="font-medium">${option.itinerary.breakdown.experiences}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Food</span>
            <span className="font-medium">${option.itinerary.breakdown.food}</span>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="space-y-2">
        <button
          onClick={() => onViewDetails(option.option_id)}
          className="w-full px-4 py-3 bg-white border-2 border-gray-300 text-gray-700 rounded-lg font-semibold hover:bg-gray-50 transition-colors"
        >
          View Full Details
        </button>
        <button
          onClick={() => onSelect(option.option_id)}
          className={`w-full px-4 py-3 text-white rounded-lg font-semibold transition-colors ${colors.button}`}
        >
          {isSelected ? 'Selected ✓' : 'Select This Option'}
        </button>
      </div>
    </div>
  )
}
