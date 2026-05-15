/**
 * Tests for TripOptionCard component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TripOptionCard } from '../TripOptionCard'
import { TripOption } from '../../types'

const mockBudgetOption: TripOption = {
  option_id: 0,
  style: 'budget',
  title: 'Budget Explorer - Greece',
  total_cost_usd: 1500,
  flight: {
    airline: 'Budget Air',
    price: 450,
    stops: 2,
    duration: '18h',
    departure_time: '22:00',
    arrival_time: '04:00'
  },
  hotel: {
    name: 'Budget Inn',
    price_per_night: 60,
    rating: 3.5,
    location: 'Athens',
    amenities: ['WiFi']
  },
  experiences: [],
  day_by_day: [],
  flight_booking_url: 'https://google.com/flights',
  hotel_booking_url: 'https://booking.com',
  highlights: ['Save $500', 'Local experiences'],
  trade_offs: ['2 stop flight', 'Basic hotel']
}

const mockPremiumOption: TripOption = {
  option_id: 2,
  style: 'premium',
  title: 'Premium Luxury - Greece',
  total_cost_usd: 2300,
  flight: {
    airline: 'Delta',
    price: 850,
    stops: 0,
    duration: '10h 30m',
    departure_time: '08:00',
    arrival_time: '10:00'
  },
  hotel: {
    name: 'Luxury Resort',
    price_per_night: 250,
    rating: 4.9,
    location: 'Santorini',
    amenities: ['Beach Access', 'Spa', 'Pool']
  },
  experiences: [],
  day_by_day: [],
  flight_booking_url: 'https://google.com/flights',
  hotel_booking_url: 'https://booking.com',
  highlights: ['Direct flight', 'Luxury resort', 'Exclusive tours'],
  trade_offs: ['$300 over budget']
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

    // Check for budget-specific styling class
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

    // Check for premium-specific styling class
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

    // Should have selected state styling
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
