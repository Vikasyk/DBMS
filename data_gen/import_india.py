"""Import the India workbook into an empty PostgreSQL database using DB_OWNER_URL."""
import argparse
import hashlib
import os
from contextlib import closing
from pathlib import Path

import psycopg
from openpyxl import load_workbook
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
SHEETS = ("FARM", "PROCESSING_FACILITY", "RETAILER", "BATCH", "QUALITY_CHECK",
          "SHIPMENT", "ANOMALY_ALERT", "PRICE_RECORD", "BATCH_SHIPMENT")


def stage(conn, path, digest):
    with conn.transaction(), closing(load_workbook(path, read_only=True, data_only=True)) as book:
        if set(book.sheetnames) != set(SHEETS):
            raise ValueError("Expected the nine India workbook sheets")
        conn.execute("CREATE SCHEMA india_source")
        conn.execute("CREATE TABLE india_source.manifest (sheet text PRIMARY KEY, rows int, sha256 text)")
        for sheet in SHEETS:
            records = iter(book[sheet].values)
            columns = [sql.Identifier(c.lower()) for c in next(records)]
            target = sql.Identifier("india_source", sheet.lower())
            conn.execute(sql.SQL("CREATE TABLE {} ({})").format(target, sql.SQL(", ").join(
                sql.SQL("{} text").format(c) for c in columns)))
            count = 0
            with conn.cursor().copy(sql.SQL("COPY {} FROM STDIN").format(target)) as copy:
                for row in records:
                    copy.write_row(row)
                    count += 1
            conn.execute("INSERT INTO india_source.manifest VALUES (%s,%s,%s)", (sheet, count, digest))
            print(sheet, count, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    with args.workbook.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    with psycopg.connect(os.environ["DB_OWNER_URL"], autocommit=True) as conn:
        if conn.execute("SELECT to_regnamespace('tracefood')").fetchone()[0]:
            raise ValueError("Use an empty database. The operational schema already exists.")
        if not conn.execute("SELECT to_regnamespace('india_source')").fetchone()[0]:
            stage(conn, args.workbook, digest)
        elif conn.execute("SELECT DISTINCT sha256 FROM india_source.manifest").fetchall() != [(digest,)]:
            raise ValueError("Existing source import belongs to a different workbook")
        with conn.transaction():
            for file in ("01_schema", "india_records", "02_integrity", "03_views", "04_functions",
                         "05_roles", "07_lineage_concurrency", "08_numeric_integrity", "india_views", "india_trace"):
                conn.execute((ROOT / "db" / f"{file}.sql").read_text(encoding="utf8"))
        conn.execute("ANALYZE")


if __name__ == "__main__":
    main()

