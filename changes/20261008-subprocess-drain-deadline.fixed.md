Apply bounded synchronous command timeouts through output pipe draining and clean
up reader threads when descendants retain pipes after the direct process exits.
Release the child and capture pipes when reader construction or startup fails.
