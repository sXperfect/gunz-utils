"""Dependency-free URI construction and TCP reachability helpers."""

from __future__ import annotations

import ipaddress
import math
import re
import socket
from collections.abc import Mapping, Sequence
from urllib.parse import quote, urlencode, urlunsplit

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*$")


def build_network_uri(
    scheme: str,
    host: str,
    *,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    path: str = "",
    query: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
) -> str:
    """Build a standards-oriented URI with an authority component.

    Parameters
    ----------
    scheme : str
        URI scheme such as http, https, postgresql, or redis.
    host : str
        Hostname, IPv4 address, or IPv6 address. Bare IPv6 addresses are
        bracketed automatically.
    port : int | None, optional
        Network port in the inclusive range 1..65535.
    username : str | None, optional
        Username encoded into URI user-info.
    password : str | None, optional
        Password encoded into URI user-info. A password requires a username.
    path : str, optional
        URI path. A leading slash is added when absent and the path is nonempty.
    query : Mapping[str, object] | Sequence[tuple[str, object]] | None, optional
        Query parameters encoded with urllib.parse.urlencode.

    Returns
    -------
    str
        Constructed URI.

    Raises
    ------
    ValueError
        If scheme, host, port, or user-info configuration is invalid.

    Notes
    -----
    This helper follows ordinary URI authority semantics. Backend-specific DSN
    conventions such as SQLAlchemy SQLite triple-slash URLs should be handled
    by the owning integration rather than special-cased here.
    """
    if not isinstance(scheme, str) or not _SCHEME_RE.fullmatch(scheme):
        raise ValueError("scheme must be a valid URI scheme")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a non-empty string")
    normalized_host = host.strip()
    if any(character.isspace() for character in normalized_host):
        raise ValueError("host must not contain whitespace")
    if "\\" in normalized_host or any(
        ord(character) < 0x20 or ord(character) == 0x7F
        for character in normalized_host
    ):
        raise ValueError("host contains invalid authority characters")
    if any(character in normalized_host for character in "@/?#%"):
        raise ValueError("host contains invalid authority delimiters")
    if normalized_host.startswith("[") != normalized_host.endswith("]"):
        raise ValueError("IPv6 host brackets must be balanced")

    if normalized_host.startswith("["):
        inner = normalized_host[1:-1]
        try:
            parsed = ipaddress.ip_address(inner)
        except ValueError as exc:
            raise ValueError("bracketed host must be a valid IPv6 address") from exc
        if parsed.version != 6:
            raise ValueError("bracketed host must be a valid IPv6 address")
        normalized_host = f"[{parsed.compressed}]"
    elif ":" in normalized_host:
        try:
            parsed = ipaddress.ip_address(normalized_host)
        except ValueError as exc:
            raise ValueError(
                "host containing ':' must be a valid IPv6 address"
            ) from exc
        if parsed.version != 6:
            raise ValueError(
                "host containing ':' must be a valid IPv6 address"
            )
        normalized_host = f"[{parsed.compressed}]"
    else:
        try:
            normalized_host = normalized_host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise ValueError("host is not a valid DNS name") from exc
    if port is not None and (
        isinstance(port, bool)
        or not isinstance(port, int)
        or not 1 <= port <= 65535
    ):
        raise ValueError("port must be an integer in the range 1..65535")
    if username is not None and not username:
        raise ValueError("username must not be empty")
    if password is not None and username is None:
        raise ValueError("password requires username")
    if not isinstance(path, str):
        raise TypeError("path must be a string")

    userinfo = ""
    if username is not None:
        userinfo = quote(username, safe="")
        if password is not None:
            userinfo += ":" + quote(password, safe="")
        userinfo += "@"

    authority = userinfo + normalized_host
    if port is not None:
        authority += f":{port}"

    normalized_path = path
    if normalized_path and not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path
    encoded_path = quote(normalized_path, safe="/:@")

    encoded_query = (
        urlencode(query, doseq=True)
        if query is not None
        else ""
    )
    return urlunsplit(
        (
            scheme.casefold(),
            authority,
            encoded_path,
            encoded_query,
            "",
        )
    )


def tcp_reachable(
    host: str,
    port: int,
    *,
    timeout: float = 5.0,
    allow_private: bool = True,
) -> bool:
    """Return whether a TCP connection can be established within a timeout.

    Parameters
    ----------
    host : str
        Hostname or IP address.
    port : int
        TCP port in the inclusive range 1..65535.
    timeout : float, optional
        Connection timeout in seconds. Must be positive.

    Returns
    -------
    bool
        True when a connection succeeds, otherwise False.

    Raises
    ------
    ValueError
        If host, port, or timeout is invalid.
    """
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a non-empty string")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("port must be an integer in the range 1..65535")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout <= 0
    ):
        raise ValueError("timeout must be a finite positive number")

    # ? Security (VULN-2026-007): Optionally restrict connections to private/loopback IP ranges
    # ? to prevent Server-Side Request Forgery (SSRF) when target parameters come from untrusted users.
    if not isinstance(allow_private, bool):
        raise TypeError("allow_private must be bool")

    target_host = host.strip()
    if not allow_private:
        try:
            ip = ipaddress.ip_address(target_host)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError("connection to private/loopback IP addresses is disallowed")
        except ValueError:
            if target_host.lower() in ("localhost", "loopback"):
                raise ValueError("connection to localhost is disallowed")

    try:
        with socket.create_connection(
            (target_host, port),
            timeout=timeout,
        ):
            return True
    except OSError:
        return False


__all__ = ["build_network_uri", "tcp_reachable"]
