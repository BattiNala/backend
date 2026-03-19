"""Tests for user agent."""

from app.utils.user_agent import (
    get_device_type,
    is_browser_user_agent,
    is_desktop_user_agent,
    is_mobile_app_user_agent,
    is_mobile_user_agent,
)


def test_get_device_type_prioritizes_mobile_app():
    """Test get device type prioritizes mobile app."""
    user_agent = "BattinalaApp/1.0 Mozilla/5.0"

    assert get_device_type(user_agent) == "BattinalaApp"
    assert is_mobile_app_user_agent(user_agent) is True


def test_browser_mobile_and_desktop_detection():
    """Test browser mobile and desktop detection."""
    mobile = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile"
    desktop = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"

    assert is_mobile_user_agent(mobile) is True
    assert is_browser_user_agent(mobile) is True
    assert get_device_type(mobile) == "browser"

    assert is_desktop_user_agent(desktop) is True
    assert is_browser_user_agent(desktop) is True
    assert get_device_type(desktop) == "browser"


def test_unknown_device_type_for_empty_string():
    """Test unknown device type for empty string."""
    assert get_device_type("") == "unknown"
