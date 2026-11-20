"""Application errors shared by services and their transport adapters."""


class ALPRDomainException(Exception):
    pass


class EntityNotFoundException(ALPRDomainException):
    pass


class AuthenticationException(ALPRDomainException):
    pass


class PermissionDeniedException(ALPRDomainException):
    pass


class InvalidPayloadException(ALPRDomainException):
    pass


class PayloadTooLargeException(InvalidPayloadException):
    pass


class ResourceConflictException(ALPRDomainException):
    pass


class ServiceUnavailableException(ALPRDomainException):
    pass


class RateLimitExceededException(ALPRDomainException):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after
