"""Measure downstream lineage plans with and without the lineage input index."""

import argparse
import json
import os
from pathlib import Path
from statistics import median

import psycopg


QUERY = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM tracefood.fn_downstream(%s)"


def collect_plans(connection, batch_id, repeats):
    connection.execute(QUERY, (batch_id,)).fetchone()
    plans = [connection.execute(QUERY, (batch_id,)).fetchone()[0][0] for _ in range(repeats)]
    return {
        "median_planning_ms": median(plan["Planning Time"] for plan in plans),
        "median_execution_ms": median(plan["Execution Time"] for plan in plans),
        "rows": plans[0]["Plan"]["Actual Rows"],
        "plans": plans,
    }


def compare_index(connection, batch_id=None, repeats=5):
    with connection.transaction(force_rollback=True):
        if batch_id is None:
            row = connection.execute(
                """SELECT input_batch_id FROM tracefood.batch_derivation
                   GROUP BY input_batch_id ORDER BY count(*) DESC, input_batch_id LIMIT 1"""
            ).fetchone()
            if row is None:
                raise ValueError("The database contains no lineage edges.")
            batch_id = row[0]
        with_index = collect_plans(connection, batch_id, repeats)
        connection.execute("DROP INDEX tracefood.ix_derivation_input")
        without_index = collect_plans(connection, batch_id, repeats)
        if with_index["rows"] != without_index["rows"]:
            raise RuntimeError("Lineage row counts differ between the measured plans.")
    return {
        "database": connection.info.dbname, "batch_id": batch_id, "query": QUERY, "runs": repeats,
        "with_index": with_index, "without_index": without_index,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DB_OWNER_URL"))
    parser.add_argument("--batch-id")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if not arguments.database_url:
        parser.error("Set DB_OWNER_URL or pass --database-url for a database owner connection.")
    if arguments.repeats < 1:
        parser.error("--repeats must be positive.")
    try:
        with psycopg.connect(arguments.database_url, autocommit=True) as connection:
            comparison = compare_index(connection, arguments.batch_id, arguments.repeats)
    except (psycopg.Error, ValueError) as error:
        parser.exit(1, f"{error}\n")
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    for configuration in ("with_index", "without_index"):
        comparison[configuration].pop("plans")
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
