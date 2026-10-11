Close rejected coroutine submissions in bounded concurrency helpers, SingleFlight
and async TTL caches. Preserve cooperative child cleanup through repeated caller
cancellation, including descriptor release and initiating error/cancellation signals.
