from __future__ import annotations

import pytest

from oracle_ai_database.sql_safety import (
    SqlSafetyError,
    bounded_float,
    build_external_hybrid_search_sql,
    build_external_vector_search_sql,
    build_external_search_sql,
    has_bind_placeholders,
    parse_bind_parameters,
    parse_identifier_allowlist,
    parse_vector,
    parse_write_bind_parameters,
    sanitize_oracle_text_query,
    validate_identifier,
    validate_read_only_sql,
    validate_write_only_sql,
)


@pytest.mark.parametrize(
    "sql",
    [
        "select * from employees",
        'select "MixedCase", col$ from employees',
        "  WITH recent AS (SELECT * FROM employees) SELECT * FROM recent",
        "select name from employees;",
    ],
)
def test_validate_read_only_sql_accepts_single_select_or_with(sql):
    assert validate_read_only_sql(sql).sql.lower().startswith(("select", "with"))


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "delete from employees",
        "select * from employees; drop table employees",
        "select * from employees for update",
        "select dbms_random.value from dual",
        "select * from employees -- hidden",
        "begin null; end;",
    ],
)
def test_validate_read_only_sql_rejects_mutating_or_ambiguous_sql(sql):
    with pytest.raises(SqlSafetyError):
        validate_read_only_sql(sql)


@pytest.mark.parametrize(
    ("sql", "operation"),
    [
        ("insert into tickets (id, title) values (:id, :title)", "INSERT"),
        ("update tickets set status = :status where id = :id", "UPDATE"),
        ("delete from tickets where id = :id", "DELETE"),
    ],
)
def test_validate_write_only_sql_accepts_allowlisted_single_table_dml(sql, operation):
    safe_sql = validate_write_only_sql(
        sql,
        allowed_tables={"TICKETS"},
        allow_delete=operation == "DELETE",
    )

    assert safe_sql.operation == operation
    assert safe_sql.target_table == "TICKETS"
    assert safe_sql.sql.lower().startswith(operation.lower())


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("select * from tickets", "Only INSERT, UPDATE, or DELETE"),
        ("merge into tickets", "Only INSERT, UPDATE, or DELETE"),
        ("update tickets set status = :status", "UPDATE requires a WHERE clause"),
        ("update tickets set status = :where", "UPDATE requires a WHERE clause"),
        ('update tickets set "WHERE" = :value', "Quoted identifiers are not allowed"),
        ("update dual set$where set dummy = :value", "Dollar and hash characters are not allowed"),
        ("delete from dual where$x", "Dollar and hash characters are not allowed"),
        ("update tickets set x$where = :value", "Dollar and hash characters are not allowed"),
        (
            "update tickets set status = source.status from source where tickets.id = source.id",
            "UPDATE FROM is not allowed",
        ),
        ("delete from tickets", "DELETE requires a WHERE clause"),
        ("insert into tickets (id) select id from archived_tickets", "SELECT and WITH are not allowed"),
        ("insert into tickets (id) values (:id) returning id into :result", "RETURNING is not allowed"),
        ("update tickets set id = dbms_random.value where id = :id", "DBMS package calls are not allowed"),
        ("insert into tickets (id) values (:id) log errors", "LOG ERRORS is not allowed"),
        ("insert into tickets select * from remote_tickets@archive", "Unsupported INSERT syntax"),
        ("insert into tickets (id) values (remote_sequence.nextval@archive)", "Database links are not allowed"),
        ("insert into tickets (title) values (q'[WHERE; DELETE]')", "Alternative quoted literals are not allowed"),
        ('insert into "TICKETS" (id) values (:id)', "Quoted identifiers are not allowed"),
        ("insert into tickets values (:id)", "Unsupported INSERT syntax"),
        ("update tickets set status = :status where id = :id; delete from tickets", "Only one SQL statement"),
        ("begin insert into tickets (id) values (:id); end;", "Only one SQL statement"),
        ("update tickets set status = :status where id = :id -- hidden", "SQL comments are not allowed"),
    ],
)
def test_validate_write_only_sql_rejects_unsafe_or_non_write_sql(sql, message):
    with pytest.raises(SqlSafetyError, match=message):
        validate_write_only_sql(sql, allowed_tables={"TICKETS", "DUAL"}, allow_delete=True)


