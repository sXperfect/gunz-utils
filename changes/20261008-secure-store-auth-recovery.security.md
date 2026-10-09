SecureStore now authenticates the current store policy when guarding reads and
mutations, rejects missing key material for previously initialized stores, and
can recover a verified pending rotation past a malformed primary key without
ignoring unsafe-file errors.
