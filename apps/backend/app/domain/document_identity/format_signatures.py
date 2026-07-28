"""
The fixed, documented format evidence tables (Milestone 25.2) - the
**one authoritative rule source** for what a document's format is.

Upload and ingestion both classify through ``format_classifier.py``,
which reads only these tables. There is deliberately no second copy of a
format rule anywhere: an architecture test asserts that nothing outside
this module declares a signature, a MIME map or an extension map.

Every entry is a literal byte prefix or an exact string. There is no
regex, no heuristic, no scoring and no "looks like" - a signature either
matches at offset zero or it does not.
"""

from __future__ import annotations

from app.domain.document_identity.document_format import ClassifiedFormat

# How many leading bytes the classifier needs. The longest signature below
# is 18 bytes ("AutoCAD Binary DXF"); 32 leaves room without ever reading
# a meaningful amount of a document.
SIGNATURE_PREFIX_LENGTH = 32

# The ZIP local-file header. OOXML formats (xlsx, docx) are both ZIP
# containers, so this prefix identifies the *container* and not the
# document format - see ``AMBIGUOUS_SIGNATURES``.
_ZIP_HEADER = b"PK\x03\x04"

# Byte prefixes that identify exactly one format. Longest-first matching
# is applied by the classifier so a longer, more specific prefix always
# wins over a shorter one.
CONTENT_SIGNATURES: tuple[tuple[bytes, ClassifiedFormat], ...] = (
    (b"%PDF-", ClassifiedFormat.PDF),
    # DWG stores its version in the first six bytes: AC1015 (2000),
    # AC1018 (2004), AC1021 (2007), AC1024 (2010), AC1027 (2013),
    # AC1032 (2018). The shared "AC10" prefix covers every version this
    # system is likely to meet without enumerating future ones.
    (b"AC10", ClassifiedFormat.DWG),
    # Binary DXF announces itself explicitly.
    (b"AutoCAD Binary DXF", ClassifiedFormat.DXF),
    # ASCII DXF opens with a group code 0 followed by SECTION. Both
    # line-ending conventions occur in the field.
    (b"  0\r\nSECTION", ClassifiedFormat.DXF),
    (b"  0\nSECTION", ClassifiedFormat.DXF),
    (b"0\r\nSECTION", ClassifiedFormat.DXF),
    (b"0\nSECTION", ClassifiedFormat.DXF),
    (b"\x89PNG\r\n\x1a\n", ClassifiedFormat.IMAGE),
    (b"\xff\xd8\xff", ClassifiedFormat.IMAGE),
    (b"GIF87a", ClassifiedFormat.IMAGE),
    (b"GIF89a", ClassifiedFormat.IMAGE),
    (b"BM", ClassifiedFormat.IMAGE),
    # TIFF, little- and big-endian.
    (b"II*\x00", ClassifiedFormat.IMAGE),
    (b"MM\x00*", ClassifiedFormat.IMAGE),
)

# Byte prefixes that identify a *container* several formats share. The
# signature has no opinion about which - and saying so is the honest
# answer, because guessing between xlsx and docx from a ZIP header would
# be exactly the arbitrary classification this milestone forbids. The
# weaker sources decide, and the evidence records why the signature
# abstained.
AMBIGUOUS_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (
        _ZIP_HEADER,
        "ZIP container - shared by xlsx and docx; the signature alone "
        "cannot distinguish them",
    ),
)

# Exact MIME types, as an uploading client declares them. Only types this
# system has a format for; anything else yields no opinion rather than a
# guess.
MIME_TYPES: dict[str, ClassifiedFormat] = {
    "application/pdf": ClassifiedFormat.PDF,
    "image/vnd.dwg": ClassifiedFormat.DWG,
    "application/acad": ClassifiedFormat.DWG,
    "image/vnd.dxf": ClassifiedFormat.DXF,
    "application/dxf": ClassifiedFormat.DXF,
    (
        "application/vnd.openxmlformats-officedocument"
        ".spreadsheetml.sheet"
    ): ClassifiedFormat.XLSX,
    (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ): ClassifiedFormat.DOCX,
    "image/png": ClassifiedFormat.IMAGE,
    "image/jpeg": ClassifiedFormat.IMAGE,
    "image/gif": ClassifiedFormat.IMAGE,
    "image/bmp": ClassifiedFormat.IMAGE,
    "image/tiff": ClassifiedFormat.IMAGE,
    "model/step": ClassifiedFormat.MODEL_3D,
    "model/iges": ClassifiedFormat.MODEL_3D,
}

# Lower-case extensions including the leading dot.
FILENAME_EXTENSIONS: dict[str, ClassifiedFormat] = {
    ".pdf": ClassifiedFormat.PDF,
    ".dwg": ClassifiedFormat.DWG,
    ".dxf": ClassifiedFormat.DXF,
    ".xlsx": ClassifiedFormat.XLSX,
    ".xlsm": ClassifiedFormat.XLSX,
    ".docx": ClassifiedFormat.DOCX,
    ".png": ClassifiedFormat.IMAGE,
    ".jpg": ClassifiedFormat.IMAGE,
    ".jpeg": ClassifiedFormat.IMAGE,
    ".gif": ClassifiedFormat.IMAGE,
    ".bmp": ClassifiedFormat.IMAGE,
    ".tif": ClassifiedFormat.IMAGE,
    ".tiff": ClassifiedFormat.IMAGE,
    ".step": ClassifiedFormat.MODEL_3D,
    ".stp": ClassifiedFormat.MODEL_3D,
    ".iges": ClassifiedFormat.MODEL_3D,
    ".igs": ClassifiedFormat.MODEL_3D,
}
