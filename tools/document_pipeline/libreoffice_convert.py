"""Windows compatibility adapter for Anthropic document-skills.

The upstream helper currently invokes "soffice" directly
(`scripts/office/soffice.py` in the docx skill, installed under
`~/.claude/plugins/marketplaces/anthropic-agent-skills/`). That script is
written for Linux/macOS sandboxes (AF_UNIX socket detection, LD_PRELOAD
shim, `SAL_USE_VCLPLUGIN=svp`) and calls `subprocess.run(["soffice"], ...)`
literally, with no extension. Verified 2026-09-07 on this machine:

  - `subprocess.run(["soffice"], ...)` on Windows -> immediate
    `FileNotFoundError` (Python's subprocess does not resolve a bare
    extensionless name the way cmd.exe's PATHEXT lookup does).
  - `soffice.exe` (the GUI-subsystem launcher), even called directly by
    absolute path -> hangs indefinitely (>7 min, near-zero CPU) — almost
    certainly a single-instance IPC / window-station check that never
    completes in this sandboxed session.
  - `soffice.com` (the console-mode launcher) and `soffice.bin` (the real
    binary) -> both start and exit correctly, instantly.

This adapter intentionally uses `soffice.com` on Windows and never
`soffice.exe`. It does NOT modify, wrap, or replace the upstream skill —
it is a standalone, local, infra-only script for S.A.P.I.'s documentation
pipeline (tools/document_pipeline/), not part of the application
(src/, app/, tests/, data/) and not a patch to the marketplace plugin.

Usage:
    python tools/document_pipeline/libreoffice_convert.py input.docx output_dir/
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 120

_WINDOWS_CANDIDATE_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.com",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.com",
)


class ConversionError(RuntimeError):
    """LibreOffice conversion failed — process error, timeout, or a PDF
    that doesn't exist / is empty once the process returns."""


def _resolve_soffice_binary() -> str:
    """Resolution order: `SOFFICE_BIN` env var -> `shutil.which("soffice.com")`
    -> known Windows install paths -> `soffice` (Linux/macOS).

    Deliberately never returns `soffice.exe` on Windows — see module
    docstring for why. `soffice.bin` is left as the internal binary the
    launchers wrap; for console/batch automation `soffice.com` is the
    right entry point on Windows.
    """
    env_override = os.environ.get("SOFFICE_BIN")
    if env_override:
        return env_override

    if platform.system() == "Windows":
        found = shutil.which("soffice.com")
        if found:
            return found
        for candidate in _WINDOWS_CANDIDATE_PATHS:
            if Path(candidate).exists():
                return candidate
        raise ConversionError(
            "No se encontró soffice.com en Windows (ni en PATH ni en las rutas "
            "conocidas de instalación). Instala LibreOffice o define la variable "
            "de entorno SOFFICE_BIN con la ruta exacta a soffice.com."
        )

    found = shutil.which("soffice")
    if found:
        return found
    raise ConversionError(
        "No se encontró 'soffice' en PATH (Linux/macOS). Instala LibreOffice "
        "o define SOFFICE_BIN."
    )


def convert_docx_to_pdf(
    input_docx: Path,
    output_dir: Path,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Path:
    """Convierte `input_docx` a PDF dentro de `output_dir`.

    Nunca modifica `input_docx` (LibreOffice corre en modo conversión de
    solo lectura sobre el archivo de entrada). Usa un perfil de
    LibreOffice temporal y exclusivo de esta ejecución
    (`-env:UserInstallation=<uri>`), creado y limpiado automáticamente,
    para evitar locks/IPC contra una instancia ya abierta o un perfil de
    usuario compartido — la causa más común de cuelgues en conversiones
    batch de LibreOffice.

    Lanza `ConversionError` si LibreOffice devuelve un código de error, si
    expira el timeout, o si el PDF resultante no aparece o queda vacío.
    """
    input_docx = Path(input_docx).resolve()
    output_dir = Path(output_dir).resolve()
    if not input_docx.exists():
        raise ConversionError(f"No existe el archivo de entrada: {input_docx}")
    output_dir.mkdir(parents=True, exist_ok=True)

    soffice_bin = _resolve_soffice_binary()
    expected_pdf = output_dir / (input_docx.stem + ".pdf")

    with tempfile.TemporaryDirectory(prefix="sapi_lo_profile_") as profile_dir:
        profile_uri = Path(profile_dir).as_uri()
        cmd = [
            soffice_bin,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            "--norestore",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_docx),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ConversionError(
                f"Conversión excedió el timeout de {timeout}s.\n"
                f"stdout parcial: {exc.stdout!r}\nstderr parcial: {exc.stderr!r}"
            ) from exc

    if result.returncode != 0:
        raise ConversionError(
            f"LibreOffice devolvió código {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    if not expected_pdf.exists():
        raise ConversionError(
            f"LibreOffice terminó sin error pero no generó {expected_pdf}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    if expected_pdf.stat().st_size == 0:
        raise ConversionError(f"El PDF generado está vacío (0 bytes): {expected_pdf}")

    return expected_pdf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_docx", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    pdf_path = convert_docx_to_pdf(args.input_docx, args.output_dir, timeout=args.timeout)
    print(f"OK: {pdf_path} ({pdf_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