def test_validate_write_only_sql_enforces_table_allowlist_and_delete_opt_in():
    with pytest.raises(SqlSafetyError, match="AUDIT_LOG is not in the configured write table allowlist"):
        validate_write_only_sql(
            "insert into audit_log (message) values (:message)",
            allowed_tables={"TICKETS"},
            allow_delete=False,
        )


@pytest.mark.parametrize(
    "sql",
    [
        "update sys . dual set dummy = :value where dummy = :previous_value",
        "delete from sys . dual where dummy = :value",
        "update only (sys.dual) set dummy = :value where dummy = :previous_value",
        "update tickets t set status = :status where t.id = :id",
        "delete from tickets t where t.id = :id",
    ],
)
def test_validate_write_only_sql_rejects_qualified_targets_and_aliases(sql):
    with pytest.raises(SqlSafetyError, match="Unsupported (UPDATE|DELETE) syntax"):
        validate_write_only_sql(
            sql,
            allowed_tables={"SYS", "ONLY", "TICKETS"},
            allow_delete=True,
        )


def test_validate_write_only_sql_ignores_keywords_inside_string_values():
    safe_sql = validate_write_only_sql(
        "insert into tickets (title) values ('SELECT WITH RETURNING')",
        allowed_tables={"TICKETS"},
        allow_delete=False,
    )

    assert safe_sql.operation == "INSERT"

    safe_update = validate_write_only_sql(
        "update tickets set status = :where where id = :id",
        allowed_tables={"TICKETS"},
        allow_delete=False,
    )
    assert safe_update.operation == "UPDATE"

    with pytest.raises(SqlSafetyError, match="DELETE is disabled"):
        validate_write_only_sql(
            "delete from tickets where id = :id",
            allowed_tables={"TICKETS"},
            allow_delete=False,
        )


def test_identifier_allowlist_is_required_and_case_insensitive():
    assert parse_identifier_allowlist("tickets, AUDIT_LOG") == {"TICKETS", "AUDIT_LOG"}

    with pytest.raises(SqlSafetyError, match="allowed_tables must contain at least one table"):
        parse_identifier_allowlist("")

    with pytest.raises(SqlSafetyError, match="Invalid write table name"):
        parse_identifier_allowlist("tickets, other.schema")

    with pytest.raises(SqlSafetyError, match="Invalid write table name"):
        parse_identifier_allowlist("tickets$")


def test_write_bind_parameters_require_exact_scalar_named_values():
    sql = "update tickets set status = :status where id = :ticket_id or parent_id = :ticket_id"

    assert parse_write_bind_parameters(sql, '{"status": "CLOSED", "ticket_id": 42}') == {
        "status": "CLOSED",
        "ticket_id": 42,
    }

    with pytest.raises(ValueError, match="Missing write bind parameters: TICKET_ID"):
        parse_write_bind_parameters(sql, '{"status": "CLOSED"}')

    with pytest.raises(ValueError, match="Unexpected write bind parameters: OTHER"):
        parse_write_bind_parameters(sql, '{"status": "CLOSED", "ticket_id": 42, "other": 1}')


@pytest.mark.parametrize("value", [True, [1], {"nested": 1}, float("nan"), float("inf")])
def test_write_bind_parameters_reject_non_scalar_or_non_finite_values(value):
    with pytest.raises(ValueError, match="Write bind parameter ID"):
        parse_write_bind_parameters("insert into tickets (id) values (:id)", {"id": value})


def test_write_bind_parameters_reject_case_insensitive_duplicates():
    with pytest.raises(ValueError, match="Duplicate write bind parameter: ID"):
        parse_write_bind_parameters(
            "insert into tickets (id) values (:id)",
            {"id": 1, "ID": 2},
        )

    with pytest.raises(ValueError, match="Duplicate write bind parameter: ID"):
        parse_write_bind_parameters(
            "insert into tickets (id) values (:id)",
            '{"id": 1, "ID": 2}',
        )


def test_write_bind_parameters_match_the_sql_placeholder_case():
    assert parse_write_bind_parameters(
        "insert into tickets (id) values (:TICKET_ID)",
        {"ticket_id": 42},
    ) == {"TICKET_ID": 42}


