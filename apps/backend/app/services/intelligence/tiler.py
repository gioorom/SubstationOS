from math import ceil
from pathlib import Path

from PIL import Image

from .models import ImageTile, RenderedPage


class AdaptiveTileEngine:
    """
    Divide automaticamente una pagina renderizzata in tile.

    Ogni tile mantiene una sovrapposizione per evitare che
    simboli e testi vengano tagliati ai bordi.
    """

    def __init__(
        self,
        tile_size: int = 2048,
        overlap: int = 256,
    ):
        self.tile_size = tile_size
        self.overlap = overlap

    def generate_tiles(
        self,
        rendered_page: RenderedPage,
        output_directory: str | Path,
    ) -> list[ImageTile]:

        output_directory = Path(output_directory)
        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        image = Image.open(rendered_page.image_path)

        width, height = image.size

        step = self.tile_size - self.overlap

        cols = max(1, ceil((width - self.overlap) / step))
        rows = max(1, ceil((height - self.overlap) / step))

        generated_tiles: list[ImageTile] = []

        tile_number = 1

        for row in range(rows):

            for col in range(cols):

                x = col * step
                y = row * step

                x = min(
                    x,
                    max(0, width - self.tile_size),
                )

                y = min(
                    y,
                    max(0, height - self.tile_size),
                )

                crop = image.crop(
                    (
                        x,
                        y,
                        min(width, x + self.tile_size),
                        min(height, y + self.tile_size),
                    )
                )

                filename = (
                    f"page_{rendered_page.page_number:03d}"
                    f"_tile_{tile_number:03d}.png"
                )

                output_path = output_directory / filename

                crop.save(output_path)

                generated_tiles.append(
                    ImageTile(
                        document_path=rendered_page.document_path,
                        page_number=rendered_page.page_number,
                        tile_number=tile_number,
                        image_path=output_path,
                        x=x,
                        y=y,
                        width=crop.width,
                        height=crop.height,
                        source_width=width,
                        source_height=height,
                        overlap_px=self.overlap,
                    )
                )

                tile_number += 1

        print(
            f"[Tile Engine] "
            f"Pagina {rendered_page.page_number}: "
            f"{len(generated_tiles)} tile generate."
        )

        return generated_tiles