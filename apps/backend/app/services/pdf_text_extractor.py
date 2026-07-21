from pathlib import Path

import fitz


def extract_text_from_pdf(file_path: str | Path) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    if path.suffix.lower() != ".pdf":
        return ""

    pages: list[str] = []

    with fitz.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            page_text = page.get_text("text").strip()

            print(
                f"[PDF TEXT] Pagina {page_number}: "
                f"{len(page_text)} caratteri estratti"
            )

            if page_text:
                pages.append(
                    f"--- PAGINA {page_number} ---\n{page_text}"
                )

    extracted_text = "\n\n".join(pages).strip()

    print(
        f"[PDF TEXT] Totale caratteri estratti: "
        f"{len(extracted_text)}"
    )

    return extracted_text