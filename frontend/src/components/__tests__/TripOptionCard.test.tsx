/**
 * Tests for TripOptionCard component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TripOptionCard } from '../TripOptionCard'
import { TripOption } from '../../types'

const mockItinerary = {
  num_days: 7,
  destination: 'Greece',
  style: 'budget' as const,
  total_cost: 1500,
  breakdown: { flight: 450, hotel: 420, experiences: 200, food: 280, misc: 150 },
}

const mockBudgetOption: TripOption = {
  option_id: 0,
  style: 'budget',
  title: 'Budget Explorer - Greece',
  description: 'Affordable trip to Greece',
  total_cost_usd: 1500,
  flight: {
    airline: 'Budget Air',
    price_usd: 450,
    stops: 2,
    duration: '18h',
    departure: '2026-07-01T22:00:00',
    arrival: '2026-07-02T04:00:00',
  },
  hotel: {
    name: 'Budget Inn',
    price_per_night_usd: 60,
    total_usd: 420,
    rating: 3.5,
    location: 'Athens',
    amenities: ['WiFi'],
  },
  experiences: [],
  itinerary: mockItinerary,
  day_by_day: [],
  flight_booking_url: 'https://google.com/flights',
  hotel_booking_url: 'https://booking.com',
  experience_booking_urls: [],
  highlights: ['Save $500', 'Local experiences'],
  trade_offs: ['2 stop flight', 'Basic hotel'],
}

const mockPremiumOption: TripOption = {
  option_id: 2,
  style: 'premium',
  title: 'Premium Luxury - Greece',
  description: 'Luxury escape to Greece',
  total_cost_usd: 2300,
  flight: {
    airline: 'Delta',
    price_usd: 850,
    stops: 0,
    duration: '10h 30m',
    departure: '2026-07-01T08:00:00',
    arrival: '2026-07-01T22:30:00',
  },
  hotel: {
    name: 'Luxury Resort',
    price_per_night_usd: 250,
    total_usd: 1750,
    rating: 4.9,
    location: 'Santorini',
    amenities: ['Beach Access', 'Spa', 'Pool'],
  },
  experiences: [],
  itinerary: { ...mockItinerary, style: 'premium', total_cost: 2300 },
  day_by_day: [],
  flight_booking_url: 'https://google.com/flights',
  hotel_booking_url: 'https://booking.com',
  experience_booking_urls: [],
  highlights: ['Direct flight', 'Luxury resort', 'Exclusive tours'],
  trade_offs: ['$300 over budget'],
}

describe('TripOptionCard', () => {
  it('renders option title', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText('Budget Explorer - Greece')).toBeInTheDocument()
  })

  it('displays total cost', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText(/\$1,500/)).toBeInTheDocument()
  })

  it('shows flight information', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText(/Budget Air/)).toBeInTheDocument()
    expect(screen.getByText(/\$450/)).toBeInTheDocument()
  })

  it('shows hotel information', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText(/Budget Inn/)).toBeInTheDocument()
    expect(screen.getByText(/\$60/)).toBeInTheDocument()
  })

  it('displays highlights', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText(/Save \$500/)).toBeInTheDocument()
    expect(screen.getByText(/Local experiences/)).toBeInTheDocument()
  })

  it('displays trade-offs', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText(/2 stop flight/)).toBeInTheDocument()
    expect(screen.getByText(/Basic hotel/)).toBeInTheDocument()
  })

  it('calls onSelect when Select button clicked', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    const selectButton = screen.getByRole('button', { name: /select/i })
    fireEvent.click(selectButton)

    expect(mockSelect).toHaveBeenCalledWith(0)
  })

  it('calls onViewDetails when View Details button clicked', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    const viewButton = screen.getByRole('button', { name: /view.*details/i })
    fireEvent.click(viewButton)

    expect(mockViewDetails).toHaveBeenCalledWith(0)
  })

  it('applies green styling for budget option', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    const { container } = render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    const card = container.firstChild
    expect(card).toHaveClass(/green/i)
  })

  it('applies purple styling for premium option', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    const { container } = render(
      <TripOptionCard
        option={mockPremiumOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    const card = container.firstChild
    expect(card).toHaveClass(/purple/i)
  })

  it('highlights card when selected', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    const { container } = render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
        isSelected={true}
      />
    )

    const card = container.firstChild
    expect(card).toHaveClass(/selected|ring|border/)
  })

  it('shows hotel rating', () => {
    const mockSelect = vi.fn()
    const mockViewDetails = vi.fn()

    render(
      <TripOptionCard
        option={mockBudgetOption}
        onSelect={mockSelect}
        onViewDetails={mockViewDetails}
      />
    )

    expect(screen.getByText(/3\.5/)).toBeInTheDocument()
  })
})
