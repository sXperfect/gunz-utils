Drain sibling tasks and close unused coroutines in `gather_with_concurrency` on
failure or cancellation; fix throttling at clock startup and after failed calls;
repair exception suppression during signal, process, lease and benchmark cleanup;
stabilize vector normalization, norms, cosine similarity and dot-product summation;
fix process RSS integration; restore package-wide typing, test isolation and
strict API documentation; repair source layout and lint findings without changing
the core dependency or export boundaries; restore native extension compilation
and make the documented verification entry point executable.
