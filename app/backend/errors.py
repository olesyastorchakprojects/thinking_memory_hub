class BackendSettingsError(Exception):
    """Raised when backend settings cannot be loaded."""


class IntentParseError(Exception):
    """Raised when the backend cannot determine one valid intent."""


class BackendProcessingError(Exception):
    """Raised when backend orchestration fails."""


class MemoryServerError(Exception):
    """Raised when the remote memory server call fails."""


class ModelClientError(Exception):
    """Raised when the model client fails to complete a generation request."""


class InputExtractionError(Exception):
    """Raised when structured input extraction fails."""


class SlackRequestError(Exception):
    """Raised when an inbound Slack request is invalid."""


class SlackApiError(Exception):
    """Raised when outbound Slack API calls fail."""
