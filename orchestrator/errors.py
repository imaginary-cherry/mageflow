class OrchestratorError(Exception):
    pass


class MissingSignatureError(OrchestratorError):
    pass


class MissingSwarmItemError(MissingSignatureError):
    pass


class SwarmError(OrchestratorError):
    pass


class TooManyTasksError(SwarmError, RuntimeError):
    pass


class SwarmIsCanceledError(SwarmError, RuntimeError):
    pass
