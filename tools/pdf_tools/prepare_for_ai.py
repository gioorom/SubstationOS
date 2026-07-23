from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

LOGGER = logging.getLogger("prepare_for_ai")


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def inspect_pdf(pdf_path: Path) -> None:
    """
    Report file size and page count for a single PDF.
    """
    # TODO: read file size via Path.stat()
    # TODO: read page count via pypdf or pymupdf
    raise NotImplementedError


def split_pdf(pdf_path: Path, output_dir: Path, max_pages: int) -> None:
    """
    Split a large PDF into chunks of at most `max_pages` pages.
    """
    # TODO: split via pdfseparate/pdfunite or pypdf, preserving page order
    raise NotImplementedError


def compress_pdf(pdf_path: Path, output_path: Path) -> None:
    """
    Compress a PDF with Ghostscript to reduce file size.
    """
    # TODO: shell out to Ghostscript with a chosen /dPDFSETTINGS profile
    raise NotImplementedError


def extract_text(pdf_path: Path, output_path: Path) -> None:
    """
    Extract all text content from a PDF.
    """
    # TODO: extract via pdftotext or pdfplumber, page by page
    raise NotImplementedError


def extract_images(pdf_path: Path, output_dir: Path) -> None:
    """
    Extract embedded images from a PDF.
    """
    # TODO: extract via pdfimages or pymupdf
    raise NotImplementedError


def prepare_ai_batch(pdf_path: Path, output_dir: Path) -> None:
    """
    Prepare an AI-ingestion-ready batch: inspect, split, compress, and
    extract text/images into a structured output directory.
    """
    # TODO: orchestrate inspect_pdf, split_pdf, compress_pdf, extract_text
    # TODO: and extract_images into a single pipeline
    raise NotImplementedError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="prepare_for_ai",
        description="Prepare engineering PDFs for AI ingestion.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect", help="Report PDF size and page count."
    )
    inspect_parser.add_argument("pdf_path", type=Path)

    split_parser = subparsers.add_parser(
        "split", help="Split a large PDF into smaller chunks."
    )
    split_parser.add_argument("pdf_path", type=Path)
    split_parser.add_argument("output_dir", type=Path)
    split_parser.add_argument("--max-pages", type=int, default=20)

    compress_parser = subparsers.add_parser(
        "compress", help="Compress a PDF with Ghostscript."
    )
    compress_parser.add_argument("pdf_path", type=Path)
    compress_parser.add_argument("output_path", type=Path)

    extract_text_parser = subparsers.add_parser(
        "extract-text", help="Extract text content from a PDF."
    )
    extract_text_parser.add_argument("pdf_path", type=Path)
    extract_text_parser.add_argument("output_path", type=Path)

    extract_images_parser = subparsers.add_parser(
        "extract-images", help="Extract embedded images from a PDF."
    )
    extract_images_parser.add_argument("pdf_path", type=Path)
    extract_images_parser.add_argument("output_dir", type=Path)

    batch_parser = subparsers.add_parser(
        "prepare-batch", help="Prepare a full AI-ingestion-ready batch."
    )
    batch_parser.add_argument("pdf_path", type=Path)
    batch_parser.add_argument("output_dir", type=Path)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    dispatch = {
        "inspect": lambda: inspect_pdf(args.pdf_path),
        "split": lambda: split_pdf(
            args.pdf_path, args.output_dir, args.max_pages
        ),
        "compress": lambda: compress_pdf(args.pdf_path, args.output_path),
        "extract-text": lambda: extract_text(
            args.pdf_path, args.output_path
        ),
        "extract-images": lambda: extract_images(
            args.pdf_path, args.output_dir
        ),
        "prepare-batch": lambda: prepare_ai_batch(
            args.pdf_path, args.output_dir
        ),
    }

    try:
        dispatch[args.command]()
    except NotImplementedError:
        LOGGER.error(
            "'%s' is a skeleton only - functionality not yet implemented.",
            args.command,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
