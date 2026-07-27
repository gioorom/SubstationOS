"""
The fixed, versioned rule table for Engineering Request Classification
(Milestone 22) - explicit immutable data, never a large if/elif
function. Every rule is independently evaluable (``evaluate_rule``) and
independently testable.

Both Italian and English request signals are supported throughout,
matching how this project's own domain vocabulary is actually written
(CLAUDE.md SS8 already establishes that real-world aliases may include
Italian).

Rule strength:
- ``STRONG``  - a specific workflow verb or phrase that alone identifies
  a workflow ("confronta", "verifica", "disegna", "apri", "spiega").
- ``WEAK``    - a supporting signal not decisive alone (a bare
  interrogative like "quale", a bare noun like "documento").
- ``DOMAIN``  - establishes only that the request is engineering-related
  at all (feeds ``GENERAL_ENGINEERING_REQUEST``, never a specific
  workflow).

Matching is **whole-token** (or whole contiguous token runs, for
phrases), never substring - see
``engineering_intent_normalization.py``'s own note on why.
"""

from __future__ import annotations

from app.domain.engineering_intent.engineering_intent_models import (
    EngineeringIntentEvidenceType,
    EngineeringIntentRule,
    EngineeringIntentRuleMatch,
    EngineeringIntentRuleStrength,
    EngineeringIntentType,
)

_STRONG = EngineeringIntentRuleStrength.STRONG
_WEAK = EngineeringIntentRuleStrength.WEAK
_DOMAIN = EngineeringIntentRuleStrength.DOMAIN


def _rule(
    rule_id: str,
    intent_type: EngineeringIntentType,
    strength: EngineeringIntentRuleStrength,
    *,
    tokens: tuple[str, ...] = (),
    phrases: tuple[str, ...] = (),
) -> EngineeringIntentRule:
    """Phrases are authored as plain strings here for readability and
    split into token tuples once, at table-construction time, so
    matching never re-splits at evaluation time."""

    return EngineeringIntentRule(
        rule_id=rule_id,
        candidate_intent_type=intent_type,
        strength=strength,
        tokens=tokens,
        phrases=tuple(tuple(phrase.split()) for phrase in phrases),
    )


CLASSIFICATION_RULES: tuple[EngineeringIntentRule, ...] = (
    # --- DRAWING_REQUEST (highest precedence) -------------------------
    _rule(
        "drawing.verb",
        EngineeringIntentType.DRAWING_REQUEST,
        _STRONG,
        tokens=("disegna", "disegnami", "draw"),
        phrases=(
            "genera schema",
            "generare schema",
            "crea schema",
            "creare schema",
            "modifica disegno",
            "modifica lo schema",
            "modificare lo schema",
            "produce drawing",
            "generate drawing",
            "create drawing",
            "create schematic",
            "generate schematic",
        ),
    ),
    # --- VERIFICATION_REQUEST ----------------------------------------
    _rule(
        "verification.verb",
        EngineeringIntentType.VERIFICATION_REQUEST,
        _STRONG,
        tokens=(
            "verifica",
            "verificalo",
            "verificare",
            "controlla",
            "controllare",
            "valida",
            "validare",
            "check",
            "verify",
            "validate",
        ),
    ),
    _rule(
        "verification.condition",
        EngineeringIntentType.VERIFICATION_REQUEST,
        _WEAK,
        tokens=(
            "conforme",
            "conformi",
            "incoerenza",
            "incoerenze",
            "coerenti",
            "coerente",
            "errore",
            "errori",
            "compliant",
            "inconsistency",
            "inconsistencies",
        ),
    ),
    # --- ENGINEERING_COMPARISON --------------------------------------
    _rule(
        "comparison.verb",
        EngineeringIntentType.ENGINEERING_COMPARISON,
        _STRONG,
        tokens=(
            "confronta",
            "confrontare",
            "confronto",
            "compare",
            "compara",
        ),
    ),
    _rule(
        "comparison.marker",
        EngineeringIntentType.ENGINEERING_COMPARISON,
        _WEAK,
        tokens=(
            "differenze",
            "differenza",
            "versus",
            "vs",
            "differences",
            "difference",
        ),
    ),
    # --- NAVIGATION_REQUEST -------------------------------------------
    _rule(
        "navigation.verb",
        EngineeringIntentType.NAVIGATION_REQUEST,
        _STRONG,
        tokens=("apri", "aprire", "open"),
        phrases=(
            "vai a",
            "vai alla",
            "vai al",
            "portami a",
            "portami alla",
            "portami al",
            "mostra pagina",
            "mostra la pagina",
            "go to",
            "navigate to",
            "show page",
            "show the page",
        ),
    ),
    # --- DOCUMENT_LOOKUP ----------------------------------------------
    _rule(
        "document.find",
        EngineeringIntentType.DOCUMENT_LOOKUP,
        _STRONG,
        tokens=("trova", "trovare", "find", "locate"),
        phrases=(
            "mostrami i documenti",
            "mostrami il documento",
            "elenca i documenti",
            "where is",
            "find document",
            "find documents",
            "list documents",
        ),
    ),
    _rule(
        "document.noun",
        EngineeringIntentType.DOCUMENT_LOOKUP,
        _WEAK,
        tokens=(
            "documento",
            "documenti",
            "file",
            "pdf",
            "tavola",
            "tavole",
            "disegno",
            "disegni",
            "drawing",
            "drawings",
            "pagina",
            "pagine",
            "riferimento",
            "riferimenti",
            "document",
            "documents",
            "page",
            "reference",
            "references",
        ),
    ),
    # --- ENGINEERING_EXPLANATION --------------------------------------
    _rule(
        "explanation.verb",
        EngineeringIntentType.ENGINEERING_EXPLANATION,
        _STRONG,
        tokens=(
            "spiega",
            "spiegami",
            "spiegare",
            "descrivi",
            "descrivimi",
            "descrivere",
            "riassumi",
            "riassumimi",
            "interpreta",
            "explain",
            "describe",
            "summarize",
            "summarise",
            "interpret",
        ),
    ),
    # --- KNOWLEDGE_QUERY -----------------------------------------------
    _rule(
        "knowledge.interrogative",
        EngineeringIntentType.KNOWLEDGE_QUERY,
        _WEAK,
        tokens=(
            "quale",
            "quali",
            "quanto",
            "quanti",
            "quanta",
            "quante",
            "what",
            "which",
            "how",
        ),
    ),
    _rule(
        "knowledge.state",
        EngineeringIntentType.KNOWLEDGE_QUERY,
        _WEAK,
        tokens=(
            "valore",
            "valori",
            "installato",
            "installata",
            "installati",
            "installate",
            "presente",
            "presenti",
            "configurazione",
            "configurazioni",
            "relazione",
            "relazioni",
            "value",
            "values",
            "installed",
            "present",
            "configuration",
            "relationship",
            "relationships",
        ),
    ),
    # --- Engineering domain vocabulary --------------------------------
    # Establishes only that a request is engineering-related at all -
    # feeding GENERAL_ENGINEERING_REQUEST, never a specific workflow.
    # Deliberately limited to SubstationOS's own current domain
    # (CLAUDE.md SS1): primary substations, HV/MV, transformers,
    # switchgear, protection, measurement, cables, equipment, bays
    # (montanti), drawings/schematics, and project documentation.
    _rule(
        "domain.vocabulary",
        EngineeringIntentType.GENERAL_ENGINEERING_REQUEST,
        _DOMAIN,
        tokens=(
            # Substation / plant
            "sottostazione",
            "sottostazioni",
            "cabina",
            "cabine",
            "impianto",
            "impianti",
            "substation",
            "substations",
            "switchyard",
            # Voltage levels
            "at",
            "mt",
            "bt",
            "hv",
            "mv",
            "lv",
            "tensione",
            "voltage",
            # Equipment
            "trasformatore",
            "trasformatori",
            "transformer",
            "transformers",
            "interruttore",
            "interruttori",
            "breaker",
            "breakers",
            "sezionatore",
            "sezionatori",
            "disconnector",
            "disconnectors",
            "quadro",
            "quadri",
            "switchgear",
            "sbarra",
            "sbarre",
            "busbar",
            "busbars",
            "cavo",
            "cavi",
            "cable",
            "cables",
            "apparecchiatura",
            "apparecchiature",
            "equipment",
            # Protection and measurement
            "protezione",
            "protezioni",
            "protection",
            "protections",
            "rele",
            "relay",
            "relays",
            "ta",
            "tv",
            "ct",
            "vt",
            "misura",
            "misure",
            "measurement",
            "measurements",
            # Bays
            "montante",
            "montanti",
            "stallo",
            "stalli",
            "bay",
            "bays",
            "feeder",
            "feeders",
            # Drawings and schematics
            "schema",
            "schemi",
            "schematic",
            "schematics",
            "unifilare",
            "unifilari",
            "funzionale",
            "funzionali",
            # Project documentation
            "progetto",
            "progetti",
            "project",
            "revisione",
            "revisioni",
            "revision",
            "revisions",
            "commessa",
        ),
    ),
)


