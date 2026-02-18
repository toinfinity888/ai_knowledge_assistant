"""
PII Detector Service

Detects Personally Identifiable Information (PII) in text for GDPR compliance.
Uses regex patterns to identify common PII types in support conversations.
"""
import re
from typing import List, Dict, Set
from dataclasses import dataclass


@dataclass
class PIIMatch:
    """Represents a detected PII item."""
    pii_type: str
    value: str
    start: int
    end: int


class PIIDetector:
    """
    Detects PII in text using regex patterns.

    Supported PII types:
    - IP addresses (IPv4)
    - MAC addresses
    - Email addresses
    - Phone numbers (international format)
    - Serial numbers (common formats)
    - Credit card numbers (basic detection)
    """

    # Regex patterns for different PII types
    PATTERNS: Dict[str, str] = {
        "ip_address": r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
        "mac_address": r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b',
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone_number": r'\b(?:\+?[1-9]\d{0,2}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b',
        "serial_number": r'\b[A-Z]{2,4}[-]?\d{6,12}\b',
        "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    }

    # Human-readable names for PII types
    TYPE_NAMES: Dict[str, str] = {
        "ip_address": "IP Address",
        "mac_address": "MAC Address",
        "email": "Email Address",
        "phone_number": "Phone Number",
        "serial_number": "Serial Number",
        "credit_card": "Credit Card",
    }

    def __init__(self, enabled_types: List[str] = None):
        """
        Initialize the PII detector.

        Args:
            enabled_types: List of PII types to detect. If None, all types are enabled.
        """
        self.enabled_types = enabled_types or list(self.PATTERNS.keys())

        # Compile regex patterns for efficiency
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        for pii_type in self.enabled_types:
            if pii_type in self.PATTERNS:
                self._compiled_patterns[pii_type] = re.compile(
                    self.PATTERNS[pii_type],
                    re.IGNORECASE if pii_type != "serial_number" else 0
                )

    def detect(self, text: str) -> List[str]:
        """
        Detect PII types present in the text.

        Args:
            text: The text to scan for PII

        Returns:
            List of PII type names found (e.g., ["IP Address", "Email Address"])
        """
        if not text:
            return []

        found_types: Set[str] = set()

        for pii_type, pattern in self._compiled_patterns.items():
            if pattern.search(text):
                found_types.add(self.TYPE_NAMES.get(pii_type, pii_type))

        return sorted(list(found_types))

    def detect_detailed(self, text: str) -> List[PIIMatch]:
        """
        Detect PII with detailed match information.

        Args:
            text: The text to scan for PII

        Returns:
            List of PIIMatch objects with type, value, and position
        """
        if not text:
            return []

        matches: List[PIIMatch] = []

        for pii_type, pattern in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                matches.append(PIIMatch(
                    pii_type=self.TYPE_NAMES.get(pii_type, pii_type),
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                ))

        # Sort by position in text
        matches.sort(key=lambda m: m.start)
        return matches

    def mask_pii(self, text: str, mask_char: str = '*') -> str:
        """
        Mask detected PII in the text.

        Args:
            text: The text containing PII
            mask_char: Character to use for masking

        Returns:
            Text with PII values masked
        """
        if not text:
            return text

        result = text

        # Get all matches sorted by position (reverse order to preserve indices)
        matches = self.detect_detailed(text)
        matches.sort(key=lambda m: m.start, reverse=True)

        for match in matches:
            # Mask the value, keeping first and last chars for context
            value = match.value
            if len(value) > 4:
                masked = value[0] + (mask_char * (len(value) - 2)) + value[-1]
            else:
                masked = mask_char * len(value)

            result = result[:match.start] + masked + result[match.end:]

        return result


# Singleton instance for easy access
_pii_detector: PIIDetector = None


def get_pii_detector() -> PIIDetector:
    """Get the singleton PII detector instance."""
    global _pii_detector
    if _pii_detector is None:
        _pii_detector = PIIDetector()
    return _pii_detector
