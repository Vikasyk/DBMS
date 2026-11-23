from ..db import require_record


def require_batch(conn, batch_id):
    row = conn.execute(
        "SELECT batch_id FROM tracefood.batch WHERE batch_id = %s", (batch_id,),
    ).fetchone()
    require_record(row, "Batch", batch_id)


def get_batch(conn, batch_id):
    row = conn.execute(
        """SELECT b.*, CASE WHEN q.check_id IS NULL THEN NULL
                  ELSE to_jsonb(q) END AS latest_quality
           FROM tracefood.v_batch_overview b
           LEFT JOIN tracefood.v_latest_quality q USING (batch_id)
           WHERE b.batch_id = %s""",
        (batch_id,),
    ).fetchone()
    return require_record(row, "Batch", batch_id)


def get_lineage(conn, batch_id, direction="both", *, check_batch=True):
    if check_batch:
        require_batch(conn, batch_id)
    upstream = []
    downstream = []
    if direction in {"up", "both"}:
        upstream = conn.execute("SELECT * FROM tracefood.fn_upstream(%s)", (batch_id,)).fetchall()
    if direction in {"down", "both"}:
        downstream = conn.execute("SELECT * FROM tracefood.fn_downstream(%s)", (batch_id,)).fetchall()
    ids = [batch_id] + [row["batch_id"] for row in upstream + downstream]
    edges = conn.execute(
        """SELECT * FROM tracefood.v_lineage_edges
           WHERE input_batch_id = ANY(%s) AND output_batch_id = ANY(%s)
           ORDER BY output_production_date, output_batch_id, input_batch_id""",
        (ids, ids),
    ).fetchall()
    return {"batch_id": batch_id, "direction": direction, "upstream": upstream, "downstream": downstream, "edges": edges}


def origin_farms(conn, batch_id):
    return conn.execute("SELECT * FROM tracefood.fn_origin_farms(%s)", (batch_id,)).fetchall()
