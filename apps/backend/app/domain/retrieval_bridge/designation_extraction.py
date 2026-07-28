"""
Deterministic extraction of **equipment designations** from a request's
own text, and their resolution against the existing canonical
vocabulary.

This is lexical recognition by a fixed, documented token shape - **not**
natural-language understanding. It answers "which tokens in this request
are shaped like an equipment designation?", never "what is this request
about?". There is no grammar, no part-of-speech analysis, no embedding,
no model, and no scoring: a token either has the documented shape or it
does not.

Why this module tokenizes the request itself rather than reusing
Engineering Request Classification's ``normalize_and_tokenize``: that
normalizer treats ``-`` as a token separator (correctly, for its own
purpose - it must match "dell'impianto" as two whole tokens). Applied
here it would split "C-295" into "c" and "295" and destroy the very
identifiers this module exists to find. The two tokenizations serve
genuinely different purposes, and this one is deliberately narrow.

Resolution reuses Canonicalization's own public
``normalize_entity_reference`` rather than restating its vocabulary. A
designation it does not recognize is **never guessed into a canonical
identifier** - it is carried forward verbatim as a lexical term, which
is an honest "this system does not know which graph entity this names".
"""

from __future__ import annotations

from app.domain.canonicalization.canonicalization_exceptions import (
    CanonicalizationError,
)
from app.domain.canonicalization.canonicalization_normalizer import (
    normalize_entity_reference,
)
from app.domain.retrieval_bridge.retrieval_bridge_models import (
    DesignationResolution,
    RequestDesignation,
)

# Characters stripped from a token's edges before it is examined, so
# "T2?" and "(C-295)" yield "T2" and "C-295". Deliberately edge-only:
# stripping them from the interior would split the designations this
# module exists to preserve.
_EDGE_CHARACTERS = ".,;:!?()[]{}<>\"'`|/\\@#$%^&*+=~“”‘’«»¿¡"


def _has_letter(token: str) -> bool:
    return any(character.isascii() and character.isalpha() for character in token)


def _has_digit(token: str) -> bool:
    return any(character.isascii() and character.isdigit() for character in token)


def is_designation_shaped(token: str) -> bool:
    """
    The whole shape policy, in one place: a designation contains **at
    least one ASCII letter and at least one ASCII digit**.

    That admits "T2", "87T", "Q52", "C-295", "TR2" - how substation
    equipment is actually labelled - and deliberately excludes:

    - bare words ("trasformatore", "montante", "TA"), because a type name
      is not an instance designation; treating one as a search term would
      broaden retrieval to every transformer in the project when the
      engineer asked about one;
    - bare numbers ("295", "400"), because nothing distinguishes an
      equipment number from a voltage, a page, or a quantity.

    Both exclusions are conservative on purpose: this milestone's rule is
    that insufficient evidence is reported, never compensated for.
    """

    return _has_letter(token) and _has_digit(token)


def _clean(token: str) -> str:
    return token.strip(_EDGE_CHARACTERS)


def _resolve(text: str, token_index: int) -> RequestDesignation:
    """Resolution is a single attempt against Canonicalization's public
    normalizer. Its typed refusals are expected outcomes here, not
    errors: most real designations ("87T", "Q52") are simply not in that
    vocabulary yet."""

    try:
        reference = normalize_entity_reference(text)
    except CanonicalizationError:
        return RequestDesignation(
            text=text,
            token_index=token_index,
            resolution=DesignationResolution.LEXICAL_TERM,
        )

    return RequestDesignation(
        text=text,
        token_index=token_index,
        resolution=DesignationResolution.CANONICAL_REFERENCE,
        entity_type=reference.entity_type,
        canonical_id=reference.canonical_id,
        canonical_reference=(
            f"{reference.entity_type}:{reference.canonical_id}"
        ),
    )


def extract_designations(request_text: str) -> tuple[RequestDesignation, ...]:
    """
    Every designation-shaped token in the request, in the order written,
    deduplicated case-insensitively.

    The **first** spelling of a repeated designation is the one kept, so
    what a reference reports is what the engineer actually typed.
    Deterministic: the same text always yields the same tuple.
    """

    seen: dict[str, RequestDesignation] = {}

    for token_index, raw_token in enumerate(request_text.split()):
        token = _clean(raw_token)

        if not token or not is_designation_shaped(token):
            continue

        seen.setdefault(token.casefold(), _resolve(token, token_index))

    return tuple(seen.values())
