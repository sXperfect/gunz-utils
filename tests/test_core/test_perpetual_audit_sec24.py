"""Perpetual security audit phase 24.

Re-audit of the benchmark CLI/IO/report/process/export modules and the package
``__init__`` lazy-import machinery (round 3).

Finding: ``from gunz_utils import *`` force-loads every name advertised in the
package ``__all__``.  The optional, lazily imported names (``GunzBaseModel``,
``type_checked``, ``resolve_project_root``, ``setup_logging``, ``encrypt``,
``decrypt``, ``get_derived_key``, ``get_system_passphrase``, ``SecureStore``,
``SecretMetadata``) are listed in ``__all__``, so a star import attempts to
import each of their backing modules (pydantic, gitpython, loguru,
cryptography, secure store).  When any one optional third-party dependency is
missing, the entire star import raises ``AttributeError`` and aborts, leaking
optional-dependency availability into core import-time behavior.  This
violates the package API policy that optional third-party packages must not
leak into core import-time behavior.
"""

import pytest

import gunz_utils

_OPTIONAL_LAZY_NAMES = (
    "resolve_project_root",
    "setup_logging",
    "encrypt",
    "decrypt",
    "get_derived_key",
    "get_system_passphrase",
    "SecureStore",
    "SecretMetadata",
    "GunzBaseModel",
    "type_checked",
)


def test_star_import_does_not_raise_on_missing_optional_dependency():
    # RED: on a minimal install (e.g. GitPython absent) `from gunz_utils
    # import *` currently raises AttributeError instead of importing cleanly.
    namespace: dict = {}
    exec("from gunz_utils import *", namespace)


def test_star_import_does_not_materialize_optional_lazy_names():
    # RED: optional lazy names must not be pulled into the star-import
    # namespace.  Currently every optional name is force-loaded (or the star
    # import aborts), so at least one is present.
    namespace: dict = {}
    exec("from gunz_utils import *", namespace)
    for name in _OPTIONAL_LAZY_NAMES:
        assert name not in namespace


def test_optional_lazy_names_not_advertised_in_all():
    # RED: optional names cannot be guaranteed importable, so advertising them
    # in __all__ forces a star import to attempt loading them.
    for name in _OPTIONAL_LAZY_NAMES:
        assert name not in gunz_utils.__all__


def test_unknown_attribute_raises_attribute_error():
    # Green sanity: direct access to a genuinely unknown name degrades
    # gracefully via the module __getattr__.
    with pytest.raises(AttributeError):
        _ = gunz_utils.no_such_perpetual_attribute
