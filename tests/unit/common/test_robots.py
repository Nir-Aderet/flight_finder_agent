from __future__ import annotations

import urllib.robotparser
from unittest.mock import MagicMock, patch

import pytest

from flight_finder.common.robots import RobotsChecker, RobotsDisallowed


def _make_parser(allowed: bool) -> urllib.robotparser.RobotFileParser:
    parser = MagicMock(spec=urllib.robotparser.RobotFileParser)
    parser.can_fetch.return_value = allowed
    return parser


class TestRobotsChecker:
    async def test_is_allowed_returns_true(self) -> None:
        with patch(
            "flight_finder.common.robots._load_robots",
            return_value=_make_parser(True),
        ):
            checker = RobotsChecker(user_agent="flight_finder")
            result = await checker.is_allowed("https://example.com", "/flights")
        assert result is True

    async def test_is_allowed_returns_false(self) -> None:
        with patch(
            "flight_finder.common.robots._load_robots",
            return_value=_make_parser(False),
        ):
            checker = RobotsChecker(user_agent="flight_finder")
            result = await checker.is_allowed("https://example.com", "/secret")
        assert result is False

    async def test_assert_allowed_passes_silently(self) -> None:
        with patch(
            "flight_finder.common.robots._load_robots",
            return_value=_make_parser(True),
        ):
            checker = RobotsChecker(user_agent="flight_finder")
            await checker.assert_allowed("https://example.com", "/ok")

    async def test_assert_allowed_raises_on_disallowed(self) -> None:
        with patch(
            "flight_finder.common.robots._load_robots",
            return_value=_make_parser(False),
        ):
            checker = RobotsChecker(user_agent="flight_finder")
            with pytest.raises(RobotsDisallowed):
                await checker.assert_allowed("https://example.com", "/blocked")

    async def test_parser_cached_across_calls(self) -> None:
        mock_parser = _make_parser(True)
        with patch(
            "flight_finder.common.robots._load_robots",
            return_value=mock_parser,
        ) as mock_load:
            checker = RobotsChecker(user_agent="flight_finder")
            await checker.is_allowed("https://example.com", "/a")
            await checker.is_allowed("https://example.com", "/b")
        # _load_robots should be called only once despite two is_allowed calls
        assert mock_load.call_count == 1

    async def test_different_hosts_fetched_separately(self) -> None:
        with patch(
            "flight_finder.common.robots._load_robots",
            return_value=_make_parser(True),
        ) as mock_load:
            checker = RobotsChecker(user_agent="flight_finder")
            await checker.is_allowed("https://alpha.com", "/x")
            await checker.is_allowed("https://beta.com", "/y")
        assert mock_load.call_count == 2

    async def test_robots_disallowed_message_contains_url(self) -> None:
        with patch(
            "flight_finder.common.robots._load_robots",
            return_value=_make_parser(False),
        ):
            checker = RobotsChecker(user_agent="bot")
            with pytest.raises(RobotsDisallowed, match="wizzair.com"):
                await checker.assert_allowed("https://wizzair.com", "/search")
