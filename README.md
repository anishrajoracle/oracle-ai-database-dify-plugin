# Knowledge Retrieval for Oracle Database

Read-only SQL and retrieval tools for Oracle AI Database in Dify. It exposes no write tool and focuses on Oracle Text, vector, and hybrid search with provider-level credentials.

- **Author:** [anishrajoracle](https://github.com/anishrajoracle)
- **Source:** [GitHub repository](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin)
- **Support:** [GitHub Issues](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin/issues)

## Features

- Bind-aware `SELECT` and `WITH` queries with bounded JSON results.
- Oracle Text or parameterized, case-insensitive `LIKE` search.
- Cosine similarity over existing `VECTOR` columns.
- Weighted text-and-vector hybrid retrieval.

## Requirements and connection

- Declared minimum Dify target: 1.14.2. The exact v0.0.5 package has not yet been validated on that minimum version.
- Declared architecture targets: `amd64` and `arm64`. Exact-package validation on both remains a release gate.
- A reachable Oracle endpoint.
- A dedicated account with only the required `SELECT` privileges.
- An Oracle Text `CONTEXT` index when Oracle Text mode is enabled.
- Oracle `VECTOR` support for vector and hybrid search. Query and stored vectors must have the same dimension.

Dify Cloud requires a reachable endpoint. Private endpoints and wallet files normally require self-hosted Dify. Wallet paths must exist inside the runtime; wallet upload is not supported.

## Setup

1. Treat any v0.0.5 package built from this source as a local, unpublished release candidate. Validate its exact checksum in a clean Dify workspace before relying on it. The packaged incident workflow remains bound to v0.0.4 until it is deliberately rebound, rehearsed, and re-exported. Use Marketplace installation only after the public listing is verified.
2. Under **Plugins**, select **Knowledge Retrieval for Oracle Database** and **Authorize**.
3. Enter and validate the connection.

| Credential | Required | Description |
| --- | --- | --- |
| User / Password | Yes | Oracle credentials. |
| DSN | Conditional | For example `db.example.com:1521/FREEPDB1`. |
| Host / Service Name | Conditional | Both are needed without a DSN. |
| Port | No | Defaults to `1521`. |
| Config Directory | No | Runtime Oracle Net configuration directory. |
| Wallet Location / Password | No | Runtime wallet settings. |

Prefer TCPS or Oracle Native Network Encryption. Never package or commit credentials or wallets.

## Usage

| Tool | Configuration and input |
| --- | --- |
| `read_only_sql` | Configure `max_rows`; pass one query and optional named binds as JSON. |
| `external_knowledge_search` | Configure table, columns, text mode, and limit; pass search text. |
| `external_vector_search` | Configure table and columns; pass an embedding as a JSON number array. |
| `hybrid_knowledge_search` | Configure text/vector columns and weights; pass text and its embedding. |

Example:

```text
sql: SELECT ticket_id, title FROM support_tickets WHERE customer_id = :customer_id
bind_parameters: {"customer_id": 42}
max_rows: 100
```

Generate vectors upstream with the same dimension as stored vectors. See the [demo guide](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin/tree/main/demo) for a runnable schema and examples.

## Security and privacy

- SQL checks reject multiple statements, comments, DML, DDL, PL/SQL, `SELECT FOR UPDATE`, and `DBMS_*`. Permitted functions may still have side effects; least-privilege grants are the real boundary.
- Only simple, unquoted identifiers are supported. Results cap at 1,000 SQL rows, 100 search rows, and 16 KiB per LOB; caps do not limit query cost.
- Connections use 10-second connect and 110-second call timeouts. Returned error strings receive only best-effort exact-value redaction of configured connection fields. This does not sanitize SQL literals, bind values, returned rows, object names, or Dify workflow traces or logs.

The plugin sends credentials and inputs to the configured Oracle endpoint and returns results to Dify. It adds no telemetry or storage. See [PRIVACY.md](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin/blob/main/PRIVACY.md).

## Publishing status

Version 0.0.5 is a local release candidate, not a Marketplace release. Building a `.difypkg` does not establish clean-workspace compatibility, publication, or Dify verification. The next maintainer must complete the ordered engineering, privacy/IP, exact-package live validation, Marketplace PR, and post-publication steps in [MARKETPLACE_HANDOVER.md](MARKETPLACE_HANDOVER.md). Do not describe a local `.difypkg` as Marketplace availability.

Oracle and Oracle AI Database are trademarks of Oracle and/or its affiliates. This community plugin is not an official Oracle product and is not endorsed by Oracle.
