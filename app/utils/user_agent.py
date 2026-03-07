"""
User agent utility functions.
"""


def get_device_type(user_agent: str) -> str:
    """Determine the device type based on the user agent string."""
    if is_mobile_user_agent(user_agent):
        return "mobile"
    elif is_desktop_user_agent(user_agent):
        return "desktop"
    elif is_browser_user_agent(user_agent):
        return "browser"
    else:
        return "unknown"


def is_mobile_user_agent(user_agent: str) -> bool:
    """Determine if the user agent string corresponds to a mobile device."""
    mobile_indicators = [
        "Mobile",
        "Android",
        "iPhone",
        "iPad",
        "iPod",
        "BlackBerry",
        "Windows Phone",
    ]
    return any(indicator in user_agent for indicator in mobile_indicators)


def is_desktop_user_agent(user_agent: str) -> bool:
    """Determine if the user agent string corresponds to a desktop device."""
    desktop_indicators = [
        "Windows NT",
        "Macintosh",
        "Linux",
        "X11",
    ]
    return any(indicator in user_agent for indicator in desktop_indicators)


def is_browser_user_agent(user_agent: str) -> bool:
    """Determine if the user agent string corresponds to a web browser."""
    browser_indicators = [
        "Mozilla",
        "Chrome",
        "Safari",
        "Firefox",
        "Edge",
        "Opera",
    ]
    return any(indicator in user_agent for indicator in browser_indicators)


def mobile_app_user_agent(user_agent: str) -> bool:
    """Determine if the user agent string corresponds to a mobile app."""
    app_indicators = [
        "BattinalaApp",
        "MyBattinalaApp",
    ]
    return any(indicator in user_agent for indicator in app_indicators)
