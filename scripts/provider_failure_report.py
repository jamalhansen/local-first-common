#!/usr/bin/env python3
"""Summarize provider-related warning/error logs from operational_log."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import duckdb
from rich.console import Console
from rich.table import Table

DEFAULT_DB_PATH = Path("~/sync/local-first/processing_log.duckdb").expanduser()


def resolve_db_path(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value).expanduser()
    if env := os.environ.get("LOCAL_FIRST_TRACKING_DB"):
        return Path(env).expanduser()
    return DEFAULT_DB_PATH


def top_run_contexts(
    con: duckdb.DuckDBPyConnection, hours: int, limit: int
) -> list[tuple]:
    query = """
    SELECT
        COALESCE(run_context, '(none)') AS run_context,
        COUNT(*) AS failures
    FROM operational_log
    WHERE level IN ('WARNING', 'ERROR', 'CRITICAL')
      AND created_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 hour')
      AND (
        run_context LIKE 'provider_%'
        OR logger_name LIKE '%local_first_common.providers%'
      )
    GROUP BY 1
    ORDER BY failures DESC
    LIMIT ?
    """
    return con.execute(query, [hours, limit]).fetchall()


def top_models(con: duckdb.DuckDBPyConnection, hours: int, limit: int) -> list[tuple]:
    query = """
    SELECT
        COALESCE(source_location, '(unknown-model)') AS model,
        COUNT(*) AS failures
    FROM operational_log
    WHERE level IN ('WARNING', 'ERROR', 'CRITICAL')
      AND created_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 hour')
      AND run_context LIKE 'provider_%'
    GROUP BY 1
    ORDER BY failures DESC
    LIMIT ?
    """
    return con.execute(query, [hours, limit]).fetchall()


def recent_examples(
    con: duckdb.DuckDBPyConnection, hours: int, limit: int
) -> list[tuple]:
    query = """
    SELECT
        created_at,
        COALESCE(run_context, '(none)') AS run_context,
        COALESCE(source_location, '(unknown-model)') AS model,
        LEFT(message, 120) AS message
    FROM operational_log
    WHERE level IN ('WARNING', 'ERROR', 'CRITICAL')
      AND created_at >= CURRENT_TIMESTAMP - (? * INTERVAL '1 hour')
      AND (
        run_context LIKE 'provider_%'
        OR logger_name LIKE '%local_first_common.providers%'
      )
    ORDER BY created_at DESC
    LIMIT ?
    """
    return con.execute(query, [hours, limit]).fetchall()


def print_table(
    console: Console, title: str, columns: list[str], rows: list[tuple]
) -> None:
    table = Table(title=title)
    for index, column in enumerate(columns):
        justify = "right" if index > 0 else "left"
        table.add_column(column, justify=justify)

    if not rows:
        table.add_row("No rows", *("-" for _ in columns[1:]))
    else:
        for row in rows:
            table.add_row(*(str(value) for value in row))

    console.print(table)


def run_report(db_path: Path, hours: int, limit: int, verbose: bool = False) -> int:
    console = Console()

    if not db_path.exists():
        console.print(f"Database not found: {db_path}")
        return 1

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "operational_log" not in tables:
            console.print("Table operational_log not found in the selected DB.")
            return 1

        if verbose:
            total = con.execute("SELECT COUNT(*) FROM operational_log").fetchone()[0]
            console.print(f"Operational rows available: {total}")

        context_rows = top_run_contexts(con, hours, limit)
        model_rows = top_models(con, hours, limit)
        recent_rows = recent_examples(con, hours, limit)
    finally:
        con.close()

    print_table(
        console,
        f"Provider Failure Contexts (last {hours} hours)",
        ["Run Context", "Count"],
        context_rows,
    )
    print_table(
        console,
        f"Provider Models with Failures (last {hours} hours)",
        ["Model", "Count"],
        model_rows,
    )
    print_table(
        console,
        f"Recent Provider Failures (last {hours} hours)",
        ["Created At", "Run Context", "Model", "Message"],
        recent_rows,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize provider-related failures from operational_log.",
    )
    parser.add_argument(
        "-b",
        "--db-path",
        default=None,
        help="Path to DuckDB file (default: LOCAL_FIRST_TRACKING_DB or ~/sync/local-first/processing_log.duckdb)",
    )
    parser.add_argument(
        "-H",
        "--hours",
        type=int,
        default=24,
        help="Lookback window in hours (default: 24)",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=15,
        help="Max rows per section (default: 15)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show extra diagnostics.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.hours <= 0:
        parser.error("--hours must be greater than 0")
    if args.limit <= 0:
        parser.error("--limit must be greater than 0")

    db_path = resolve_db_path(args.db_path)
    return run_report(db_path, args.hours, args.limit, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
