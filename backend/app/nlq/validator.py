from sqlglot import Dialect, ErrorLevel, exp, parse
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.scope import Scope, traverse_scope
from sqlglot.tokens import TokenType


ALLOWED_VIEWS = frozenset({
    "v_alerts",
    "v_batch_facilities",
    "v_batch_overview",
    "v_facilities",
    "v_farms",
    "v_lineage_edges",
    "v_price_history",
    "v_quality_checks",
    "v_retailers",
    "v_shipment_lines",
    "v_shipment_summary",
    "v_stage_price_monthly",
})
RESULT_LIMIT = 200
_POSTGRES = Dialect.get_or_raise("postgres")

# Permitted grammar and built-ins for reports. Unknown syntax and functions fail closed.
_ALLOWED_NODES = frozenset("""
    Select Union With CTE Subquery From Join Table TableAlias Identifier
    Alias Column Star Literal Boolean Null Distinct Where Group Having
    Order Ordered Limit Offset Window WindowSpec Filter
    Paren And Or Not EQ NEQ GT GTE LT LTE Is In Between Like ILike Exists
    Add Sub Mul Div IntDiv Mod Neg Case If
    Count Sum Avg Min Max Round Abs Coalesce Nullif Greatest Least
    Lower Upper Trim Length Concat RowNumber Rank DenseRank Lag Lead
    Cast DataType DataTypeParam CurrentDate CurrentTimestamp Interval
    Extract TimestampTrunc DateTrunc TimeToStr Var
""".split())
_ALLOWED_TYPES = frozenset("""
    BIGINT BOOLEAN CHAR DATE DECIMAL DOUBLE FLOAT INT INTERVAL SMALLINT
    TEXT TIMESTAMP TIMESTAMPTZ VARCHAR
""".split())
_DATE_PARTS = frozenset("""
    YEAR QUARTER MONTH WEEK DAY HOUR MINUTE SECOND MILLISECOND
    DOW ISODOW DOY EPOCH ISOYEAR
""".split())


class RejectedQuery(ValueError):
    pass


def validate(query: str) -> str:
    """Return the only SQL that may be executed for a generated query."""
    if not query.strip() or len(query) > 8000:
        raise RejectedQuery("The SQL is empty or exceeds the query size limit.")
    try:
        tokens = _POSTGRES.tokenize(query)
        if any(token.comments or token.token_type == TokenType.SEMICOLON for token in tokens):
            raise RejectedQuery("Comments and statement separators are not allowed.")
        if len(tokens) > 750:
            raise RejectedQuery("The SQL exceeds the query complexity limit.")
        statements = parse(query, read="postgres")
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union)):
            raise RejectedQuery("Only one SELECT query is allowed.")
        tree = normalize_identifiers(statements[0], dialect="postgres")
        for node in tree.walk():
            if type(node).__name__ not in _ALLOWED_NODES:
                raise RejectedQuery("The query includes an operation or function outside the allowlist.")
            if isinstance(node, exp.With) and node.args.get("recursive"):
                raise RejectedQuery("Recursive generated queries are not supported.")
            if isinstance(node, exp.DataType) and node.this.name not in _ALLOWED_TYPES:
                raise RejectedQuery("The query uses an unsupported data type.")
            if isinstance(node, exp.Var) and str(node.this).upper() not in _DATE_PARTS:
                raise RejectedQuery("The query uses an unsupported SQL keyword.")
            if isinstance(node, exp.Column) and (node.catalog or node.db not in ("", "tracefood")):
                raise RejectedQuery("Only columns in the tracefood schema can be read.")
            if isinstance(node, exp.Identifier) and (
                not node.name or "\x00" in node.name or len(node.name.encode("utf-8")) > 63
            ):
                raise RejectedQuery("The query includes an invalid identifier.")
        _qualify_sources(tree)
        sql = tree.sql(dialect="postgres", unsupported_level=ErrorLevel.RAISE)
    except (SqlglotError, RecursionError, UnicodeError) as exc:
        raise RejectedQuery("The SQL could not be parsed as a supported PostgreSQL SELECT.") from exc
    return f"SELECT * FROM ({sql}) AS tracefood_result LIMIT {RESULT_LIMIT}"


def _qualify_sources(tree: exp.Expr) -> None:
    scopes = {
        id(node): source
        for scope in traverse_scope(tree)
        for node, source in scope.selected_sources.values()
        if isinstance(node, exp.Table)
    }
    allowed_view_used = False
    for table in tree.find_all(exp.Table):
        source = scopes.get(id(table))
        if source is None or table.args.get("catalog") is not None or not isinstance(table.this, exp.Identifier):
            raise RejectedQuery("Only curated views and local query aliases can be read.")
        if not table.db and isinstance(source, Scope) and source.is_cte:
            continue
        if table.name not in ALLOWED_VIEWS or table.db not in ("", "tracefood"):
            raise RejectedQuery("Only curated views in the tracefood schema can be read.")
        table.set("db", exp.to_identifier("tracefood"))
        allowed_view_used = True
    if not allowed_view_used:
        raise RejectedQuery("The query must read a curated TraceFood view.")
