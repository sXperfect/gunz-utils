Anchor content-store fanout operations to directory descriptors on supported
POSIX platforms, verify and copy from opened regular-file handles, and retain
materialization staging files until publication. Reject non-ASCII hexadecimal
digest spellings. Platforms without descriptor-relative no-follow operations
require trusted directory trees; same-digest hard-link fallback preserves content
rather than the inode of a competing publisher.
