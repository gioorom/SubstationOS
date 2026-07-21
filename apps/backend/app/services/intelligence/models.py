from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DocumentInfo:
    """
    Informazioni generali sul documento analizzato.
    """

    file_path: Path
    file_type: str
    document_type: str
    total_pages: int
    text_pages: list[int] = field(default_factory=list)
    graphical_pages: list[int] = field(default_factory=list)


@dataclass(slots=True)
class RenderedPage:
    """
    Rappresenta una pagina PDF renderizzata come immagine.
    """

    document_path: Path
    page_number: int
    image_path: Path
    width_px: int
    height_px: int
    dpi: int


@dataclass(slots=True)
class ImageTile:
    """
    Rappresenta una porzione ritagliata da una pagina renderizzata.
    """

    document_path: Path
    page_number: int
    tile_number: int
    image_path: Path

    x: int
    y: int
    width: int
    height: int

    source_width: int
    source_height: int

    overlap_px: int = 0


@dataclass(slots=True)
class VisionEntity:
    """
    Entità elettrica individuata dal modello Vision.
    """

    entity_type: str
    name: str
    description: str | None = None
    confidence: float = 0.0

    page_number: int | None = None
    tile_number: int | None = None

    bounding_box: dict[str, int] | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VisionRelationship:
    """
    Collegamento individuato tra due entità elettriche.
    """

    source: str
    target: str
    relation_type: str
    description: str | None = None
    confidence: float = 0.0

    page_number: int | None = None
    tile_number: int | None = None

    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VisionResult:
    """
    Risultato dell'analisi di una pagina o di un tile.
    """

    page_number: int
    tile_number: int | None

    entities: list[VisionEntity] = field(default_factory=list)
    relationships: list[VisionRelationship] = field(default_factory=list)

    raw_response: str | None = None
    model: str | None = None

    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(slots=True)
class DocumentAnalysisResult:
    """
    Risultato completo della pipeline di analisi.
    """

    document: DocumentInfo
    rendered_pages: list[RenderedPage] = field(default_factory=list)
    tiles: list[ImageTile] = field(default_factory=list)

    entities: list[VisionEntity] = field(default_factory=list)
    relationships: list[VisionRelationship] = field(default_factory=list)

    status: str = "pending"
    errors: list[str] = field(default_factory=list)