def test_bind_parameters_must_be_json_object_with_safe_names():
    assert parse_bind_parameters('{"department_id": 10}') == {"department_id": 10}

    with pytest.raises(ValueError):
        parse_bind_parameters("[1, 2]")

    with pytest.raises(SqlSafetyError):
        parse_bind_parameters('{"bad-name": 10}')


def test_has_bind_placeholders_ignores_colons_inside_string_literals():
    assert has_bind_placeholders("select * from employees where id = :id")
    assert not has_bind_placeholders("select 'https://example.com/a:b' as url from dual")


def test_identifier_and_external_search_sql_are_validated():
    assert validate_identifier("DOCS_2026") == "DOCS_2026"

    with pytest.raises(SqlSafetyError):
        validate_identifier("DOCS;DROP")

    sql = build_external_search_sql(
        table_name="DOCS",
        text_column="BODY",
        id_column="ID",
        metadata_columns=["SOURCE"],
        use_oracle_text=True,
    )
    assert sql == (
        "SELECT ID, BODY, SOURCE, SCORE(1) AS search_score FROM DOCS "
        "WHERE CONTAINS(BODY, :query, 1) > 0 ORDER BY SCORE(1) DESC"
    )

    with pytest.raises(SqlSafetyError):
        build_external_search_sql(
            table_name="DOCS",
            text_column="BODY) OR 1=1 --",
            id_column="ID",
            metadata_columns=[],
            use_oracle_text=False,
        )


def test_parse_vector_accepts_json_array_and_rejects_invalid_values():
    assert parse_vector("[0.1, 2, -3]") == [0.1, 2.0, -3.0]

    with pytest.raises(ValueError, match="query_vector must be a JSON array"):
        parse_vector('{"not": "a vector"}')

    with pytest.raises(ValueError, match=r"query_vector\[1\] must be a number"):
        parse_vector("[0.1, true]")


@pytest.mark.parametrize("value", ["[NaN]", "[Infinity]", "[-Infinity]"])
def test_parse_vector_rejects_non_finite_values(value):
    with pytest.raises(ValueError, match=r"query_vector\[0\] must be a finite number"):
        parse_vector(value)


def test_bounded_float_accepts_valid_weights_and_rejects_invalid_values():
    assert bounded_float("0.7", default=0.5, minimum=0, maximum=1, name="weight") == 0.7
    assert bounded_float("", default=0.5, minimum=0, maximum=1, name="weight") == 0.5

    with pytest.raises(ValueError, match="weight must be between 0 and 1"):
        bounded_float("1.5", default=0.5, minimum=0, maximum=1, name="weight")


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_bounded_float_rejects_non_finite_values(value):
    with pytest.raises(ValueError, match="weight must be a finite number"):
        bounded_float(value, default=0.5, minimum=0, maximum=1, name="weight")


def test_external_vector_search_sql_uses_cosine_vector_distance():
    sql = build_external_vector_search_sql(
        table_name="DOCS",
        vector_column="EMBEDDING",
        content_column="BODY",
        id_column="ID",
        metadata_columns=["SOURCE"],
    )

    assert "VECTOR_DISTANCE(EMBEDDING, :query_vector, COSINE)" in sql
    assert "WHERE EMBEDDING IS NOT NULL" in sql
    assert "ORDER BY VECTOR_DISTANCE" in sql


def test_external_hybrid_search_sql_combines_text_and_vector_scores():
    sql = build_external_hybrid_search_sql(
        table_name="DOCS",
        text_column="BODY",
        vector_column="EMBEDDING",
        content_column="BODY",
        id_column="ID",
        metadata_columns=["SOURCE"],
        use_oracle_text=True,
        candidate_rows=25,
    )

    assert "WITH vector_candidates AS" in sql
    assert "CONTAINS(BODY, :query, 1) > 0" in sql
    assert "VECTOR_DISTANCE(EMBEDDING, :query_vector, COSINE)" in sql
    assert "(:vector_weight * MAX(vector_score)) + (:text_weight * MAX(text_score)) AS hybrid_score" in sql
    assert "SELECT source.ID, source.BODY, source.SOURCE" in sql


def test_oracle_text_query_drops_reserved_and_unsafe_tokens():
    assert sanitize_oracle_text_query("oracle AND ai??? oracle") == "oracle ACCUM ai"

    with pytest.raises(SqlSafetyError):
        sanitize_oracle_text_query("AND OR ???")
