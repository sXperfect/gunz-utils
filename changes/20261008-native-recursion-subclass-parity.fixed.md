Bound native JSON fast-path recursion independently of interpreter accounting,
delegating deeper inputs to the Python reference so expanded nesting limits and
cyclic objects remain safe on Python 3.11 and 3.12. Preserve Python integer-subclass
arithmetic and comparison semantics in native varint encoding by delegating those
subclasses to the reference implementation.
