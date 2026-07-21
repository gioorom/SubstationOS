from pathlib import Path

import fitz

from .models import RenderedPage


class PdfRenderer:
    """
    Renderizza un PDF in immagini ad alta risoluzione.

    Questa classe non contiene alcuna logica AI.
    Il suo unico compito è trasformare un PDF in PNG.
    """

    def __init__(self, dpi: int = 300):
        self.dpi = dpi

    def render(
        self,
        pdf_path: str | Path,
        output_directory: str | Path,
    ) -> list[RenderedPage]:

        pdf_path = Path(pdf_path)
        output_directory = Path(output_directory)

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        zoom = self.dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        rendered_pages: list[RenderedPage] = []

        with fitz.open(pdf_path) as document:

            for index, page in enumerate(document):

                page_number = index + 1

                pix = page.get_pixmap(
                    matrix=matrix,
                    alpha=False,
                )

                output_path = (
                    output_directory
                    / f"page_{page_number:03d}.png"
                )

                pix.save(output_path)

                rendered_pages.append(
                    RenderedPage(
                        document_path=pdf_path,
                        page_number=page_number,
                        image_path=output_path,
                        width_px=pix.width,
                        height_px=pix.height,
                        dpi=self.dpi,
                    )
                )

                print(
                    f"[Renderer] "
                    f"Pagina {page_number} "
                    f"{pix.width}x{pix.height}"
                )

        return rendered_pages