class CodeKeyError(Exception):
    """An expected, user-facing CodeKey failure."""


class ConfigurationError(CodeKeyError):
    pass


class ClipboardError(CodeKeyError):
    pass


class ModelError(CodeKeyError):
    pass


class OutputValidationError(CodeKeyError):
    pass
