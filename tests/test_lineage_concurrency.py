import os
from concurrent.futures import ThreadPoolExecutor
from secrets import randbelow
from time import monotonic, sleep

import psycopg
import pytest


def test_concurrent_same_day_edges_cannot_commit_a_cycle():
    owner_url = os.getenv("TRACEFOOD_TEST_OWNER_URL")
    if not owner_url:
        pytest.skip("Set TRACEFOOD_TEST_OWNER_URL to a disposable database with the demo fixture")
    first_id, second_id = (f"B{10_000 + randbelow(1_000_000_000)}" for _ in range(2))
    edge = "INSERT INTO tracefood.batch_derivation VALUES (%s, %s, 1)"
    with psycopg.connect(owner_url) as setup:
        with setup.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO tracefood.batch
                       (batch_id, product_name, quantity, unit, production_date, expiry_date)
                   VALUES (%s, 'Tomato Puree', 1, 'kg', '2026-02-01', '2026-04-01')""",
                [(first_id,), (second_id,)],
            )
            cursor.executemany(edge, [(first_id, "B101"), (second_id, "B101")])
    try:
        with psycopg.connect(owner_url) as first, psycopg.connect(owner_url) as second:
            second.execute("SET LOCAL statement_timeout = '6s'")
            first.execute(edge, (first_id, second_id))
            with ThreadPoolExecutor(max_workers=1) as worker:
                pending = worker.submit(second.execute, edge, (second_id, first_id))
                with psycopg.connect(owner_url, autocommit=True) as observer:
                    until = monotonic() + 4
                    while monotonic() < until and not pending.done():
                        waiting = observer.execute(
                            "SELECT 1 FROM pg_locks WHERE pid = %s AND locktype = 'advisory' AND NOT granted",
                            (second.info.backend_pid,),
                        ).fetchone()
                        if waiting:
                            break
                        sleep(0.01)
                    else:
                        pytest.fail("The concurrent edge did not wait on the production-day lock")
                first.commit()
                with pytest.raises(psycopg.errors.RaiseException, match="would create a cycle"):
                    pending.result(timeout=5)
                second.rollback()
    finally:
        with psycopg.connect(owner_url) as cleanup:
            ids = [first_id, second_id]
            cleanup.execute(
                "DELETE FROM tracefood.batch_derivation WHERE output_batch_id = ANY(%s)", (ids,)
            )
            cleanup.execute("DELETE FROM tracefood.batch WHERE batch_id = ANY(%s)", (ids,))
