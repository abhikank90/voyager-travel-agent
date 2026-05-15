"""
External API configuration for all travel agents.
Centralized config makes it easy to update API endpoints and keys.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class FlightAPIConfig(BaseModel):
    """Configuration for flight search APIs."""
    provider: str = Field(default="amadeus", description="API provider: amadeus, skyscanner, etc.")
    api_key: Optional[str] = Field(default=None)
    api_secret: Optional[str] = Field(default=None)
    base_url: str = Field(default="https://test.api.amadeus.com/v2")
    booking_url_template: str = Field(
        default="https://www.google.com/travel/flights?q={origin}+to+{destination}+{date}",
        description="Deep link template for flight bookings"
    )
    use_mock: bool = Field(default=False, description="Use mock data if True")

    @classmethod
    def from_env(cls) -> "FlightAPIConfig":
        return cls(
            api_key=os.getenv("AMADEUS_API_KEY"),
            api_secret=os.getenv("AMADEUS_API_SECRET"),
            use_mock=not bool(os.getenv("AMADEUS_API_KEY"))
        )


class HotelAPIConfig(BaseModel):
    """Configuration for hotel search APIs."""
    provider: str = Field(default="booking", description="API provider: booking, expedia, etc.")
    api_key: Optional[str] = Field(default=None)
    base_url: str = Field(default="https://booking-com.p.rapidapi.com/v1")
    booking_url_template: str = Field(
        default="https://www.booking.com/searchresults.html?ss={destination}&checkin={checkin}&checkout={checkout}",
        description="Deep link template for hotel bookings"
    )
    use_mock: bool = Field(default=False)

    @classmethod
    def from_env(cls) -> "HotelAPIConfig":
        return cls(
            api_key=os.getenv("BOOKING_API_KEY"),
            use_mock=not bool(os.getenv("BOOKING_API_KEY"))
        )


class WeatherAPIConfig(BaseModel):
    """Configuration for weather APIs."""
    provider: str = Field(default="openweather", description="API provider: openweather, weatherapi, etc.")
    api_key: Optional[str] = Field(default=None)
    base_url: str = Field(default="https://api.openweathermap.org/data/3.0")
    use_mock: bool = Field(default=False)

    @classmethod
    def from_env(cls) -> "WeatherAPIConfig":
        return cls(
            api_key=os.getenv("OPENWEATHER_API_KEY"),
            use_mock=not bool(os.getenv("OPENWEATHER_API_KEY"))
        )


class ExperienceAPIConfig(BaseModel):
    """Configuration for experience/activity APIs."""
    provider: str = Field(default="viator", description="API provider: viator, getyourguide, etc.")
    api_key: Optional[str] = Field(default=None)
    base_url: str = Field(default="https://viatorapi.viator.com/service")
    booking_url_template: str = Field(
        default="https://www.getyourguide.com/s/?q={destination}",
        description="Deep link template for experience bookings"
    )
    use_mock: bool = Field(default=True)  # Default to mock for now

    @classmethod
    def from_env(cls) -> "ExperienceAPIConfig":
        return cls(
            api_key=os.getenv("VIATOR_API_KEY"),
            use_mock=not bool(os.getenv("VIATOR_API_KEY"))
        )


class VisaSafetyAPIConfig(BaseModel):
    """Configuration for visa/safety information APIs."""
    provider: str = Field(default="duckduckgo", description="Search provider for visa/safety info")
    search_engine: str = Field(default="duckduckgo")
    fallback_sources: list[str] = Field(
        default=["travel.state.gov", "gov.uk/foreign-travel-advice"]
    )
    use_mock: bool = Field(default=False)

    @classmethod
    def from_env(cls) -> "VisaSafetyAPIConfig":
        return cls()


class LLMConfig(BaseModel):
    """Configuration for LLM (Claude) usage across agents."""
    api_key: str = Field(description="Anthropic API key")
    default_model: str = Field(default="claude-sonnet-4-5-20250929")
    intent_parser_model: str = Field(default="claude-sonnet-4-5-20250929")
    collaboration_hub_model: str = Field(default="claude-sonnet-4-5-20250929")
    option_generator_model: str = Field(default="claude-sonnet-4-5-20250929")
    itinerary_builder_model: str = Field(default="claude-sonnet-4-5-20250929")
    quick_tasks_model: str = Field(default="claude-haiku-4-20250514", description="For simple tasks")

    @classmethod
    def from_env(cls) -> "LLMConfig":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        return cls(api_key=api_key)


class APIConfiguration(BaseModel):
    """Central configuration for all external APIs."""
    flight: FlightAPIConfig
    hotel: HotelAPIConfig
    weather: WeatherAPIConfig
    experience: ExperienceAPIConfig
    visa_safety: VisaSafetyAPIConfig
    llm: LLMConfig

    @classmethod
    def from_env(cls) -> "APIConfiguration":
        """Load all API configs from environment variables."""
        return cls(
            flight=FlightAPIConfig.from_env(),
            hotel=HotelAPIConfig.from_env(),
            weather=WeatherAPIConfig.from_env(),
            experience=ExperienceAPIConfig.from_env(),
            visa_safety=VisaSafetyAPIConfig.from_env(),
            llm=LLMConfig.from_env()
        )

    def to_dict(self) -> dict:
        """Export config as dict for easy passing to agents."""
        return {
            "flight": self.flight.model_dump(),
            "hotel": self.hotel.model_dump(),
            "weather": self.weather.model_dump(),
            "experience": self.experience.model_dump(),
            "visa_safety": self.visa_safety.model_dump(),
            "llm": self.llm.model_dump()
        }


# Singleton instance
_config: Optional[APIConfiguration] = None


def get_api_config() -> APIConfiguration:
    """Get the global API configuration instance."""
    global _config
    if _config is None:
        _config = APIConfiguration.from_env()
    return _config


def reload_config():
    """Force reload configuration from environment."""
    global _config
    _config = APIConfiguration.from_env()
