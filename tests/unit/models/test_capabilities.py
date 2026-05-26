from __future__ import annotations

import pytest
from pydantic import ValidationError

from flight_finder.models.capabilities import AdapterCapabilities


class TestAdapterCapabilities:
    def test_minimal(self) -> None:
        cap = AdapterCapabilities(name="google_flights")
        assert cap.name == "google_flights"
        assert cap.supported_cabin_classes == []
        assert cap.supports_multi_city is False
        assert cap.supported_regions == []
        assert cap.max_passengers == 9
        assert cap.supported_currencies == []

    def test_google_flights_profile(self) -> None:
        cap = AdapterCapabilities(
            name="google_flights",
            supported_cabin_classes=["economy", "premium", "business", "first"],
            supports_multi_city=True,
            max_passengers=9,
        )
        assert cap.supports_multi_city is True
        assert "business" in cap.supported_cabin_classes

    def test_wizz_air_profile(self) -> None:
        cap = AdapterCapabilities(
            name="wizz_air",
            supported_cabin_classes=["economy"],
            supported_regions=["EU", "CEE"],
            supports_multi_city=False,
            max_passengers=6,
            supported_currencies=["EUR", "GBP", "PLN"],
        )
        assert cap.supported_regions == ["EU", "CEE"]
        assert cap.max_passengers == 6
        assert "EUR" in cap.supported_currencies

    def test_max_passengers_min_one(self) -> None:
        cap = AdapterCapabilities(name="kayak", max_passengers=1)
        assert cap.max_passengers == 1

    def test_max_passengers_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            AdapterCapabilities(name="kayak", max_passengers=0)

    def test_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            AdapterCapabilities()  # type: ignore[call-arg]

    def test_regions_empty_means_global(self) -> None:
        cap = AdapterCapabilities(name="kayak", supported_regions=[])
        assert cap.supported_regions == []
