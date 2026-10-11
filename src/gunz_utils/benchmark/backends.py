"""Cross-platform process-sampling backend contracts."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SamplerCapabilities:
    process_tree: bool
    rss: bool
    pss: bool
    private_memory: bool
    cpu_time: bool
    io_bytes: bool
    page_faults: bool
    context_switches: bool


class ProcessSampler(ABC):
    """Platform backend interface for process-resource collection."""

    @property
    @abstractmethod
    def capabilities(self) -> SamplerCapabilities:
        """capabilities() function.

        Returns
        -------
        SamplerCapabilities
            The result of the operation.
        """
        raise NotImplementedError


class LinuxProcSampler(ProcessSampler):
    @property
    def capabilities(self) -> SamplerCapabilities:
        """capabilities() function.

        Returns
        -------
        SamplerCapabilities
            The result of the operation.
        """
        return SamplerCapabilities(True, True, True, True, True, True, True, True)


class PortableSampler(ProcessSampler):
    """Explicit minimal backend for unsupported platforms."""

    @property
    def capabilities(self) -> SamplerCapabilities:
        """capabilities() function.

        Returns
        -------
        SamplerCapabilities
            The result of the operation.
        """
        return SamplerCapabilities(
            False, False, False, False, False, False, False, False
        )


def default_sampler() -> ProcessSampler:
    """Return the best built-in process sampler for the current platform.

    Returns
    -------
    ProcessSampler
        The result of the operation.
    """
    return LinuxProcSampler() if sys.platform.startswith("linux") else PortableSampler()


__all__ = [
    "LinuxProcSampler",
    "PortableSampler",
    "ProcessSampler",
    "SamplerCapabilities",
    "default_sampler",
]
