Apply asynchronous bounded-capture timeouts to process exit and pipe draining.
On timeout, cancellation, overflow or reader failure, cancel and join owned
capture tasks, close capture read ends, and reap the child without waiting for
foreign pipe writers. Preserve shared output limits and repeated cancellation
cleanup, including timeout/cancellation for unlimited capture.
