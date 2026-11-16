"""Dependency-free URI construction and TCP reachability helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import ipaddress
import math
import re
import socket
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

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
        #? IDNA can map Unicode characters into authority delimiters. Validate
        #? the actual encoded host before combining distinct URI components.
        if any(character in normalized_host for character in "@/?#%:[]"):
            raise ValueError("host contains invalid authority delimiters")
        if "\\" in normalized_host or any(
            character.isspace() or ord(character) < 0x20 or ord(character) == 0x7F
            for character in normalized_host
        ):
            raise ValueError("host contains invalid authority characters")
    if port is not None and (
        isinstance(port, bool)
        or not isinstance(port, int)
        or not 1 <= port <= 65535
    ):
        raise ValueError("port must be an integer in the range 1..65535")
    if username is not None:
        if not isinstance(username, str):
            raise TypeError("username must be a string")
        if not username:
            raise ValueError("username must not be empty")
        if any(character in username for character in "\r\n\0"):
            raise ValueError("username contains invalid control characters")
    if password is not None:
        if not isinstance(password, str):
            raise TypeError("password must be a string")
        if username is None:
            raise ValueError("password requires username")
        if any(character in password for character in "\r\n\0"):
            raise ValueError("password contains invalid control characters")
    if not isinstance(path, str):
        raise TypeError("path must be a string")
    if query is not None:
        if isinstance(query, (str, bytes, bytearray)):
            raise TypeError(
                "query must be a Mapping or Sequence of pairs, not a string")
        if not isinstance(query, (Mapping, Sequence)):
            raise TypeError("query must be a Mapping or Sequence of pairs")

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


def _is_non_public_address(
    address: str,
) -> bool:
    """Return whether an IP address is unsafe for an external-only probe.

    Parameters
    ----------
    address : str
        address parameter.

    Returns
    -------
    bool
        The result of the operation.
    """
    normalized = address.split("%", 1)[0]
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    ip = ipaddress.ip_address(normalized)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_reserved
    )


def tcp_reachable(
    host: str,
    port: int,
    *,
    timeout: float = 5.0,
    allow_private: bool = True,
) -> bool:
    """Return whether a TCP connection can be established within a timeout.

    When allow_private is false, all resolved addresses are checked before any
    connection is attempted. The connection is then made to the validated
    numeric address, preventing a second DNS lookup from bypassing the policy.
    """
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a non-empty string")
    if (
        isinstance(port, bool)
        or not isinstance(port, int)
        or not 1 <= port <= 65535
    ):
        raise ValueError("port must be an integer in the range 1..65535")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout <= 0
    ):
        raise ValueError("timeout must be a finite positive number")
    if not isinstance(allow_private, bool):
        raise TypeError("allow_private must be bool")

    target_host = host.strip()
    if target_host.startswith("[") and target_host.endswith("]"):
        target_host = target_host[1:-1]
    if allow_private:
        try:
            with socket.create_connection(
                (target_host, port),
                timeout=timeout,
            ):
                return True
        except OSError:
            return False

    try:
        literal = ipaddress.ip_address(target_host.split("%", 1)[0])
    except ValueError:
        try:
            address_info = socket.getaddrinfo(
                target_host,
                port,
                type=socket.SOCK_STREAM,
            )
        except OSError:
            return False
        resolved_values: list[str] = []
        for info in address_info:
            address = info[4][0]
            if isinstance(address, str):
                resolved_values.append(address)
        resolved = tuple(dict.fromkeys(resolved_values))
    else:
        resolved = (str(literal),)

    if not resolved:
        return False
    if any(_is_non_public_address(address) for address in resolved):
        raise ValueError(
            "connection to non-public IP addresses is disallowed"
        )

    deadline = time.monotonic() + float(timeout)
    for address in resolved:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return False
        try:
            with socket.create_connection(
                (address, port),
                timeout=remaining,
            ):
                return True
        except OSError:
            continue
    return False


@dataclass(frozen=True, slots=True)
class ParsedURI:
    """Parsed network URI components."""

    scheme: str
    host: str
    port: int | None
    path: str
    query: str
    fragment: str
    username: str | None = None


def parse_network_uri(
    uri: str,
) -> ParsedURI:
    """Strictly parse a network URI into components, validating scheme and host."""
    if not isinstance(uri, str) or not uri.strip():
        raise ValueError("uri must be a non-empty string")
    parts = urlsplit(uri.strip())
    if not parts.scheme or not _SCHEME_RE.fullmatch(parts.scheme):
        raise ValueError(f"invalid URI scheme: {parts.scheme!r}")
    if not parts.hostname:
        raise ValueError("URI must contain a valid host")
    return ParsedURI(
        scheme=parts.scheme,
        host=parts.hostname,
        port=parts.port,
        path=parts.path,
        query=parts.query,
        fragment=parts.fragment,
        username=parts.username,
    )


def is_public_ip(
    address: str,
) -> bool:
    """Return True if an IP address is globally routable (not private, loopback, or
    reserved).
    """
    try:
        return not _is_non_public_address(address)
    except ValueError:
        return False


def is_loopback_host(
    host: str,
) -> bool:
    """Return True if host resolves syntactically to a loopback address or localhost."""
    if not isinstance(host, str):
        return False
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    if h in ("localhost", "localhost.localdomain"):
        return True
    try:
        ip = ipaddress.ip_address(h.split("%", 1)[0])
        return ip.is_loopback
    except ValueError:
        return False


def sanitize_uri(
    uri: str,
    replacement: str = "***",
) -> str:
    """Redact embedded credentials from a URI string."""
    if not isinstance(uri, str):
        raise TypeError(f"expected str, got {type(uri).__name__}")
    parts = urlsplit(uri)
    if not parts.netloc or ("@" not in parts.netloc):
        return uri
    userinfo, host = parts.netloc.rsplit("@", 1)
    if ":" in userinfo:
        user, _ = userinfo.split(":", 1)
        redacted_userinfo = f"{user}:{replacement}"
    else:
        redacted_userinfo = replacement
    new_netloc = f"{redacted_userinfo}@{host}"
    return urlunsplit(
    (parts.scheme,
    new_netloc,
    parts.path,
    parts.query,
     parts.fragment))


__all__ = [
    "ParsedURI",
    "build_network_uri",
    "is_loopback_host",
    "is_public_ip",
    "parse_network_uri",
    "sanitize_uri",
    "tcp_reachable",
]
