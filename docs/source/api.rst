API Reference
=============

This page documents the public modules in the currently installed ``gunz_utils`` release.

.. contents::
   :local:
   :depth: 2


Core utilities (stdlib-only)
----------------------------

These modules have no third-party runtime dependencies.

.. automodule:: gunz_utils.dict_utils
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.enums
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.formatting
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.hashing
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.io
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.iteration
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.limits
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.plugins
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.provenance
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.retry
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.streaming
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.versioning
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: gunz_utils.sampling
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.experiments
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.structures
   :no-index:
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.instrumentation
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.content_store
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.signals
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.network
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.stats
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.partitions
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.dag
   :members:
   :undoc-members:
   :show-inheritance:


.. automodule:: gunz_utils.provenance_graph
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.sync
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.models
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.parsing
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.redaction
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.security
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.timing
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.upstream_protocol
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.project
   :members:
   :undoc-members:
   :show-inheritance:



Additional stable subsystem namespaces
--------------------------------------

The package follows a namespace-first public API policy. These top-level
modules expose stable subsystem contracts without bulk-exporting every symbol
from :mod:`gunz_utils`.

.. automodule:: gunz_utils.async_utils
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.binary
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.buffers
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.cache
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.collections
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.concurrency
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.config
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.context
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.deprecation
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.diagnostics
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.env
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.faults
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.fs
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.identifiers
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.pipeline
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.rate_limit
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.resilience
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.resources
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.result
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.serialization
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.subprocess
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.testing
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.testkit
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.time_utils
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.typed_config
   :members:
   :undoc-members:
   :show-inheritance:


Benchmarking namespace
----------------------

The benchmark package exposes its supported API through
:mod:`gunz_utils.benchmark`.

.. automodule:: gunz_utils.benchmark
   :members:
   :imported-members:
   :undoc-members:
   :show-inheritance:


Optional backends (``gunz_utils.ext.*``)
----------------------------------------

Each extra (``validation``, ``project``, ``observability``, ``secure``)
pulls in its default backend here. Stdlib fallbacks ship alongside and
let you run with zero third-party deps where supported.

.. automodule:: gunz_utils.ext.validation_pydantic
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.ext.validation_stdlib
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.ext.project_gitpython
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.ext.project_stdlib
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.ext.observability_loguru
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.ext.secure_crypto
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.ext.secure_store
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: gunz_utils.leases
   :members:
   :undoc-members:
   :show-inheritance:
