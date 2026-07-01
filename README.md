# Oracle AI Database Dify Plugin

Standalone Dify Tool plugin for Oracle AI Database.

## Tools

- `read_only_sql`: run validated read-only SQL and return rows as JSON.
- `external_knowledge_search`: search an Oracle table through Oracle Text or a safe `LIKE` fallback.
- `external_vector_search`: find semantically similar rows with Oracle vector distance.
- `hybrid_knowledge_search`: combine Oracle Text and vector similarity scores.

## Local validation

```bash
python -m pytest -q
```

The tests do not require a live Oracle database. They use fake connections and SDK stubs to validate SQL safety, tool wiring, and message output.

## Runtime notes

The plugin uses the Dify plugin SDK at runtime and lazy-loads `oracledb` only when a tool connects to Oracle. Do not commit `.env`, Oracle wallet files, local logs, or `.difypkg` artifacts.
