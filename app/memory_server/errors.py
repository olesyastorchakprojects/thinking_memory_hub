class SettingsError(Exception):
    pass


class StorageClientError(Exception):
    pass


class StorageNotFoundError(StorageClientError):
    pass


class StorageConflictError(StorageClientError):
    pass


class ToolInputValidationError(Exception):
    pass
