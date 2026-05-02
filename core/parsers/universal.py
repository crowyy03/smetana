"""Роутер: формат → парсер."""

from __future__ import annotations

from pathlib import Path

from core.parsers.docx_parser import DocxParser
from core.parsers.excel_parser import ExcelParser
from core.parsers.pdf_parser import PDFParser
from core.parsers.text_parser import TextParser
from core.parsers.types import ParseResult, ParseSource


class UniversalParser:
    async def parse(self, source: ParseSource) -> ParseResult:
        fmt = source.file_format
        if fmt == "auto":
            if source.file_path:
                fmt = self._detect_from_path(source.file_path)
            elif source.text is not None:
                fmt = "text"
            else:
                raise ValueError("Нет file_path и нет text")

        if fmt == "text":
            assert source.text is not None
            return await TextParser().parse(source.text)

        assert source.file_path is not None
        path = Path(source.file_path)

        if fmt in ("xlsx", "xls"):
            if fmt == "xls":
                return ParseResult(
                    items=[],
                    confidence=0.0,
                    needs_manual_review=True,
                    parser_notes=["Старый .xls не поддерживается — конвертируй в .xlsx"],
                )
            return await ExcelParser().parse(path)
        if fmt == "pdf":
            return await PDFParser().parse(path)
        if fmt == "docx":
            return await DocxParser().parse(path)
        raise ValueError(f"Unsupported format: {fmt}")

    @staticmethod
    def _detect_from_path(path: Path) -> str:
        s = path.suffix.lower()
        if s in (".xlsx", ".xls"):
            return "xlsx" if s == ".xlsx" else "xls"
        if s == ".pdf":
            return "pdf"
        if s == ".docx":
            return "docx"
        return "text"
