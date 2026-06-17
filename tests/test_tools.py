from __future__ import annotations

from types import SimpleNamespace

from oracle_ai_database.client import QueryResult
from tools import external_knowledge_search, nl2sql_query, read_only_sql, select_ai_query


class FakeClient:
    def __init__(self):
        self.read_calls = []
        self.select_ai_calls = []

    def execute_read_only(self, sql, *, binds, max_rows):
        self.read_calls.append((sql, binds, max_rows))
        return QueryResult(columns=["ID"], rows=[{"ID": 1}], row_count=1, truncated=False)

    def select_ai(self, *, prompt, profile_name, action):
        self.select_ai_calls.append((prompt, profile_name, action))
        return "```sql\nSELECT id FROM employees\n```"


def _tool_instance(cls):
    tool = cls()
    tool.runtime = SimpleNamespace(credentials={"user": "app", "password": "secret", "dsn": "db/pdb"})
    return tool


def test_read_only_sql_tool_returns_json_message(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(read_only_sql, "client_from_runtime", lambda _tool: client)
    tool = _tool_instance(read_only_sql.ReadOnlySqlTool)

    messages = list(
        tool._invoke(
            {
                "sql": "select id from employees where id = :id",
                "bind_parameters": '{"id": 1}',
                "max_rows": 25,
            }
        )
    )

    assert messages[0]["type"] == "json"
    assert messages[0]["json"]["status"] == "success"
    assert client.read_calls[0] == ("select id from employees where id = :id", {"id": 1}, 25)


def test_select_ai_tool_returns_response(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(select_ai_query, "client_from_runtime", lambda _tool: client)
    tool = _tool_instance(select_ai_query.SelectAiQueryTool)

    message = list(
        tool._invoke(
            {
                "prompt": "show employees",
                "profile_name": "AI_PROFILE",
                "action": "showsql",
            }
        )
    )[0]

    assert message["json"]["status"] == "success"
    assert message["json"]["response"] == "```sql\nSELECT id FROM employees\n```"
    assert client.select_ai_calls == [("show employees", "AI_PROFILE", "showsql")]


def test_nl2sql_tool_validates_generated_sql_before_optional_execution(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(nl2sql_query, "client_from_runtime", lambda _tool: client)
    tool = _tool_instance(nl2sql_query.Nl2SqlQueryTool)

    message = list(
        tool._invoke(
            {
                "question": "which employees exist?",
                "profile_name": "AI_PROFILE",
                "execute": True,
                "max_rows": 3,
            }
        )
    )[0]

    assert message["json"]["status"] == "success"
    assert message["json"]["generated_sql"] == "SELECT id FROM employees"
    assert message["json"]["result"]["row_count"] == 1
    assert client.read_calls[0][2] == 3


def test_external_knowledge_search_tool_uses_safe_sql_builder(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(external_knowledge_search, "client_from_runtime", lambda _tool: client)
    tool = _tool_instance(external_knowledge_search.ExternalKnowledgeSearchTool)

    message = list(
        tool._invoke(
            {
                "query": "oracle ai",
                "table_name": "DOCS",
                "text_column": "BODY",
                "id_column": "ID",
                "metadata_columns": "SOURCE",
                "use_oracle_text": True,
                "max_rows": 5,
            }
        )
    )[0]

    sql, binds, max_rows = client.read_calls[0]
    assert "CONTAINS(BODY, :query, 1)" in sql
    assert binds == {"query": "oracle ACCUM ai"}
    assert max_rows == 5
    assert message["json"]["mode"] == "oracle_text"

