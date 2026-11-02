class LLMError(Exception):
    """An LLM failure with an explicit retry policy.

    retryable: whether repeating the same request might succeed.
    retry_after: seconds the provider asked us to wait, if it said.
    """

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after