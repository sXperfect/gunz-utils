"""Public namespace contract for reusable runtime modules."""

from __future__ import annotations

import gunz_utils
import gunz_utils.content_store as content_store
import gunz_utils.dag as dag
import gunz_utils.experiments as experiments
import gunz_utils.faults as faults
import gunz_utils.hashing as hashing
import gunz_utils.instrumentation as instrumentation
import gunz_utils.leases as leases
import gunz_utils.network as network
import gunz_utils.partitions as partitions
import gunz_utils.provenance as provenance
import gunz_utils.provenance_graph as provenance_graph
import gunz_utils.sampling as sampling
import gunz_utils.security as security
import gunz_utils.signals as signals
import gunz_utils.stats as stats
import gunz_utils.structures as structures
import gunz_utils.sync as sync


def test_reusable_runtime_module_exports_resolve_and_are_unique() -> None:
    modules = (
        content_store,
        dag,
        experiments,
        faults,
        hashing,
        instrumentation,
        leases,
        network,
        partitions,
        provenance,
        provenance_graph,
        sampling,
        security,
        signals,
        stats,
        structures,
        sync,
    )

    for module in modules:
        exports = module.__all__
        assert len(exports) == len(set(exports)), module.__name__
        missing = [
            name
            for name in exports
            if not hasattr(module, name)
        ]
        assert missing == [], module.__name__



def test_new_runtime_apis_remain_namespace_first() -> None:
    names = {
        "BootstrapMeanCI",
        "ContentAddressedStore",
        "ExecutionManifest",
        "NamedFaultInjector",
        "PartitionManifest",
        "ProvenanceGraph",
        "SignalRegistration",
        "Trace",
        "VariantResult",
        "WorkflowDAG",
        "build_network_uri",
        "rsync_mirror",
        "stable_priority",
    }

    assert names.isdisjoint(gunz_utils.__all__)
