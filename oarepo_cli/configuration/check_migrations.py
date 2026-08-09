#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Check migrations script for Invenio/OARepo repositories.

This script compares the current database schema against the Alembic migrations
and outputs either the pending upgrade operations as JSON or the corresponding
SQL statements.

It is designed to be run from within an initialized Flask application context,
such as via ``invenio shell``:

    $ invenio shell
    >>> from check_migrations import main
    ...
    ... main()

Or as a standalone script when run from a repository with services running:

    $ python check_migrations.py [--sql]

Arguments:
    --sql: Output SQL statements instead of JSON operation descriptions

Output format (JSON mode, default):
    JSON array of migration operations representing the differences between
    the current database schema and the model metadata. Each operation contains:
    - op_type: The type of operation (e.g., "CreateTableOp", "AddColumnOp")
    - table_name: Target table name (if applicable)
    - column_name: Target column name (if applicable)
    - Other operation-specific fields

Example output (no pending migrations):
    []

Example output (pending migrations):
    [
        {
            "op_type": "CreateTableOp",
            "table_name": "my_table",
            "schema": null,
            "columns": ["id", "name"]
        }
    ]

Output format (SQL mode, --sql):
    Plain text SQL statements that would be executed to apply the pending
    migrations. Uses PostgreSQL dialect since Invenio uses PostgreSQL.

Example output:
    CREATE TABLE my_table (
        id INTEGER NOT NULL,
        name VARCHAR(50),
        PRIMARY KEY (id)
    );

    ALTER TABLE existing_table ADD COLUMN new_column INTEGER;

Exit codes:
    0: Success (output to stdout)
    1: Error (error details to stderr)

"""

from __future__ import annotations

import argparse
import io
import json
import sys
from typing import Any


def _extract_operation(op: Any) -> dict[str, Any]:  # noqa: C901
    """Extract operation information into a JSON-serializable dict.

    Args:
        op: An Alembic operation object

    Returns:
        Dictionary containing operation details

    """
    op_type = type(op).__name__
    op_info: dict[str, Any] = {"op_type": op_type}

    # Extract common attributes based on operation type
    if hasattr(op, "table_name"):
        op_info["table_name"] = op.table_name
    if hasattr(op, "schema"):
        op_info["schema"] = op.schema
    if hasattr(op, "columns"):
        op_info["columns"] = [col.name if hasattr(col, "name") else str(col) for col in op.columns]
    if hasattr(op, "column_name"):
        op_info["column_name"] = op.column_name
    if hasattr(op, "constraint_name"):
        op_info["constraint_name"] = op.constraint_name
    if hasattr(op, "referenced_table_name"):
        op_info["referenced_table_name"] = op.referenced_table_name
    if hasattr(op, "type_"):
        op_info["type"] = str(op.type_)
    if hasattr(op, "nullable"):
        op_info["nullable"] = op.nullable
    if hasattr(op, "existing_nullable"):
        op_info["existing_nullable"] = op.existing_nullable
    if hasattr(op, "parameters"):
        op_info["parameters"] = op.parameters

    # Recursively extract nested operations (e.g., ModifyTableOps contains ops)
    if hasattr(op, "ops") and op.ops:
        op_info["nested_ops"] = [_extract_operation(nested_op) for nested_op in op.ops]

    return op_info


def _extract_operations_from_upgrade_ops(
    upgrade_ops: Any,
) -> list[dict[str, Any]]:
    """Extract all operations from UpgradeOps object.

    Args:
        upgrade_ops: Alembic UpgradeOps object

    Returns:
        List of operation dictionaries

    """
    result: list[dict[str, Any]] = []

    if hasattr(upgrade_ops, "ops"):
        result.extend(_extract_operation(op) for op in upgrade_ops.ops)

    return result


def _generate_sql_from_operations(migration_script: Any) -> str:
    """Generate SQL statements from a migration script using Alembic's Operations.

    This uses Alembic's built-in SQL generation by configuring a MigrationContext
    with as_sql=True and capturing the output.

    Args:
        migration_script: Alembic MigrationScript object from produce_migrations

    Returns:
        SQL statements as a string

    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    buf = io.StringIO()

    # Configure a migration context that generates SQL instead of executing
    ctx = MigrationContext.configure(
        url="postgresql://",
        opts={
            "as_sql": True,
            "output_buffer": buf,
        },
    )

    operations = Operations(ctx)

    def invoke_ops(ops_list: list[Any]) -> None:
        """Recursively invoke operations to generate SQL."""
        for op in ops_list:
            # If operation has nested ops, recurse into them without invoking the parent
            if hasattr(op, "ops") and op.ops:
                invoke_ops(op.ops)
            else:
                # Leaf operation - invoke it to generate SQL
                operations.invoke(op)

    # Invoke each operation to generate SQL
    if hasattr(migration_script, "upgrade_ops"):
        invoke_ops(migration_script.upgrade_ops.ops)

    return buf.getvalue()


