from pathlib import Path
import fitz


def render_pdf_pages(
    pdf_path: str | Path,
    output_dir: str | Path,
    dpi: int = 300,
) -> list[Path]:
    """
    Renderizza tutte le pagine di un PDF in PNG.

    Restituisce la lista dei file PNG generati.
    """

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    generated_files: list[Path] = []

    with fitz.open(pdf_path) as document:

        for page_number, page in enumerate(document):

            pix = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )

            output_file = (
                output_dir
                / f"page_{page_number + 1:03d}.png"
            )

            pix.save(output_file)

            generated_files.append(output_file)

            print(
                f"[PDF RENDER] Pagina {page_number + 1} -> {output_file.name}"
            )

    print(
        f"[PDF RENDER] Generate {len(generated_files)} immagini."
    )

    return generated_files