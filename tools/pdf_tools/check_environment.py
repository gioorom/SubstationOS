from __future__ import annotations

import importlib.metadata
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass

POPPLER_TOOLS = (
    "pdfinfo",
    "pdftotext",
    "pdfimages",
    "pdfseparate",
    "pdfunite",
    "pdftoppm",
)

GHOSTSCRIPT_CANDIDATES = ("gs", "gswin64c", "gswin32c")

REQUIRED_PACKAGES = (
    "pypdf",
    "pymupdf",
    "pdfplumber",
    "pillow",
)

OPTIONAL_PACKAGES = (
    "ocrmypdf",
    "pytesseract",
)


@dataclass(frozen=True, slots=True)
class ToolCheck:
    name: str
    found: bool
    version: str | None = None
    path: str | None = None
    note: str | None = None


def _run_version(executable: str, *args: str) -> str | None:
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError:
        return None

    output = (result.stdout or result.stderr or "").strip()

    if not output:
        return None

    return output.splitlines()[0]


def check_poppler_tool(name: str) -> ToolCheck:
    path = shutil.which(name)

    if path is None:
        return ToolCheck(name=name, found=False)

    version = _run_version(path, "-v")

    return ToolCheck(name=name, found=True, version=version, path=path)


def check_ghostscript() -> ToolCheck:
    for candidate in GHOSTSCRIPT_CANDIDATES:
        path = shutil.which(candidate)

        if path is None:
            continue

        version = _run_version(path, "--version")

        return ToolCheck(
            name="gs",
            found=True,
            version=version,
            path=path,
            note=f"invoked as '{candidate}'" if candidate != "gs" else None,
        )

    return ToolCheck(name="gs", found=False)


def check_python_package(package: str) -> ToolCheck:
    try:
        version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return ToolCheck(name=package, found=False)

    return ToolCheck(name=package, found=True, version=version)


def collect_checks() -> tuple[
    list[ToolCheck],
    ToolCheck,
    list[ToolCheck],
    list[ToolCheck],
]:
    poppler_checks = [check_poppler_tool(tool) for tool in POPPLER_TOOLS]
    ghostscript_check = check_ghostscript()
    required_checks = [
        check_python_package(package) for package in REQUIRED_PACKAGES
    ]
    optional_checks = [
        check_python_package(package) for package in OPTIONAL_PACKAGES
    ]

    return poppler_checks, ghostscript_check, required_checks, optional_checks


def _format_check(check: ToolCheck) -> str:
    if not check.found:
        return f"  [MISSING] {check.name}"

    detail = check.version or "version unknown"
    suffix = f" ({check.note})" if check.note else ""

    return f"  [OK]      {check.name} - {detail}{suffix}"


def print_report(
    poppler_checks: list[ToolCheck],
    ghostscript_check: ToolCheck,
    required_checks: list[ToolCheck],
    optional_checks: list[ToolCheck],
) -> bool:
    print(
        f"SubstationOS PDF Environment Report "
        f"- {platform.system()} {platform.release()}"
    )
    print()

    print("Poppler:")
    for check in poppler_checks:
        print(_format_check(check))
    print()

    print("Ghostscript:")
    print(_format_check(ghostscript_check))
    print()

    print("Required Python packages:")
    for check in required_checks:
        print(_format_check(check))
    print()

    print("Optional Python packages (OCR support):")
    for check in optional_checks:
        print(_format_check(check))
    print()

    required_all = [*poppler_checks, ghostscript_check, *required_checks]
    missing = [check.name for check in required_all if not check.found]

    if missing:
        print(f"Environment INCOMPLETE - missing: {', '.join(missing)}")
    else:
        print("Environment READY - all required dependencies found.")

    return not missing


def main() -> int:
    poppler_checks, ghostscript_check, required_checks, optional_checks = (
        collect_checks()
    )
    is_ready = print_report(
        poppler_checks,
        ghostscript_check,
        required_checks,
        optional_checks,
    )

    return 0 if is_ready else 1


if __name__ == "__main__":
    sys.exit(main())
