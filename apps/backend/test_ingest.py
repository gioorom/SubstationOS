from dotenv import load_dotenv

load_dotenv("../../.env", override=True)

from app.database.database import SessionLocal
from app.services.knowledge_graph import ingest_document

db = SessionLocal()

try:
    entities = ingest_document(
        db=db,
        project_id=1,
        text="""
Quadro MT Siemens tipo NXPLUS.

Trasformatore TR-R da 25 MVA 132/20 kV.

Interruttore ABB VD4 matricola CB-001.

Relè Siemens SIPROTEC 5 7SJ82.

TA rapporto 1000/1 A classe 5P20.

TV rapporto 20000/100 V.

Sezionatore linea 132 kV.

Scaricatore di sovratensione ABB PEXLIM.
""",
        source_document="test_manuale.txt",
    )

    print("\n")
    print("=" * 80)
    print("ENTITÀ SALVATE NEL KNOWLEDGE GRAPH")
    print("=" * 80)

    for entity in entities:
        print()
        print("-" * 80)
        print(f"ID           : {entity.id}")
        print(f"Tipo         : {entity.entity_type}")
        print(f"Nome         : {entity.name}")
        print(f"Descrizione  : {entity.description}")
        print(f"Documento    : {entity.source_document}")
        print(f"Attributi    : {entity.attributes}")

    print()
    print("=" * 80)
    print(f"Totale entità: {len(entities)}")
    print("=" * 80)

finally:
    db.close()