"""Backward-compat re-export for ``resolve_project_root``.

The canonical implementation lives in :mod:`gunz_utils.ext.project_gitpython`
(the default backend) and is also lazy-loaded from the package root via
:data:`gunz_utils._LAZY`. This module is kept only so that historical imports
of the form ``from gunz_utils.project import resolve_project_root`` continue
to resolve to the same function object.

New code should prefer ``from gunz_utils import resolve_project_root``.
"""

from __future__ import annotations

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "Clear BSD"

# =============================================================================
# RE-EXPORT
# =============================================================================
from .ext.project_gitpython import resolve_project_root

__all__ = ["resolve_project_root"]
