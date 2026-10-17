"""UK e-signature audit. The raw email token is hashed before it is stored."""

import base64
import hashlib
import uuid
from datetime import datetime, timezone

from hr_automata.integrity import DocumentIntegrityEngine

from app.db import connection


def _pdf(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "48 760 Td"]
    for index, line in enumerate(lines[:48]):
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            commands.append("0 -14 Td")
        commands.append(f"({safe}) Tj")
    commands.append("ET")
    stream = ("\n".join(commands) + "\n").encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in chunks))
        chunks.append(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_at = sum(len(part) for part in chunks)
    xref = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    xref.extend(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    xref.append(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n")
    return b"".join(chunks) + "".join(xref).encode()


def execute_signature(
    candidate_id: str,
    signer_email: str,
    email_token: str,
    document_text: str,
    ip_address: str,
    user_agent: str,
) -> dict:
    document = document_text.encode()
    document_sha = DocumentIntegrityEngine.generate_sha256_checksum(document)
    token_sha = hashlib.sha256(email_token.encode()).hexdigest()
    signed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    audit_id = "sig_" + uuid.uuid4().hex[:12]
    certificate = [
        "SEQUEL SUPPORT LTD",
        "Electronic signature certificate",
        "UK eIDAS and UK GDPR",
        f"Audit: {audit_id}",
        f"Candidate: {candidate_id}",
        f"Signer: {signer_email}",
        f"Signed at (UTC): {signed_at}",
        f"IP address: {ip_address}",
        f"User agent: {user_agent[:180]}",
        f"Document SHA-256: {document_sha}",
        f"Email token SHA-256: {token_sha}",
        "The email authentication token is stored only as this hash.",
    ]
    pdf = _pdf(certificate + ["", "Document:", document_text[:800]])
    connection().execute(
        """
        INSERT INTO signature_audits (
          id, candidate_id, signer_email, ip_address, user_agent, signed_at, document_sha256, token_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (audit_id, candidate_id, signer_email, ip_address, user_agent[:300], signed_at, document_sha, token_sha),
    )
    connection().commit()
    return {
        "id": audit_id,
        "candidate_id": candidate_id,
        "signer_email": signer_email,
        "ip_address": ip_address,
        "user_agent": user_agent[:300],
        "signed_at": signed_at,
        "document_sha256": document_sha,
        "token_sha256": token_sha,
        "pdf_base64": base64.b64encode(pdf).decode("ascii"),
    }
