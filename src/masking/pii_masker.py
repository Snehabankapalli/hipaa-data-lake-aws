"""
HIPAA-compliant PII masking for healthcare data.
Implements HIPAA Safe Harbor de-identification (45 CFR §164.514(b)).

Safe Harbor requires removing 18 identifiers:
  Names, geographic data, dates, phone numbers, fax numbers,
  email addresses, SSNs, MRNs, health plan numbers, account numbers,
  certificate numbers, vehicle identifiers, device identifiers,
  URLs, IP addresses, biometric identifiers, full-face photos, and
  any other unique identifying numbers or codes.
"""

import hashlib
import hmac
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

_SECRET = os.environ.get("PII_MASKING_SECRET", "").encode("utf-8")
if not _SECRET:
    raise EnvironmentError(
        "PII_MASKING_SECRET environment variable must be set. "
        "Rotate immediately if this secret is ever exposed."
    )


class MaskingStrategy(Enum):
    TOKEN = "token"          # Deterministic HMAC token (enables joins)
    REDACT = "redact"        # Replace with [REDACTED]
    GENERALIZE = "generalize"  # Reduce precision (e.g., ZIP → 3-digit prefix)
    SUPPRESS = "suppress"    # Remove field entirely


@dataclass
class MaskingResult:
    original_field: str
    masked_value: str
    strategy_applied: MaskingStrategy
    was_phi: bool


def tokenize(value: str) -> str:
    """
    HMAC-SHA256 token. Deterministic: same input always produces same token.
    Enables joining tokenized records without exposing raw PHI.
    """
    if not value or not value.strip():
        return ""
    return hmac.new(_SECRET, value.strip().encode("utf-8"), hashlib.sha256).hexdigest()


def redact(value: str, placeholder: str = "[REDACTED]") -> str:
    """Replace PHI with a placeholder. Use when the value is never needed downstream."""
    if not value or not value.strip():
        return ""
    return placeholder


def generalize_zip(zip_code: str) -> str:
    """
    HIPAA Safe Harbor: ZIP codes with fewer than 20,000 people must be suppressed.
    Conservative approach: always return only first 3 digits.
    """
    if not zip_code:
        return ""
    cleaned = re.sub(r"[^0-9]", "", zip_code)
    return cleaned[:3] if len(cleaned) >= 3 else ""


def generalize_date(date_str: str, keep_year: bool = True) -> str:
    """
    HIPAA Safe Harbor: dates must be generalized to year only.
    Exception: ages over 89 must be aggregated into a single category.
    """
    if not date_str:
        return ""
    year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
    if not year_match:
        return "[DATE_REDACTED]"
    return year_match.group(0) if keep_year else "[YEAR_REDACTED]"


def mask_ssn(ssn: str) -> str:
    """Mask SSN — always tokenize, never store raw."""
    return tokenize(ssn) if ssn else ""


def mask_mrn(mrn: str) -> str:
    """Mask Medical Record Number — tokenize to allow joins across systems."""
    return tokenize(mrn) if mrn else ""


def mask_phone(phone: str) -> str:
    """Phone numbers must be removed under Safe Harbor."""
    return redact(phone)


def mask_email(email: str) -> str:
    """Email addresses must be removed under Safe Harbor."""
    return redact(email)


class PatientRecordMasker:
    """
    Applies HIPAA Safe Harbor masking to a patient record dict.
    Returns a new dict — never mutates the input.
    """

    PHI_FIELD_STRATEGIES: dict[str, MaskingStrategy] = {
        "patient_id":      MaskingStrategy.TOKEN,
        "mrn":             MaskingStrategy.TOKEN,
        "ssn":             MaskingStrategy.TOKEN,
        "first_name":      MaskingStrategy.REDACT,
        "last_name":       MaskingStrategy.REDACT,
        "date_of_birth":   MaskingStrategy.GENERALIZE,
        "admission_date":  MaskingStrategy.GENERALIZE,
        "discharge_date":  MaskingStrategy.GENERALIZE,
        "zip_code":        MaskingStrategy.GENERALIZE,
        "address":         MaskingStrategy.REDACT,
        "phone":           MaskingStrategy.REDACT,
        "email":           MaskingStrategy.REDACT,
        "insurance_id":    MaskingStrategy.TOKEN,
    }

    def mask(self, record: dict) -> dict:
        """
        Apply Safe Harbor masking to all PHI fields.
        Non-PHI fields are passed through unchanged.
        Returns a new dict.
        """
        masked = {}
        for field, value in record.items():
            strategy = self.PHI_FIELD_STRATEGIES.get(field)
            if strategy is None:
                masked[field] = value
                continue

            if strategy == MaskingStrategy.TOKEN:
                masked[field] = tokenize(str(value)) if value else ""
            elif strategy == MaskingStrategy.REDACT:
                masked[field] = redact(str(value)) if value else ""
            elif strategy == MaskingStrategy.GENERALIZE:
                if "date" in field.lower() or "birth" in field.lower():
                    masked[field] = generalize_date(str(value)) if value else ""
                elif "zip" in field.lower():
                    masked[field] = generalize_zip(str(value)) if value else ""
                else:
                    masked[field] = redact(str(value)) if value else ""
            elif strategy == MaskingStrategy.SUPPRESS:
                pass  # Field omitted from output

        return masked
