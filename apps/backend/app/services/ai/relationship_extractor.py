import json
from typing import Any

from app.models.knowledge_graph import RelationType
from app.services.ai.claude_provider import ClaudeProvider
from app.services.ai.models import ExtractedRelationship


RELATIONSHIP_EXTRACTION_SYSTEM_PROMPT = """
Sei un ingegnere elettrico esperto di cabine primarie, sottostazioni
AT/MT, schemi funzionali, schemi unifilari, protezioni elettriche,
automazione e commissioning.

Il tuo compito è individuare le relazioni funzionali e topologiche
tra i componenti elettrici presenti nel contenuto fornito.

Il contenuto può derivare dall'estrazione testuale di uno schema
funzionale. Le relazioni potrebbero quindi non essere espresse
con frasi complete, ma essere deducibili da sigle, denominazioni,
descrizioni, riferimenti di pagina e funzione degli apparati.

Restituisci esclusivamente JSON valido, senza testo aggiuntivo.

Formato richiesto:

{
  "relationships": [
    {
      "source": "nome esatto dell'entità sorgente",
      "target": "nome esatto dell'entità destinazione",
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

1. Usa esattamente i nomi delle entità presenti nel contenuto.

2. Non inventare nuovi componenti.

3. Genera una relazione quando:
   - è esplicitamente descritta;
   - è tecnicamente chiaramente deducibile;
   - deriva dalla normale struttura funzionale di una cabina primaria
     o di una sottostazione AT/MT.

4. Considera, quando coerente con il contenuto, che:
   - una linea può essere collegata al proprio interruttore;
   - un interruttore può appartenere a una linea, baia o cella;
   - un TA può misurare la corrente della linea, del trasformatore
     o dell'interruttore associato;
   - un TV può misurare la tensione della linea o della sbarra associata;
   - un sezionatore può essere collegato all'interruttore della stessa baia;
   - un trasformatore può essere collegato agli interruttori AT e MT;
   - un quadro o pannello può controllare gli apparati della stessa baia;
   - un apparato può essere installato nella relativa cella o baia.

5. Non generare una relazione soltanto perché due componenti compaiono
nello stesso documento. Deve esistere una motivazione tecnica plausibile.

6. La direzione source-target deve rispettare il significato della relazione.

Esempi:

{
  "source": "LINEA MT",
  "target": "INTERRUTTORE 43L",
  "relation_type": "connected_to",
  "description": "La linea MT è collegata al proprio interruttore",
  "confidence": 0.85,
  "attributes": {}
}

{
  "source": "TA AT",
  "target": "52AT",
  "relation_type": "measured_by_ct",
  "description": "Il circuito associato all'interruttore 52AT è misurato dal TA AT",
  "confidence": 0.85,
  "attributes": {}
}

7. Usa connected_to quando non è disponibile una relazione più specifica.

8. Se non esiste realmente alcuna relazione tecnicamente deducibile,
restituisci:

{"relationships": []}
"""


def build_relationship_extraction_prompt(
    text: str,
    entity_names: list[str],
) -> str:
    entities_text = "\n".join(
        f"- {name}" for name in entity_names
    )

    return f"""
Analizza il seguente testo tecnico ed estrai le relazioni
tra i componenti elettrici.

Puoi creare relazioni esclusivamente tra le entità
presenti nell'elenco seguente.

ENTITÀ DISPONIBILI:

{entities_text}

REGOLE AGGIUNTIVE:

- source deve corrispondere esattamente a una delle entità disponibili;
- target deve corrispondere esattamente a una delle entità disponibili;
- non usare documenti, località, titoli o descrizioni se non sono
  presenti nell'elenco;
- non inventare nuove entità;
- non creare relazioni di un'entità con sé stessa.

TESTO:

{text}
""".strip()

class AIRelationshipExtractor:
    def __init__(self) -> None:
        self.provider = ClaudeProvider()

    def extract(
    self,
    text: str,
    entity_names: list[str],
) -> list[ExtractedRelationship]:
        if not text or not text.strip():
            return []

        response = self.provider.generate(
    system_prompt=RELATIONSHIP_EXTRACTION_SYSTEM_PROMPT,
    user_prompt=build_relationship_extraction_prompt(
        text=text,
        entity_names=entity_names,
    ),
    temperature=0.0,
)

        print(response.content)
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
    entity_names: list[str],
) -> list[ExtractedRelationship]:
    relationships = _get_relationship_extractor().extract(
        text=text,
        entity_names=entity_names,
    )

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