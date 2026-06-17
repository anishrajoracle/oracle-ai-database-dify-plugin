# Oracle AI Database Dify Plugin

Standalone Dify Tool plugin for Oracle AI Database.

## v0 tools

- `read_only_sql`: run validated read-only SQL and return rows as JSON.
- `select_ai_query`: call Oracle Select AI through `DBMS_CLOUD_AI.GENERATE`.
- `nl2sql_query`: generate SQL with Select AI and optionally execute it after read-only validation.
- `external_knowledge_search`: search an Oracle table through Oracle Text or a safe `LIKE` fallback.

## Local validation

```bash
python -m pytest -q
```

The tests do not require a live Oracle database. They use fake connections and SDK stubs to validate SQL safety, tool wiring, and message output.

## Runtime notes

The plugin uses the Dify plugin SDK at runtime and lazy-loads `oracledb` only when a tool connects to Oracle. Do not commit `.env`, Oracle wallet files, local logs, or `.difypkg` artifacts.
