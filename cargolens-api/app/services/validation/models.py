from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import uuid

from app.models.validation import ValidationOutcome, ValidationSeverity


@dataclass
class ValidationRuleResult:
    """Represents the evaluation result of a single validation rule."""
    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    outcome: ValidationOutcome
    explanation: str
    compared_values: Dict[str, Any] = field(default_factory=dict)
    source_document_ids: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "outcome": self.outcome.value,
            "explanation": self.explanation,
            "compared_values": self.compared_values,
            "source_document_ids": self.source_document_ids,
            "timestamp": self.timestamp.isoformat(),
        }
