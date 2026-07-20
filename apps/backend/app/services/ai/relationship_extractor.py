import json
from typing import Any

from app.models.knowledge_graph import RelationType
from app.services.ai.claude_provider import ClaudeProvider
from app.services.ai.models import ExtractedRelationship


RELATIONSHIP_EXTRACTION_SYSTEM_PROMPT = """
Sei un esperto di sottostazioni elettriche, schemi unifilari,
protezioni elettriche e sistemi di automazione.

Il tuo compito è estrarre esclusivamente le relazioni esplicitamente
descritte nel testo tra componenti elettrici.

Restituisci esclusivamente JSON valido, senza testo aggiuntivo.

Formato richiesto:

{
  "relationships": [
    {
      "source": "nome entità sorgente",
      "target": "nome entità destinazione",
      "relation_type": "connected_to",
      "description": "descrizione sintetica della relazione",
      "confidence": 0.95,
      "attributes": {}
    }
  ]
}

Tipi di relazione ammessi:

- connected_to
- feeds
- fed_by
- protected_by
- protects
- measured_by_ct
- measured_by_vt
- controls
- belongs_to
- part_of
- installed_in
- documented_in
- tested_by
- other

Regole:

1. Usa esattamente i nomi presenti nel testo.
2. Non inventare componenti o relazioni.
3. Crea una relazione solo quando è esplicita o tecnicamente
   chiaramente deducibile dal testo.
4. La direzione source-target deve rispettare il significato
   del tipo di relazione.
5. Usa connected_to solo quando non esiste un tipo più specifico.
6. Se non ci sono relazioni, restituisci:
   {"relationships": []}
"""


def build_relationship_extraction_prompt(text: str) -> str:
    return f"""
Analizza il seguente testo tecnico ed estrai le relazioni
tra i componenti elettrici.

TESTO:

{text}
""".strip()


class AIRelationshipExtractor:
    def __init__(self) -> None:
        self.provider = ClaudeProvider()

    def extract(
        self,
        text: str,
    ) -> list[ExtractedRelationship]:
        if not text or not text.strip():
            return []

        response = self.provider.generate(
            system_prompt=RELATIONSHIP_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=build_relationship_extraction_prompt(text),
            temperature=0.0,
        )

        data = self._parse_response(response.content)

        relationships: list[ExtractedRelationship] = []
        seen: set[tuple[str, RelationType, str]] = set()

        for item in data:
            source_value = item.get("source")
            target_value = item.get("target")
            relation_type_value = item.get("relation_type")

            if not isinstance(source_value, str):
                continue

            if not isinstance(target_value, str):
                continue

            if not isinstance(relation_type_value, str):
                continue

            source = " ".join(source_value.strip().split())
            target = " ".join(target_value.strip().split())

            if not source or not target:
                continue

            if source.casefold() == target.casefold():
                continue

            try:
                relation_type = RelationType(relation_type_value)
            except ValueError:
                continue

            key = (
                source.casefold(),
                relation_type,
                target.casefold(),
            )

            if key in seen:
                continue

            seen.add(key)

            description_value = item.get("description")
            description = (
                description_value.strip()
                if isinstance(description_value, str)
                and description_value.strip()
                else None
            )

            confidence_value = item.get("confidence", 1.0)

            try:
                confidence = float(confidence_value)
            except (TypeError, ValueError):
                confidence = 1.0

            confidence = max(
                0.0,
                min(1.0, confidence),
            )

            attributes_value = item.get("attributes", {})

            attributes = (
                dict(attributes_value)
                if isinstance(attributes_value, dict)
                else {}
            )

            relationships.append(
                ExtractedRelationship(
                    source=source,
                    target=target,
                    relation_type=relation_type,
                    confidence=confidence,
                    description=description,
                    attributes=attributes,
                )
            )

        return relationships

    @staticmethod
    def _parse_response(
        content: str,
    ) -> list[dict[str, Any]]:
        cleaned_content = content.strip()

        if cleaned_content.startswith("```"):
            lines = cleaned_content.splitlines()

            if lines and lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned_content = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned_content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Claude non ha restituito un JSON valido "
                "durante l'estrazione delle relazioni.\n\n"
                f"Risposta ricevuta:\n{content}"
            ) from exc

        if isinstance(parsed, dict):
            parsed = parsed.get("relationships", [])

        if not isinstance(parsed, list):
            raise RuntimeError(
                "Claude deve restituire una lista di relazioni "
                "oppure un oggetto con la proprietà 'relationships'."
            )

        return [
            item
            for item in parsed
            if isinstance(item, dict)
        ]


_relationship_extractor: AIRelationshipExtractor | None = None


def _get_relationship_extractor() -> AIRelationshipExtractor:
    global _relationship_extractor

    if _relationship_extractor is None:
        _relationship_extractor = AIRelationshipExtractor()

    return _relationship_extractor


def extract_relationships(
    text: str,
) -> list[ExtractedRelationship]:
    relationships = _get_relationship_extractor().extract(text)

    print("\n===== DEBUG RELAZIONI CLAUDE =====")

    for relationship in relationships:
        print("-" * 60)
        print(f"Sorgente   : {relationship.source}")
        print(f"Relazione  : {relationship.relation_type}")
        print(f"Destinazione: {relationship.target}")
        print(f"Descrizione: {relationship.description}")
        print(f"Confidence : {relationship.confidence}")
        print(f"Attributi  : {relationship.attributes}")

    print("==================================\n")

    return relationships