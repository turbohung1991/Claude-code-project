class AfterSalesError(Exception):
    """Base exception for after-sales agent."""


class TriageConfidenceTooLow(AfterSalesError):
    """Raised when classification confidence is below threshold."""


class ComplianceViolation(AfterSalesError):
    """Raised when generated content violates compliance rules."""


class KnowledgeNotFound(AfterSalesError):
    """Raised when required knowledge entry is missing."""
