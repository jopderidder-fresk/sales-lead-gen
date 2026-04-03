import enum


class CompanyStatus(enum.StrEnum):
    DISCOVERED = "discovered"
    ENRICHED = "enriched"
    MONITORING = "monitoring"
    QUALIFIED = "qualified"
    PUSHED = "pushed"
    ARCHIVED = "archived"


class EmailStatus(enum.StrEnum):
    VERIFIED = "verified"
    CATCH_ALL = "catch-all"
    UNVERIFIED = "unverified"


class SignalType(enum.StrEnum):
    HIRING_SURGE = "hiring_surge"
    TECHNOLOGY_ADOPTION = "technology_adoption"
    DIGITAL_TRANSFORMATION = "digital_transformation"
    WORKFORCE_CHALLENGE = "workforce_challenge"
    FUNDING_ROUND = "funding_round"
    LEADERSHIP_CHANGE = "leadership_change"
    EXPANSION = "expansion"
    PARTNERSHIP = "partnership"
    PRODUCT_LAUNCH = "product_launch"
    OTHER = "other"
    NO_SIGNAL = "no_signal"


class SignalAction(enum.StrEnum):
    NOTIFY_IMMEDIATE = "notify_immediate"
    NOTIFY_DIGEST = "notify_digest"
    ENRICH_FURTHER = "enrich_further"
    IGNORE = "ignore"


class ScrapeJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class DiscoveryJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EnrichmentJobStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditLogTarget(enum.StrEnum):
    CLICKUP = "clickup"
    CRM = "crm"
    SLACK = "slack"
    ENRICHMENT = "enrichment"


class AuditLogStatus(enum.StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
