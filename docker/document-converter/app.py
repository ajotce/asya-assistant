from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

app = FastAPI(title="Asya Document Converter", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/convert/docx-to-pdf")
async def convert_docx_to_pdf(file: UploadFile = File(...)) -> Response:
    filename = (file.filename or "").lower()
    if not filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Только DOCX поддерживается для конвертации.")

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Пустой DOCX-файл.")

    with tempfile.TemporaryDirectory(prefix="asya-doc-convert-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        source_path = tmp_path / "source.docx"
        source_path.write_bytes(payload)

        cmd = [
            "soffice",
            "--headless",
            "--nologo",
            "--nofirststartwizard",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(tmp_path),
            str(source_path),
        ]

        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=40, check=False)
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="Конвертация превысила лимит времени.") from exc

        output_path = tmp_path / "source.pdf"
        if completed.returncode != 0 or not output_path.exists():
            stderr = (completed.stderr or "").strip()
            detail = stderr or "LibreOffice не смог сконвертировать DOCX в PDF."
            raise HTTPException(status_code=422, detail=detail)

        return Response(content=output_path.read_bytes(), media_type="application/pdf")
