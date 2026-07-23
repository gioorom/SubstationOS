# PDF Tools

Development-environment tooling that lets AI agents reliably process large
engineering PDFs (functional diagrams, single-line diagrams, cable schedules)
for SubstationOS's Document Intelligence Engine.

This directory is developer/environment tooling, not part of the domain
model — see `CLAUDE.md` for the project's architectural rules.

## Available Tools

| File | Purpose |
|---|---|
| `check_environment.py` | Verifies Poppler, Ghostscript, and required Python packages are installed and prints a diagnostic report. |
| `prepare_for_ai.py` | CLI skeleton for a future utility that will inspect, split, compress, and extract content from PDFs before AI ingestion. Not yet implemented — see [Roadmap](#roadmap). |

## Installed Dependencies

### System (CLI) dependencies

| Tool | Provides | Installed via |
|---|---|---|
| Poppler | `pdfinfo`, `pdftotext`, `pdfimages`, `pdfseparate`, `pdfunite`, `pdftoppm` | winget (`oschwartz10612.Poppler`) on Windows; `poppler-utils` package on Linux; `poppler` via Homebrew on macOS |
| Ghostscript | `gs` (`gswin64c` on Windows) | Scoop (`ghostscript`) on Windows; `ghostscript` package on Linux; `ghostscript` via Homebrew on macOS |

On Windows, Poppler was installed via **winget** and Ghostscript via
**Scoop**, because no clean, unambiguous Ghostscript package exists on
winget at the time of writing. Chocolatey was tried first per the project's
preferred order but requires an elevated (Administrator) shell, which was
not available in the automated setup — Scoop was used instead since it
installs per-user without elevation.

### Python packages (`apps/backend/.venv`)

| Package | Purpose |
|---|---|
| `pypdf` | Pure-Python PDF reading/writing/merging. |
| `pymupdf` (imports as `fitz`) | Fast PDF rendering, text and image extraction. |
| `pdfplumber` | Structured text and table extraction. |
| `pillow` | Image handling for rendered pages and extracted images. |
| `ocrmypdf` (optional) | Adds an OCR text layer to scanned PDFs. |
| `pytesseract` (optional) | Python bindings for the Tesseract OCR engine. |

Install or update them with:

```bash
apps/backend/.venv/Scripts/python.exe -m pip install pypdf pymupdf pdfplumber pillow ocrmypdf pytesseract
```

**Note:** `ocrmypdf` and `pytesseract` are Python bindings only. Actually
running OCR also requires the **Tesseract OCR engine** binary
(`tesseract`), which is a separate system dependency, not installed by this
setup. See [Troubleshooting](#troubleshooting).

## Verification Commands

Run the environment check from the repository root:

```bash
apps/backend/.venv/Scripts/python.exe tools/pdf_tools/check_environment.py
```

It exits `0` when every required dependency (Poppler tools, Ghostscript,
`pypdf`, `pymupdf`, `pdfplumber`, `pillow`) is found, and `1` otherwise.

To check a single tool directly:

```bash
pdfinfo -v
pdftotext -v
pdfimages -v
pdfseparate -v
pdfunite -v
pdftoppm -v
gs --version          # gswin64c --version on Windows if 'gs' isn't shimmed
```

## Examples

Inspect a PDF with Poppler directly:

```bash
pdfinfo storage/documents/some_drawing.pdf
```

Render page 1 of a PDF to PNG:

```bash
pdftoppm -png -f 1 -l 1 storage/documents/some_drawing.pdf page
```

Extract embedded images:

```bash
pdfimages -all storage/documents/some_drawing.pdf storage/documents/extracted/image
```

Compress a PDF with Ghostscript (screen-quality preset):

```bash
gs -sDEVICE=pdfwrite -dPDFSETTINGS=/screen -dNOPAUSE -dBATCH \
   -sOutputFile=compressed.pdf storage/documents/some_drawing.pdf
```

The `prepare_for_ai.py` CLI shape (once implemented) will be:

```bash
python tools/pdf_tools/prepare_for_ai.py inspect storage/documents/some_drawing.pdf
python tools/pdf_tools/prepare_for_ai.py split storage/documents/some_drawing.pdf out/ --max-pages 20
python tools/pdf_tools/prepare_for_ai.py compress storage/documents/some_drawing.pdf out/compressed.pdf
python tools/pdf_tools/prepare_for_ai.py extract-text storage/documents/some_drawing.pdf out/text.txt
python tools/pdf_tools/prepare_for_ai.py extract-images storage/documents/some_drawing.pdf out/images/
python tools/pdf_tools/prepare_for_ai.py prepare-batch storage/documents/some_drawing.pdf out/batch/
```

Every subcommand currently raises `NotImplementedError` — this is a
deliberate skeleton (see [Roadmap](#roadmap)).

## Troubleshooting

**`check_environment.py` reports a Poppler/Ghostscript tool as `[MISSING]`
right after installation (Windows).**
Installers that modify the persistent `PATH` environment variable
(winget, Scoop) only affect *new* processes spawned after the change.
Restart your terminal (or sign out/in) so it inherits the updated `PATH`,
then re-run the check.

**`gs` is not found even though Ghostscript is installed.**
On Windows the binary is `gswin64c.exe` (or `gswin32c.exe` on 32-bit
installs); a plain `gs` shim is not guaranteed unless your installer
created one. `check_environment.py` already checks `gs`, `gswin64c`, and
`gswin32c` in that order — if all three are missing, Ghostscript's `bin`
directory is not on `PATH`.

**A Python package check fails even though `pip install` succeeded.**
Confirm you're running the check with the project's virtual-environment
interpreter (`apps/backend/.venv/Scripts/python.exe`), not a system-wide
Python — packages installed in one interpreter are invisible to another.

**OCR commands fail even though `ocrmypdf`/`pytesseract` import correctly.**
Both are Python bindings around the external **Tesseract OCR engine**.
Install the `tesseract` binary separately (e.g. `winget install
UB-Mannheim.TesseractOCR` on Windows, `apt install tesseract-ocr` on
Debian/Ubuntu, `brew install tesseract` on macOS) and ensure it's on
`PATH` before OCR features are usable.

**Chocolatey install fails with a lock-file / access-denied error.**
Chocolatey's default install location (`C:\ProgramData\chocolatey`)
requires an elevated (Administrator) shell. Either re-run from an elevated
terminal, or use winget/Scoop instead — both support non-elevated,
per-user installs.

## Roadmap

`prepare_for_ai.py` is currently a CLI skeleton only. Planned behavior,
once implemented:

- **inspect** — report file size and page count for a PDF.
- **split** — split a large PDF into smaller chunks by page count.
- **compress** — shrink a PDF via Ghostscript.
- **extract-text** — pull all text content out of a PDF.
- **extract-images** — pull embedded images out of a PDF.
- **prepare-batch** — orchestrate the above into a single AI-ingestion-ready
  output directory.

Each command currently raises `NotImplementedError` with a clear log
message; none of this logic exists yet.
