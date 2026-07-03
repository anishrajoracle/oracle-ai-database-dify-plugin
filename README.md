# Guarded Oracle AI Database Retrieval and Actions

Bounded SQL actions and retrieval tools for Oracle AI Database in Dify. The plugin combines read-only SQL, a human-configured write action, Oracle Text, vector, and hybrid search with provider-level credentials.

- **Author:** [anishrajoracle](https://github.com/anishrajoracle)
- **Source:** [GitHub repository](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin)
- **Support:** [GitHub Issues](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin/issues)

## Features

- Bind-aware `SELECT` and `WITH` queries with bounded JSON results.
- A configured `INSERT`, `UPDATE`, or opt-in `DELETE` action with table and affected-row limits.
- Oracle Text or parameterized, case-insensitive `LIKE` search.
- Cosine similarity over existing `VECTOR` columns.
- Weighted text-and-vector hybrid retrieval.

## Requirements and connection

- Dify 1.14.2 or later and a reachable Oracle endpoint.
- A dedicated account with only the required `SELECT` privileges for retrieval workflows.
- For write workflows, grant only the required DML privileges on intended tables and any narrowly scoped `SELECT` Oracle requires for conditional updates/deletes; do not grant DDL, package execution, database links, or `ANY` privileges.
- An Oracle Text `CONTEXT` index when Oracle Text mode is enabled.
- Oracle `VECTOR` support for vector and hybrid search. Query and stored vectors must have the same dimension.

Dify Cloud requires a reachable endpoint. Private endpoints and wallet files normally require self-hosted Dify. Wallet paths must exist inside the runtime; wallet upload is not supported.

## Setup

1. The latest frozen local package is v0.0.4. Current source is the unpublished v0.0.6 release candidate and must be packaged and validated before installation. Use Marketplace installation only after the public listing is verified.
2. Under **Plugins**, select **Guarded Oracle Retrieval and Actions** and **Authorize**.
3. Enter and validate the connection.

| Credential | Required | Description |
| --- | --- | --- |
| User / Password | Yes | Oracle credentials. |
| DSN | Conditional | For example `db.example.com:1521/FREEPDB1`. |
| Host / Service Name | Conditional | Both are needed without a DSN. |
| Port | No | Defaults to `1521`. |
| Config Directory | No | Runtime Oracle Net configuration directory. |
| Wallet Location / Password | No | Runtime wallet settings. |
| Enable Write Actions | No | Defaults to false. Enable only on an authorization intended for configured write workflows. |

Prefer TCPS or Oracle Native Network Encryption. Never package or commit credentials or wallets.

## Usage

| Tool | Configuration and input |
| --- | --- |
| `read_only_sql` | Configure `max_rows`; pass one query and optional named binds as JSON. |
| `write_only_sql` | A human configures and enables one SQL template, target-table allowlist, delete policy, and row limit; the agent supplies only named scalar binds. |
| `external_knowledge_search` | Configure table, columns, text mode, and limit; pass search text. |
| `external_vector_search` | Configure table and columns; pass an embedding as a JSON number array. |
| `hybrid_knowledge_search` | Configure text/vector columns and weights; pass text and its embedding. |

Example:

```text
sql: SELECT ticket_id, title FROM support_tickets WHERE customer_id = :customer_id
bind_parameters: {"customer_id": 42}
max_rows: 100
```

First enable write actions in the selected provider authorization. Then configure the tool:

```text
sql: UPDATE support_tickets SET status = :status WHERE ticket_id = :ticket_id
allowed_tables: SUPPORT_TICKETS
allow_delete: false
max_affected_rows: 1

agent input:
bind_parameters: {"status":"CLOSED","ticket_id":42}
```

The model cannot enable writes or change the configured SQL, table allowlist, delete policy, or row limit. Because only `bind_parameters` is model-facing, the workflow instructions must name the required bind keys and their meaning. Successful writes return only the operation, target table, affected-row count, and commit status—never database rows.

Generate vectors upstream with the same dimension as stored vectors. See the [demo guide](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin/tree/main/demo) for a runnable schema and examples.

## Security and privacy

- Read-only SQL checks reject multiple statements, comments, DML, DDL, PL/SQL, `SELECT FOR UPDATE`, and `DBMS_*`.
- Write SQL is disabled by default and fixed by the workflow author. It permits one allowlisted `INSERT ... VALUES`, single-target `UPDATE ... WHERE`, or explicitly enabled `DELETE ... WHERE`; it rejects `SELECT`/`WITH`, `UPDATE ... FROM`, `MERGE`, DDL, PL/SQL, comments, `RETURNING`, error logging, database links, and non-scalar or mismatched binds, and it never returns database rows.
- Only named `:identifier` binds are supported; positional binds and Oracle JSON colon syntax are outside this tool's SQL subset. The table allowlist checks the target name written in SQL, while Oracle authorization remains responsible for the objects behind synonyms or views.
- All five tools use the credentials from the selected provider authorization. `Enable Write Actions` is an explicit gate, not an independent credential boundary; Oracle grants determine what that account can actually change.
- In a local Oracle 23ai Free validation, cross-schema `INSERT` worked with an insert-only grant, while conditional `UPDATE` returned `ORA-41900` until the target table also had `SELECT` granted. The tool is write-only at its interface, but the database account may still need target-table read privilege for Oracle to evaluate predicates.
- Writes use an explicit transaction. The plugin commits only when Oracle reports a non-negative affected-row count within the configured limit; otherwise it rolls back. It never retries a write automatically, and a commit transport failure is reported as an unknown outcome.
- Dify, an agent, or a user can still invoke an action more than once. Prefer naturally idempotent SQL or database uniqueness/business keys, and add workflow-level deduplication for non-idempotent updates such as counters.
- The affected-row guard does not bound query work, locks, trigger/cascade effects, sequence increments, or autonomous routines. Permitted SQL functions may still have side effects. Least-privilege Oracle grants remain the real security boundary.
- Write SQL supports only simple, unquoted, unqualified identifiers made from letters, digits, and underscores; aliases and `$`/`#` identifiers are rejected. Results cap at 1,000 SQL rows, 100 search rows, and 16 KiB per LOB; caps do not limit query cost.
- Connections use 10-second connect and 110-second call timeouts. Errors redact configured secrets but may reveal object names.

The plugin sends credentials and inputs to the configured Oracle endpoint and returns results to Dify. It adds no telemetry or author-operated storage; configured writes persist in the selected Oracle database. See [PRIVACY.md](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin/blob/main/PRIVACY.md).

## Publishing status

Version 0.0.6 is a source release candidate and is not yet packaged, published, or verified in the Dify Marketplace. The latest frozen local package remains v0.0.4. The write tool requires live validation against a disposable table before release. The next maintainer must complete the ordered engineering, privacy/IP, packaging, live-validation, Marketplace PR, and post-publication steps in [MARKETPLACE_HANDOVER.md](MARKETPLACE_HANDOVER.md). Do not describe a local `.difypkg` as Marketplace availability.

Oracle and Oracle AI Database are trademarks of Oracle and/or its affiliates. This community plugin is not an official Oracle product and is not endorsed by Oracle.
