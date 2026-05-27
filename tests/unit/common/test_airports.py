from __future__ import annotations

from flight_finder.common.airports import adapter_covers_route, route_region


class TestRouteRegion:
    def test_trans_atlantic(self) -> None:
        regions = route_region("SFO", "CDG")
        assert "NA" in regions
        assert "EU" in regions

    def test_intra_eu(self) -> None:
        regions = route_region("LTN", "BUD")
        assert regions == frozenset({"EU"})

    def test_na_to_apac(self) -> None:
        regions = route_region("LAX", "NRT")
        assert "NA" in regions
        assert "APAC" in regions

    def test_unknown_code_excluded(self) -> None:
        regions = route_region("XXX", "CDG")
        assert "EU" in regions
        assert len(regions) == 1  # only CDG contributes

    def test_both_unknown(self) -> None:
        assert route_region("XXX", "YYY") == frozenset()

    def test_eu_to_mea(self) -> None:
        regions = route_region("LTN", "TLV")
        assert "EU" in regions
        assert "MEA" in regions


class TestAdapterCoversRoute:
    def test_empty_regions_is_global(self) -> None:
        assert adapter_covers_route([], "SFO", "CDG") is True

    def test_eu_adapter_intra_eu(self) -> None:
        assert adapter_covers_route(["EU"], "LTN", "BUD") is True

    def test_eu_adapter_trans_atlantic(self) -> None:
        # SFO is NA, not EU — Wizz Air should be excluded
        assert adapter_covers_route(["EU"], "SFO", "CDG") is False

    def test_eu_mea_adapter_eu_to_mea(self) -> None:
        assert adapter_covers_route(["EU", "MEA"], "LTN", "TLV") is True

    def test_eu_mea_adapter_trans_atlantic(self) -> None:
        assert adapter_covers_route(["EU", "MEA"], "JFK", "LHR") is False

    def test_global_adapter_any_route(self) -> None:
        assert adapter_covers_route(["NA", "EU", "APAC", "LATAM", "MEA", "AF"], "SFO", "CDG") is True
        assert adapter_covers_route(["NA", "EU", "APAC", "LATAM", "MEA", "AF"], "LAX", "NRT") is True

    def test_unknown_origin_returns_false(self) -> None:
        assert adapter_covers_route(["EU"], "XXX", "CDG") is False

    def test_unknown_dest_returns_false(self) -> None:
        assert adapter_covers_route(["EU"], "LTN", "XXX") is False

    def test_na_adapter_trans_atlantic(self) -> None:
        # Both endpoints in NA → covered
        assert adapter_covers_route(["NA"], "JFK", "LAX") is True

    def test_na_adapter_intra_eu(self) -> None:
        assert adapter_covers_route(["NA"], "LTN", "BUD") is False
