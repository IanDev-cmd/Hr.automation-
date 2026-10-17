"""SHA-256 checksums and the Ofsted watermark block."""

import hashlib
from typing import Dict


class DocumentIntegrityEngine:
    """Checksum a file and build the inspection watermark metadata."""

    @staticmethod
    def generate_sha256_checksum(file_bytes: bytes) -> str:
        if not isinstance(file_bytes, (bytes, bytearray)):
            raise TypeError("checksum input must be bytes")
        return hashlib.sha256(file_bytes).hexdigest()

    @staticmethod
    def build_watermark_metadata(
        candidate_id: str, manager_name: str, signoff_timestamp: str
    ) -> Dict[str, str]:
        return {
            "watermark_text": f"OFSTED VERIFIED - SEQUEL SUPPORT - CANDIDATE {candidate_id}",
            "verified_by": manager_name,
            "verification_date": signoff_timestamp,
            "legal_status": "COMPLIANT_UNDER_CHILDRENS_HOMES_REGS_2015",
        }
