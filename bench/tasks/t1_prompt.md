Write a Python module `lru_ttl.py` containing class `LRUTTL(capacity: int, ttl: float)` with methods
`get(key)` -> value or None, `put(key, value)`, `__len__`. Semantics: least-recently-used eviction when over capacity;
entries expire `ttl` seconds after their last `put` (not after get). Expired entries must not count in `__len__`
and `get` on them returns None. Use `time.monotonic()` and accept an optional `clock` callable in the constructor for testing.
Output ONLY the python code in a single ```python block, no explanation.
