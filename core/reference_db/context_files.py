"""Сопутствующие документы (концепции, спецификации) к каждому КП.

В data/reference_kp/ лежат сами КП, а в `Примеры для ИИ расчетов/<проект>/` —
концепции архитекторов, спецификации, рабочая документация. Эти материалы
содержат размеры, материалы, отделку и крепления — то, чего часто
не хватает в самих КП.
"""

from __future__ import annotations

from pathlib import Path

# Соответствие имени файла КП папке с контекстом.
KP_TO_CONTEXT_FOLDER: dict[str, str] = {
    "kp_2025-02_mira": "МИРА",
    "kp_2025-07_zhk_wave": "Wave навигация",
    "kp_2025-08_peredelkino": "Переделкино",
    "kp_2025-08_zhk_era": "ЭРА",
    "kp_2025-09_bc_upside": "Upside",
    "kp_2025-09_op_upside": "Upside навгиация",
}

EXAMPLES_ROOT = Path("Примеры для ИИ расчетов")
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".xlsx"}


def _is_kp_duplicate(name: str) -> bool:
    n = name.strip().lower()
    return n.startswith("кп") or n.startswith("kp_") or n.startswith("~$")


def get_context_files(kp_stem: str, project_root: Path | None = None) -> list[Path]:
    """Файлы из папки `Примеры для ИИ расчетов/<проект>/`, кроме самой копии КП."""
    folder_name = KP_TO_CONTEXT_FOLDER.get(kp_stem)
    if not folder_name:
        return []
    root = project_root or Path.cwd()
    folder = root / EXAMPLES_ROOT / folder_name
    if not folder.is_dir():
        return []
    out: list[Path] = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if _is_kp_duplicate(p.name):
            continue
        out.append(p)
    return sorted(out)
