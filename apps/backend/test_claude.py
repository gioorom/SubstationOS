from dotenv import load_dotenv

load_dotenv("../../.env")

from app.services.ai.extractor import extract_entities

text = """
Quadro MT.

Trasformatore TR-R.
Interruttore 52 MT-TR-R.
Relè di protezione DV7500.
TA lato MT.
TV sbarre.
"""

entities = extract_entities(text)

for e in entities:
    print(e)