from urllib.parse import urlsplit


def is_safe_url(target):
    """
    Check if a redirect target is a path on this site (prevents open redirects).
    Only local paths are accepted: every ``next`` the app generates is one, and
    browsers read backslashes, extra slashes and stripped whitespace as another host.
    """
    if not isinstance(target, str) or not target.startswith("/") or target.startswith("//"):
        return False
    # isprintable() rejects control characters and every whitespace except a plain space.
    if "\\" in target or " " in target or not target.isprintable():
        return False
    parsed = urlsplit(target)
    return not parsed.scheme and not parsed.netloc
