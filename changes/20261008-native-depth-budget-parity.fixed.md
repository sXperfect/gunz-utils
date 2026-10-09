Preserve Python reference values and depth errors for normalization budgets outside
the native classifier's C-integer range. Check depth with Python semantics first
and bound only the native optimization budget, retaining the caller's recursive
budget, default depth and existing native stack-safety cutoff.
