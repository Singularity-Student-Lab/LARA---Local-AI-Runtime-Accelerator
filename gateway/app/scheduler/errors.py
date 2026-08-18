class QueueFullError(Exception):
    """Queue depth at LARA_QUEUE_MAX_DEPTH on arrival -> 429, job REJECTED."""


class QueueTimeoutError(Exception):
    """Queue wait exceeded LARA_QUEUE_TIMEOUT_S -> 503, job FAILED (error_class=queue_timeout)."""
