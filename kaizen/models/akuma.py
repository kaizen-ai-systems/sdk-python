from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Guardrails:
    """Security guardrails for Akuma queries."""

    read_only: bool = True
    allow_tables: list[str] | None = None
    deny_tables: list[str] | None = None
    deny_columns: list[str] | None = None
    max_rows: int | None = None
    timeout_secs: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"readOnly": self.read_only}
        if self.allow_tables:
            payload["allowTables"] = self.allow_tables
        if self.deny_tables:
            payload["denyTables"] = self.deny_tables
        if self.deny_columns:
            payload["denyColumns"] = self.deny_columns
        if self.max_rows:
            payload["maxRows"] = self.max_rows
        if self.timeout_secs:
            payload["timeoutSecs"] = self.timeout_secs
        return payload


@dataclass
class AkumaQueryResponse:
    """Response from Akuma query."""

    sql: str
    rows: list[dict[str, Any]] | None = None
    explanation: str | None = None
    tables: list[str] | None = None
    warnings: list[str] | None = None
    error: str | None = None


@dataclass
class AkumaExplainResponse:
    """Response from Akuma explain."""

    sql: str
    explanation: str


@dataclass
class AkumaColumn:
    """Schema column description for Akuma context."""

    name: str
    type: str
    nullable: bool = False
    description: str = ""
    examples: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "type": self.type,
            "nullable": self.nullable,
            "description": self.description,
        }
        if self.examples:
            payload["examples"] = self.examples
        return payload


@dataclass
class AkumaForeignKey:
    """Schema foreign key relationship for Akuma context."""

    columns: list[str]
    ref_table: str
    ref_columns: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "refTable": self.ref_table,
            "refColumns": self.ref_columns,
        }


@dataclass
class AkumaTable:
    """Schema table description for Akuma context."""

    name: str
    columns: list[AkumaColumn]
    description: str = ""
    primary_key: list[str] | None = None
    foreign_keys: list[AkumaForeignKey] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "columns": [column.to_dict() for column in self.columns],
        }
        if self.primary_key:
            payload["primaryKey"] = self.primary_key
        if self.foreign_keys:
            payload["foreignKeys"] = [fk.to_dict() for fk in self.foreign_keys]
        return payload


@dataclass
class AkumaSchemaResponse:
    """Response from Akuma schema update."""

    status: str
    tables: int
