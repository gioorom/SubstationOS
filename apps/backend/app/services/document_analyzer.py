from pathlib import Path
from typing import Any

import fitz


def analyze_pdf(
    file_path: str | Path,
    dpi: int = 200,
    max_rendered_pages: int = 3,
) -> dict[str, Any]:
    """
    Analizza un PDF e determina se le pagine contengono testo
    oppure se devono essere interpretate come disegni tecnici.

    In questa prima versione renderizza automaticamente le prime
    pagine grafiche come immagini PNG.
    """

    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF non trovato: {pdf_path}"
        )

    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Il file non è un PDF: {pdf_path}"
        )

    output_directory = (
        pdf_path.parent
        / "rendered"
        / pdf_path.stem
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    rendered_pages: list[Path] = []
    text_pages: list[int] = []
    graphical_pages: list[int] = []

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    with fitz.open(pdf_path) as document:
        total_pages = len(document)

        for page_index, page in enumerate(document):
            page_number = page_index + 1

            extracted_text = page.get_text("text").strip()

            if extracted_text:
                text_pages.append(page_number)
            else:
                graphical_pages.append(page_number)

                if len(rendered_pages) < max_rendered_pages:
                    output_file = (
                        output_directory
                        / f"page_{page_number:03d}.png"
                    )

                    pixmap = page.get_pixmap(
                        matrix=matrix,
                        alpha=False,
                    )

                    pixmap.save(output_file)

                    rendered_pages.append(output_file)

                    print(
                        "[DOCUMENT ANALYZER] "
                        f"Pagina grafica {page_number} renderizzata: "
                        f"{output_file}"
                    )

    if graphical_pages:
        document_type = "graphical_pdf"
    else:
        document_type = "text_pdf"

    result = {
        "document_type": document_type,
        "total_pages": total_pages,
        "text_pages": text_pages,
        "graphical_pages": graphical_pages,
        "rendered_pages": [
            str(path)
            for path in rendered_pages
        ],
        "render_output_directory": str(
            output_directory
        ),
    }

    print("===== DOCUMENT ANALYZER =====")
    print(f"Tipo documento: {document_type}")
    print(f"Pagine totali: {total_pages}")
    print(f"Pagine con testo: {len(text_pages)}")
    print(f"Pagine grafiche: {len(graphical_pages)}")
    print(f"Immagini generate: {len(rendered_pages)}")
    print("=============================")

    return result