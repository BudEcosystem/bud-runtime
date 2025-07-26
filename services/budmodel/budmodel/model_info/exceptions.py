class HubDownloadException(Exception):
    """Exception raised when there is an error in downloading from the hub."""

    pass


class ModelScanException(Exception):
    """Exception raised when an error occurs during model scanning."""

    pass


class UnsupportedModelException(Exception):
    """Exception raised when an unsupported model is detected."""

    pass


class SpaceNotAvailableException(Exception):
    """Exception raised when the model size bigger than disck space."""

    pass


class RepoAccessException(Exception):
    """Exception raised when the repo cannot be accessed."""

    pass


class SaveRegistryException(Exception):
    """Exception raised when the model cannot be saved to the registry."""

    pass
