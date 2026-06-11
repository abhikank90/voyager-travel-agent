import React, { useState } from 'react'
import { TripOption } from '../types'
import {
  ArrowLeft,
  ExternalLink,
  Plane,
  Hotel,
  MapPin,
  Calendar,
  DollarSign,
  Sun,
  Moon,
  Coffee,
  Utensils,
  ChevronDown,
  ChevronUp
} from 'lucide-react'

interface DetailedItineraryViewProps {
  option: TripOption
  onBack: () => void
  onRequestRefinement: (refinementQuery: string) => void
}

export const DetailedItineraryView: React.FC<DetailedItineraryViewProps> = ({
  option,
  onBack,
  onRequestRefinement
}) => {
  const [expandedDay, setExpandedDay] = useState<number | null>(null)
  const [refinementInput, setRefinementInput] = useState('')

  const toggleDay = (day: number) => {
    setExpandedDay(expandedDay === day ? null : day)
  }

  const handleRefinement = () => {
    if (refinementInput.trim()) {
      onRequestRefinement(refinementInput)
      setRefinementInput('')
    }
  }

  const styleColors = {
    budget: 'from-green-500 to-green-600',
    balanced: 'from-blue-500 to-blue-600',
    premium: 'from-purple-500 to-purple-600'
  }

  return (
    <div className="w-full max-w-6xl mx-auto py-8 px-4">
      {/* Back Button */}
      <button
        onClick={onBack}
        className="mb-6 flex items-center text-gray-600 hover:text-gray-900 transition-colors"
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to Options
      </button>

      {/* Header */}
      <div className={`bg-gradient-to-r ${styleColors[option.style]} text-white rounded-lg p-8 mb-8`}>
        <div className="flex justify-between items-start">
          <div>
            <span className="px-3 py-1 bg-white bg-opacity-20 rounded-full text-sm font-semibold">
              {option.style.charAt(0).toUpperCase() + option.style.slice(1)}
            </span>
            <h1 className="text-4xl font-bold mt-4 mb-2">{option.title}</h1>
            <p className="text-lg opacity-90">{option.description}</p>
          </div>
          <div className="text-right">
            <div className="text-sm opacity-75">Total Cost</div>
            <div className="text-4xl font-bold">${option.total_cost_usd.toLocaleString()}</div>
            <div className="text-sm opacity-75 mt-1">{option.itinerary.num_days} days</div>
          </div>
        </div>
      </div>

      {/* Quick Booking Links */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {/* Flight Booking */}
        <a
          href={option.flight_booking_url || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-between p-4 bg-white border-2 border-blue-200 rounded-lg hover:border-blue-400 hover:shadow-md transition-all group"
        >
          <div className="flex items-center">
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
              <Plane className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <div className="font-semibold text-gray-900">Book Flight</div>
              <div className="text-sm text-gray-600">${option.flight.price_usd}</div>
            </div>
          </div>
          <ExternalLink className="w-5 h-5 text-gray-400 group-hover:text-blue-600" />
        </a>

        {/* Hotel Booking */}
        <a
          href={option.hotel_booking_url || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-between p-4 bg-white border-2 border-green-200 rounded-lg hover:border-green-400 hover:shadow-md transition-all group"
        >
          <div className="flex items-center">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mr-3">
              <Hotel className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <div className="font-semibold text-gray-900">Book Hotel</div>
              <div className="text-sm text-gray-600">
                ${option.hotel.price_per_night_usd}/night
              </div>
            </div>
          </div>
          <ExternalLink className="w-5 h-5 text-gray-400 group-hover:text-green-600" />
        </a>

        {/* Experiences Booking */}
        <a
          href={option.experience_booking_urls[0] || '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-between p-4 bg-white border-2 border-purple-200 rounded-lg hover:border-purple-400 hover:shadow-md transition-all group"
        >
          <div className="flex items-center">
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mr-3">
              <MapPin className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <div className="font-semibold text-gray-900">Book Experiences</div>
              <div className="text-sm text-gray-600">{option.experiences.length} activities</div>
            </div>
          </div>
          <ExternalLink className="w-5 h-5 text-gray-400 group-hover:text-purple-600" />
        </a>
      </div>

      {/* Budget Breakdown */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <DollarSign className="w-5 h-5 mr-2" />
          Budget Breakdown
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div>
            <div className="text-sm text-gray-600">Flight</div>
            <div className="text-lg font-bold text-gray-900">
              ${option.itinerary.breakdown.flight}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Hotel</div>
            <div className="text-lg font-bold text-gray-900">
              ${option.itinerary.breakdown.hotel}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Experiences</div>
            <div className="text-lg font-bold text-gray-900">
              ${option.itinerary.breakdown.experiences}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Food</div>
            <div className="text-lg font-bold text-gray-900">
              ${option.itinerary.breakdown.food}
            </div>
          </div>
          <div>
            <div className="text-sm text-gray-600">Misc</div>
            <div className="text-lg font-bold text-gray-900">
              ${option.itinerary.breakdown.misc}
            </div>
          </div>
        </div>
      </div>

      {/* Day-by-Day Itinerary */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
        <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
          <Calendar className="w-5 h-5 mr-2" />
          Day-by-Day Itinerary
        </h2>
        <div className="space-y-3">
          {option.day_by_day.map((day) => (
            <div key={day.day} className="border border-gray-200 rounded-lg overflow-hidden">
              {/* Day Header */}
              <button
                onClick={() => toggleDay(day.day)}
                className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="flex items-center">
                  <div className="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold mr-3">
                    {day.day}
                  </div>
                  <div className="text-left">
                    <div className="font-semibold text-gray-900">{day.date}</div>
                    <div className="text-sm text-gray-600">{day.notes || 'Tap to expand'}</div>
                  </div>
                </div>
                {expandedDay === day.day ? (
                  <ChevronUp className="w-5 h-5 text-gray-600" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-gray-600" />
                )}
              </button>

              {/* Day Details */}
              {expandedDay === day.day && (
                <div className="p-4 space-y-4">
                  {/* Morning */}
                  <div className="flex items-start">
                    <div className="w-10 h-10 bg-yellow-100 rounded-lg flex items-center justify-center mr-3 flex-shrink-0">
                      <Sun className="w-5 h-5 text-yellow-600" />
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 mb-1">Morning</div>
                      <div className="text-gray-700">{day.morning}</div>
                    </div>
                  </div>

                  {/* Afternoon */}
                  <div className="flex items-start">
                    <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center mr-3 flex-shrink-0">
                      <Sun className="w-5 h-5 text-orange-600" />
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 mb-1">Afternoon</div>
                      <div className="text-gray-700">{day.afternoon}</div>
                    </div>
                  </div>

                  {/* Evening */}
                  <div className="flex items-start">
                    <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center mr-3 flex-shrink-0">
                      <Moon className="w-5 h-5 text-indigo-600" />
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900 mb-1">Evening</div>
                      <div className="text-gray-700">{day.evening}</div>
                    </div>
                  </div>

                  {/* Meals */}
                  <div className="border-t border-gray-200 pt-4">
                    <div className="font-semibold text-gray-900 mb-2 flex items-center">
                      <Utensils className="w-4 h-4 mr-2" />
                      Meals
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div>
                        <Coffee className="w-3 h-3 inline mr-1 text-gray-600" />
                        <span className="text-gray-700">{day.meals.breakfast}</span>
                      </div>
                      <div>
                        <Utensils className="w-3 h-3 inline mr-1 text-gray-600" />
                        <span className="text-gray-700">{day.meals.lunch}</span>
                      </div>
                      <div>
                        <Utensils className="w-3 h-3 inline mr-1 text-gray-600" />
                        <span className="text-gray-700">{day.meals.dinner}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Refinement Section */}
      <div className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-lg border-2 border-blue-200 p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-2">Want to Make Changes?</h2>
        <p className="text-gray-600 mb-4">
          Ask for modifications like "Use the hotel from the premium option" or "Add more museums
          instead of beaches"
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={refinementInput}
            onChange={(e) => setRefinementInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleRefinement()}
            placeholder="e.g., Use cheaper hotel from budget option..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleRefinement}
            disabled={!refinementInput.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            Refine
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            onClick={() => setRefinementInput('Use the hotel from the budget option')}
            className="px-3 py-1 text-sm bg-white border border-gray-300 rounded-full hover:bg-gray-50"
          >
            Use budget hotel
          </button>
          <button
            onClick={() => setRefinementInput('Add more cultural experiences')}
            className="px-3 py-1 text-sm bg-white border border-gray-300 rounded-full hover:bg-gray-50"
          >
            More culture
          </button>
          <button
            onClick={() => setRefinementInput('Find a direct flight instead')}
            className="px-3 py-1 text-sm bg-white border border-gray-300 rounded-full hover:bg-gray-50"
          >
            Direct flight
          </button>
        </div>
      </div>
    </div>
  )
}
