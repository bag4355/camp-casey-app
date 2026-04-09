from __future__ import annotations

from camp_casey_app.domain.models import SourceReference


def json_source(file_name: str, label: str, json_pointer: str, excerpt: str | None = None) -> SourceReference:
    return SourceReference(
        source_type="json",
        file_name=file_name,
        label=label,
        json_pointer=json_pointer,
        excerpt=excerpt,
    )


def excel_source(file_name: str, label: str, sheet_name: str, row: int, column: int | None = None, excerpt: str | None = None) -> SourceReference:
    return SourceReference(
        source_type="xlsx",
        file_name=file_name,
        label=label,
        sheet_name=sheet_name,
        row=row,
        column=column,
        excerpt=excerpt,
    )


def generated_source(file_name: str, label: str, excerpt: str | None = None) -> SourceReference:
    return SourceReference(
        source_type="generated",
        file_name=file_name,
        label=label,
        excerpt=excerpt,
    )
