from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
import secrets

from docx import Document
from docx.document import Document as DocxDocument
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from app.core.config import get_settings

PLACEHOLDER_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9\-\(\)\s]{7,20}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{2}\.\d{2}\.\d{4}$")


class DocumentFillValidationError(ValueError):
    pass


@dataclass
class FillValidationResult:
    missing_fields: list[str]
    invalid_fields: dict[str, str]

    @property
    def ok(self) -> bool:
        return not self.missing_fields and not self.invalid_fields


@dataclass
class FilledDocumentArtifact:
    filename: str
    content_type: str
    path: str
    size_bytes: int


class DocumentFillService:
    def preview(
        self,
        *,
        template_fields: list[dict],
        values: dict[str, str],
        template_bytes: bytes,
    ) -> FillValidationResult:
        placeholders = self._extract_placeholders(template_bytes=template_bytes)
        return self._validate(template_fields=template_fields, values=values, placeholders=placeholders)

    def fill(
        self,
        *,
        template_fields: list[dict],
        values: dict[str, str],
        template_bytes: bytes,
        output_filename: str,
        user_id: str,
    ) -> FilledDocumentArtifact:
        placeholders = self._extract_placeholders(template_bytes=template_bytes)
        validation = self._validate(template_fields=template_fields, values=values, placeholders=placeholders)
        if not validation.ok:
            raise DocumentFillValidationError("Missing or invalid fields.")

        document = Document(BytesIO(template_bytes))
        replacements = {key: value for key, value in values.items() if key in placeholders}
        self._replace_placeholders(document=document, replacements=replacements)

        target_dir = Path(get_settings().tmp_dir).resolve() / "generated-documents" / user_id
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._normalize_filename(output_filename)
        unique_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}_{safe_name}.docx"
        target_path = target_dir / unique_name
        document.save(target_path)
        return FilledDocumentArtifact(
            filename=unique_name,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            path=str(target_path),
            size_bytes=target_path.stat().st_size,
        )

    def _extract_placeholders(self, *, template_bytes: bytes) -> set[str]:
        document = Document(BytesIO(template_bytes))
        texts = []
        for paragraph in self._iter_paragraphs(document):
            texts.append(paragraph.text or "")
        found = set()
        for text in texts:
            found.update(match.group(1) for match in PLACEHOLDER_RE.finditer(text))
        return found

    def _validate(
        self,
        *,
        template_fields: list[dict],
        values: dict[str, str],
        placeholders: set[str],
    ) -> FillValidationResult:
        missing_fields: list[str] = []
        invalid_fields: dict[str, str] = {}

        fields_by_key = {str(item.get("key", "")).strip(): item for item in template_fields if item.get("key")}
        required_keys = [
            key
            for key, field in fields_by_key.items()
            if bool(field.get("required")) and (not placeholders or key in placeholders)
        ]
        for key in required_keys:
            value = values.get(key)
            if value is None or not str(value).strip():
                missing_fields.append(key)

        for key, raw in values.items():
            if key not in fields_by_key:
                continue
            value = str(raw).strip()
            if not value:
                continue
            field_type = str(fields_by_key[key].get("type", "text")).lower()
            if field_type == "vin":
                vin = value.upper()
                if not VIN_RE.match(vin):
                    invalid_fields[key] = "VIN must be 17 chars and cannot contain I, O, Q."
            elif field_type == "email":
                if not EMAIL_RE.match(value):
                    invalid_fields[key] = "Invalid email format."
            elif field_type == "phone":
                if not PHONE_RE.match(value):
                    invalid_fields[key] = "Invalid phone format."
            elif field_type == "date":
                if not DATE_RE.match(value):
                    invalid_fields[key] = "Unsupported date format. Use YYYY-MM-DD or DD.MM.YYYY."
        return FillValidationResult(missing_fields=sorted(missing_fields), invalid_fields=invalid_fields)

    def _replace_placeholders(self, *, document: DocxDocument, replacements: dict[str, str]) -> None:
        for paragraph in self._iter_paragraphs(document):
            self._replace_in_paragraph(paragraph=paragraph, replacements=replacements)

    def _replace_in_paragraph(self, *, paragraph: Paragraph, replacements: dict[str, str]) -> None:
        text = paragraph.text
        if not text:
            return
        replaced = text
        for key, value in replacements.items():
            replaced = replaced.replace(f"{{{{{key}}}}}", value)
        if replaced == text:
            return
        runs: list[Run] = list(paragraph.runs)
        if not runs:
            paragraph.text = replaced
            return
        runs[0].text = replaced
        for run in runs[1:]:
            run.text = ""

    def _iter_paragraphs(self, document: DocxDocument) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        paragraphs.extend(document.paragraphs)
        for table in document.tables:
            paragraphs.extend(self._iter_table_paragraphs(table))
        for section in document.sections:
            paragraphs.extend(section.header.paragraphs)
            paragraphs.extend(section.footer.paragraphs)
            for table in section.header.tables:
                paragraphs.extend(self._iter_table_paragraphs(table))
            for table in section.footer.tables:
                paragraphs.extend(self._iter_table_paragraphs(table))
        return paragraphs

    def _iter_table_paragraphs(self, table: Table) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(self._iter_cell_paragraphs(cell))
        return paragraphs

    def _iter_cell_paragraphs(self, cell: _Cell) -> list[Paragraph]:
        paragraphs: list[Paragraph] = list(cell.paragraphs)
        for nested in cell.tables:
            paragraphs.extend(self._iter_table_paragraphs(nested))
        return paragraphs

    @staticmethod
    def _normalize_filename(raw: str) -> str:
        base = re.sub(r"[^a-zA-Z0-9_-]+", "_", raw.strip())
        return base[:80] if base else "filled_template"