def evaluate_rule(
    rule: EngineeringIntentRule, tokens: tuple[str, ...]
) -> EngineeringIntentRuleMatch | None:
    """
    Evaluates one rule against one token sequence, returning the
    earliest match (or ``None``). Phrases are checked before single
    tokens so a rule carrying both reports the more specific signal
    when both are present.

    Independently testable in isolation, one rule at a time - the
    milestone's own "rules must be testable independently" requirement.
    """

    earliest: EngineeringIntentRuleMatch | None = None

    for phrase in rule.phrases:
        phrase_length = len(phrase)
        for index in range(len(tokens) - phrase_length + 1):
            if tokens[index : index + phrase_length] == phrase:
                if earliest is None or index < earliest.token_index:
                    earliest = EngineeringIntentRuleMatch(
                        rule_id=rule.rule_id,
                        candidate_intent_type=rule.candidate_intent_type,
                        strength=rule.strength,
                        matched_text=" ".join(phrase),
                        token_index=index,
                        evidence_type=EngineeringIntentEvidenceType.PHRASE_MATCH,
                    )
                break

    if earliest is not None:
        return earliest

    evidence_type = (
        EngineeringIntentEvidenceType.DOMAIN_VOCABULARY_MATCH
        if rule.strength is _DOMAIN
        else EngineeringIntentEvidenceType.TOKEN_MATCH
    )

    for index, token in enumerate(tokens):
        if token in rule.tokens:
            return EngineeringIntentRuleMatch(
                rule_id=rule.rule_id,
                candidate_intent_type=rule.candidate_intent_type,
                strength=rule.strength,
                matched_text=token,
                token_index=index,
                evidence_type=evidence_type,
            )

    return None


def evaluate_all_rules(
    tokens: tuple[str, ...],
    rules: tuple[EngineeringIntentRule, ...] = CLASSIFICATION_RULES,
) -> tuple[EngineeringIntentRuleMatch, ...]:
    """Every rule that fires, ordered deterministically by
    ``(token_index, rule_id)`` - position first, so evidence reads in
    the order the request itself is written, with the rule id breaking
    ties reproducibly."""

    matches = [
        match
        for match in (evaluate_rule(rule, tokens) for rule in rules)
        if match is not None
    ]
    matches.sort(key=lambda match: (match.token_index, match.rule_id))

    return tuple(matches)
