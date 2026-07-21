import json
from typing import Any

from app.models.knowledge_graph import EntityType
from app.services.ai.claude_provider import ClaudeProvider
from app.services.ai.models import (
    ExtractedEntity,
    ExtractionResult,
)
from app.services.ai.prompts import (
    ENTITY_EXTRACTION_SYSTEM_PROMPT,
    build_entity_extraction_prompt,
)


class AIEntityExtractor:
    def __init__(self) -> None:
        self.provider = ClaudeProvider()

    def extract(self, text: str) -> list[ExtractedEntity]:
        """
        Estrae le entità tecniche dal testo utilizzando Claude.
        """

        if not text or not text.strip():
            print("\n===== TESTO INVIATO A CLAUDE =====")
            print("Testo vuoto: nessun contenuto ricevuto.")
            print("==================================\n")
            return []

        prompt = build_entity_extraction_prompt(text)

        print("\n===== TESTO INVIATO A CLAUDE =====")
        print(prompt[:5000])

        if len(prompt) > 5000:
            print("\n[Output interrotto dopo 5000 caratteri]")

        print("==================================\n")

        response = self.provider.generate(
            system_prompt=ENTITY_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.0,
        )

        data = self._parse_response(response.content)

        entities: list[ExtractedEntity] = []
        seen: set[tuple[EntityType, str]] = set()

        for item in data:
            entity_type_value = item.get("entity_type")
            name_value = item.get("name")

            if not isinstance(entity_type_value, str):
                continue

            if not isinstance(name_value, str):
                continue

            name = name_value.strip()

            if not name:
                continue

            try:
                entity_type = EntityType(entity_type_value)
            except ValueError:
                continue

            key = (
                entity_type,
                name.casefold(),
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

            if isinstance(attributes_value, dict):
                attributes = dict(attributes_value)
            else:
                attributes = {}

            entities.append(
                ExtractedEntity(
                    entity_type=entity_type,
                    name=name,
                    confidence=confidence,
                    description=description,
                    attributes=attributes,
                )
            )

        return entities

    @staticmethod
    def _parse_response(
        content: str,
    ) -> list[dict[str, Any]]:
        """
        Converte la risposta JSON di Claude in una lista di dizionari.
        """

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
                "Claude non ha restituito un JSON valido.\n\n"
                f"Risposta ricevuta:\n{content}"
            ) from exc

        if isinstance(parsed, dict):
            parsed = parsed.get("entities", [])

        if not isinstance(parsed, list):
            raise RuntimeError(
                "Claude deve restituire una lista di entità "
                "oppure un oggetto con la proprietà 'entities'."
            )

        return [
            item
            for item in parsed
            if isinstance(item, dict)
        ]


_extractor: AIEntityExtractor | None = None


def _get_extractor() -> AIEntityExtractor:
    global _extractor

    if _extractor is None:
        _extractor = AIEntityExtractor()

    return _extractor


def extract_entities(
    text: str,
) -> list[ExtractedEntity]:
    """
    Funzione pubblica per l'estrazione delle entità.
    """

    entities = _get_extractor().extract(text)

    print("\n===== DEBUG CLAUDE =====")

    if not entities:
        print("Nessuna entità estratta.")

    for entity in entities:
        print("-" * 60)
        print(f"Tipo       : {entity.entity_type}")
        print(f"Nome       : {entity.name}")
        print(f"Descrizione: {entity.description}")
        print(f"Confidence : {entity.confidence}")
        print(f"Attributi  : {entity.attributes}")

    print("========================\n")

    return entities


def extract_document(
    text: str,
) -> ExtractionResult:
    """
    Estrae tutte le informazioni disponibili dal documento.
    """

    return ExtractionResult(
        entities=extract_entities(text),
    )