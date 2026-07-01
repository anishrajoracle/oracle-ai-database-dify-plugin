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
    parse_vector,
    sanitize_oracle_text_query,
    validate_identifier,
    validate_read_only_sql,
)
from tools._shared import extract_sql_from_select_ai_response


@pytest.mark.parametrize(
    "sql",
    [
        "select * from employees",
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


def test_bounded_float_accepts_valid_weights_and_rejects_invalid_values():
    assert bounded_float("0.7", default=0.5, minimum=0, maximum=1, name="weight") == 0.7
    assert bounded_float("", default=0.5, minimum=0, maximum=1, name="weight") == 0.5

    with pytest.raises(ValueError, match="weight must be between 0 and 1"):
        bounded_float("1.5", default=0.5, minimum=0, maximum=1, name="weight")


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


def test_extract_sql_from_select_ai_response_accepts_markdown_block():
    response = "Here is SQL:\n```sql\nSELECT * FROM employees\n```"

    assert extract_sql_from_select_ai_response(response) == "SELECT * FROM employees"
