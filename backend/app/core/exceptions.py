class QueueConflictError(ValueError):
    """큐 충돌 에러. existing_topic_id 포함."""

    def __init__(self, message: str, existing_topic_id: str):
        super().__init__(message)
        self.existing_topic_id = existing_topic_id
