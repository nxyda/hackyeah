from enum import Enum


class ReportCategory(str, Enum):
    DANGER = "danger"
    HARASSMENT = "harassment"
    POOR_LIGHTING = "poor_lighting"
    BLOCKED_PATH = "blocked_path"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    OTHER = "other"

class ReportStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    EXPIRED = "expired"
    REJECTED = "rejected"