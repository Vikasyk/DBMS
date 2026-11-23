"""Load a generated dataset into an empty TraceFood schema."""

import argparse
import json
import os
from pathlib import Path

import psycopg
from psycopg import sql

from .schema import SEQUENCES, TABLE_COLUMNS


def load(connection, source):
    source = Path(source)
    for table in TABLE_COLUMNS:
        if not (source / f"{table}.csv").is_file():
            raise FileNotFoundError(f"Missing dataset file: {source / f'{table}.csv'}")

    tables = {table: sql.Identifier("tracefood", table) for table in TABLE_COLUMNS}
    with connection.transaction():
        connection.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
            sql.SQL(", ").join(tables.values())
        ))
        for table, identifier in tables.items():
            if connection.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(identifier)).fetchone():
                raise ValueError(f"Load into an empty TraceFood schema. {table} already contains records.")

        with connection.cursor() as cursor:
            for table, columns in TABLE_COLUMNS.items():
                statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER MATCH)").format(
                    tables[table], sql.SQL(", ").join(map(sql.Identifier, columns))
                )
                with (source / f"{table}.csv").open("rb") as data_file, cursor.copy(statement) as copy:
                    while chunk := data_file.read(65_536):
                        copy.write(chunk)

        for sequence, (table, column, prefix, start) in SEQUENCES.items():
            maximum = connection.execute(
                sql.SQL("SELECT max(substr({}, %s)::bigint) FROM {}").format(
                    sql.Identifier(column), tables[table],
                ),
                (len(prefix) + 1,),
            ).fetchone()[0]
            # RESTART advances to the same next ID as setval, and rolls back if the load fails.
            connection.execute(sql.SQL("ALTER SEQUENCE {} RESTART WITH {}").format(
                sql.Identifier("tracefood", sequence), sql.Literal(maximum + 1 if maximum is not None else start)
            ))

        alerts = connection.execute("SELECT tracefood.fn_run_rule_checks()").fetchone()[0]
        for identifier in tables.values():
            connection.execute(sql.SQL("ANALYZE {}").format(identifier))
        counts = {
            table: connection.execute(sql.SQL("SELECT count(*) FROM {}").format(identifier)).fetchone()[0]
            for table, identifier in tables.items()
        }
    return {"database": connection.info.dbname, "tables": counts, "rule_alerts": alerts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--database-url", default=os.getenv("DB_OWNER_URL"))
    arguments = parser.parse_args()
    if not arguments.database_url:
        parser.error("Set DB_OWNER_URL or pass --database-url for a database owner connection.")
    try:
        with psycopg.connect(arguments.database_url, autocommit=True) as connection:
            counts = load(connection, arguments.input)
    except (psycopg.Error, ValueError, FileNotFoundError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
