API Reference
=============

This page documents every public module in ``gunz_utils`` v1.10.0.

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
