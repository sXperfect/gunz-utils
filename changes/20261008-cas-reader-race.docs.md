Clarify that verified content-store reads may reject a concurrent pathname
replacement even when the replacement has the same digest. Callers may retry
after cooperating publication settles; returned paths remain snapshots.