def check_migrations(as_sql: bool = False) -> Any:
    """Compare database schema against model metadata and return pending migrations.

    This function:
    1. Gets the current Flask application
    2. Retrieves the Alembic instance from InvenioDB extension
    3. Uses the migration context with active database connection
    4. Compares database schema against target metadata using produce_migrations
    5. Extracts and returns either operation descriptions or SQL statements

    Args:
        as_sql: If True, return SQL statements instead of operation descriptions

    Requires:
        To be called within an active Flask application context where InvenioDB
        has been initialized and services are running.

    Returns:
        List of pending migration operations (as dicts) or SQL string

    Raises:
        RuntimeError: If InvenioDB extension not found or no connection available

    """
    from alembic.autogenerate import produce_migrations
    from flask import current_app

    # Get the alembic instance from InvenioDB extension
    if "invenio-db" not in current_app.extensions:
        raise RuntimeError("InvenioDB extension not found in app.extensions")

    alembic = current_app.extensions["invenio-db"].alembic

    # Get the database connection from the migration context
    if not alembic.migration_contexts:
        raise RuntimeError("No Alembic migration contexts available")

    migration_context = next(iter(alembic.migration_contexts.values()))

    if migration_context.connection is None:
        raise RuntimeError("Migration context has no active connection")

    # Get the target metadata from the database extension
    from invenio_db import db

    target_metadata = db.metadata

    # Produce migrations comparison
    migrations = produce_migrations(migration_context, target_metadata)

    # Extract upgrade operations
    if not hasattr(migrations, "upgrade_ops"):
        return []

    if as_sql:
        return _generate_sql_from_operations(migrations)

    return _extract_operations_from_upgrade_ops(migrations.upgrade_ops)


def main() -> int:
    """Run the migration check and output results to stdout.

    Expects to be called within an active Flask application context where
    InvenioDB has been initialized. Can be used:

    1. From invenio shell:
       >>> from check_migrations import main
       ...
       ... main()

    2. As standalone script:
       $ python check_migrations.py
       $ python check_migrations.py --sql

    Returns:
        Exit code (0 for success, non-zero for error)

    """
    parser = argparse.ArgumentParser(description="Check pending database migrations and output as JSON or SQL")
    parser.add_argument(
        "sql",
        nargs="?",
        const=True,
        default=False,
        help="Output SQL statements instead of JSON (pass 'sql' to enable)",
    )
    args = parser.parse_args()

    try:
        from flask import current_app

        # Check we're in an app context
        if not current_app:
            raise RuntimeError("Not in Flask application context")

        # Run the migration check
        pending_migrations = check_migrations(as_sql=bool(args.sql))

        if args.sql:
            # Output SQL statements
            print(pending_migrations, end="")  # noqa: T201
        else:
            # Output JSON
            print(json.dumps(pending_migrations, indent=2))  # noqa: T201

        return 0

    except RuntimeError as e:
        error_response = {"error": str(e)}
        print(json.dumps(error_response), file=sys.stderr)  # noqa: T201
        return 1
    except Exception as e:  # noqa: BLE001
        error_response = {"error": f"Unexpected error: {e}"}
        print(json.dumps(error_response), file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main())
