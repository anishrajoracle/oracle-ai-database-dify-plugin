# Oracle Live Data Assistant Demo Dataset

This demo dataset is for the separate Dify Oracle AI Database plugin workstream.
It is not part of the in-tree OracleVector VDB adapter PRs.

The dataset gives the Dify workflow visible Oracle results for:

- `read_only_sql`
- `external_knowledge_search`
- `external_vector_search`
- `hybrid_knowledge_search`
- `write_only_sql`
- read-only safety rejection

## What It Creates

The seed script creates only demo tables prefixed with `DEMO_`:

- `DEMO_CUSTOMERS`
- `DEMO_SUPPORT_TICKETS`
- `DEMO_SUPPORT_NOTES`
- `DEMO_AGENT_ACTION_LOG`

`DEMO_SUPPORT_NOTES` includes a `VECTOR(768, FLOAT32)` embedding column for
the vector and hybrid-search tools. The dimension matches the default local
`nomic-embed-text` model.

It also creates useful indexes for the demo:

- `DEMO_SUPPORT_TICKETS_CUSTOMER_IDX`
- `DEMO_SUPPORT_TICKETS_STATUS_IDX`
- `DEMO_SUPPORT_NOTES_CUSTOMER_IDX`

If Oracle Text is available, it also tries to create:

- `DIFY_DEMO_WORLD_LEXER`
- `DEMO_SUPPORT_NOTES_CTX_IDX`

Oracle Text setup is best-effort. If the user lacks privileges or Oracle Text is not available, the script prints a message and continues. The read-only SQL and LIKE search demos still work.

## How To Run

Run the setup, vector seeder, and verification in that order. The final verification expects all six support notes to have embeddings, so do not run it immediately after the SQL setup.

For an isolated local demo, the simplest option is to use one disposable schema owner for setup, seeding, and plugin authorization. That account has DDL and Oracle Text package privileges and must not be reused as a production authorization. For a least-privilege rehearsal, have an administrator/schema owner run setup, grant the plugin user only required table `SELECT`/DML privileges, and create private synonyms in the plugin schema for the unqualified `DEMO_*` names. Conditional cross-schema updates/deletes may require target-table `SELECT` in Oracle 23ai. The write tool intentionally rejects schema-qualified targets.

With SQLcl:

```bash
sql user@host:1521/service @demo/setup_support_ops_demo.sql
uv run --env-file .env python demo/seed_support_note_embeddings.py
sql user@host:1521/service @demo/verify_support_ops_demo.sql
```

With SQL*Plus:

```bash
sqlplus user@host:1521/service @demo/setup_support_ops_demo.sql
uv run --env-file .env python demo/seed_support_note_embeddings.py
sqlplus user@host:1521/service @demo/verify_support_ops_demo.sql
```

Do not commit credentials, wallet files, `.env` files, or passwords.

Before running the Python seeder, run `uv sync --frozen --group dev`, copy `.env.example` to the ignored local `.env`, fill `ORACLE_USER`, `ORACLE_PASSWORD`, and `ORACLE_DSN`, and start Ollama with `nomic-embed-text`. The `uv run --env-file .env` command loads those values without putting the password in the shell command. The complete unified MVP workflow uses Oracle Text mode; use the documented LIKE fallback only for a reduced text-tool rehearsal.

## Expected Dify Workflow Prompts

### 1. Read-only SQL

Prompt:

```text
Show me the latest open tickets for Acme Bank.
```

Expected result:

- At least 3 non-closed tickets for Acme Bank after running the vector seeder.
- Ticket `1001`: `VPN login failure after password reset`
- Ticket `1002`: `Invoice webhook timeout`
- Ticket `1005`: `Remote access authentication state remains stale`

Suggested SQL for the tool:

```sql
SELECT t.ticket_id, c.customer_name, t.title, t.severity, t.status, t.product, t.created_at
FROM demo_support_tickets t
JOIN demo_customers c ON c.customer_id = t.customer_id
WHERE c.customer_name = :customer_name
  AND t.status <> 'CLOSED'
ORDER BY t.created_at DESC
```

Suggested bind parameters:

```json
{"customer_name":"Acme Bank"}
```

### 2. External Knowledge Search

Prompt:

```text
Search support notes for VPN password sync issues for Acme Bank.
```

Expected result:

- Note `501`, titled `VPN password sync issue`.
- The note body contains:

```text
VPN password sync identity synchronization cached credentials MFA enrollment
```

Oracle Text mode should work when `DEMO_SUPPORT_NOTES_CTX_IDX` exists.
LIKE mode should also work because the note body contains exact searchable words.

Suggested plugin settings:

```text
table_name: DEMO_SUPPORT_NOTES
text_column: BODY
id_column: ID
metadata_columns: TICKET_ID,CUSTOMER_NAME,TITLE,TAGS,CREATED_AT
use_oracle_text: true
max_rows: 5
```

For LIKE-mode fallback, set:

```text
use_oracle_text: false
```

### 3. Safety Demo

Prompt:

```text
Delete all closed tickets.
```

Expected result:

- The plugin rejects `DELETE` / DML.
- The demo has one closed ticket, `1004`, so it is clear what would have been deleted if the safety check did not exist.
- The separate write action is disabled by default and cannot reuse this model-generated SQL.

### 4. Configured Write Action

Enable write actions in a dedicated provider authorization, then configure the tool before giving it to the agent:

```text
sql: INSERT INTO DEMO_AGENT_ACTION_LOG (ACTION_ID, TICKET_ID, ACTION_TYPE, DETAILS) VALUES (:action_id, :ticket_id, :action_type, :details)
allowed_tables: DEMO_AGENT_ACTION_LOG
allow_delete: false
max_affected_rows: 1
```

Prompt:

```text
Record action 9001 for ticket 1001: FOLLOW_UP_REQUIRED, details "Verify identity sync and contact Acme Bank."
```

Add the exact payload contract to the agent/system instructions because Dify does not expose human-only form values such as the SQL template to the model:

```text
For the configured Oracle write action, pass bind_parameters as JSON with exactly:
action_id (integer), ticket_id (integer), action_type (string), and details (string).
Use it only when the user explicitly asks to record a support action.
```

Expected agent bind input:

```json
{"action_id":9001,"ticket_id":1001,"action_type":"FOLLOW_UP_REQUIRED","details":"Verify identity sync and contact Acme Bank."}
```

Expected result:

- One committed `INSERT` receipt with `affected_rows = 1`; no database row is returned by the write tool.
- A subsequent `read_only_sql` query can show action `9001`, making the persisted change visible.

For the rollback proof, configure a disposable second instance of the tool with:

```text
sql: UPDATE DEMO_SUPPORT_TICKETS SET STATUS = :status WHERE CUSTOMER_ID = :customer_id
allowed_tables: DEMO_SUPPORT_TICKETS
allow_delete: false
max_affected_rows: 1
```

Invoke it with `{"status":"REVIEW","customer_id":1}`. It matches multiple Acme Bank tickets, so the plugin must roll back and return an affected-row-limit error. Confirm with `read_only_sql` that their original statuses remain unchanged.

## Verification Queries

Run:

```bash
sql user@host:1521/service @demo/verify_support_ops_demo.sql
```

The verification file checks:

- 3 customers exist.
- Acme Bank has tickets `1001`, `1002`, and `1005` open after vector seeding.
- LIKE search finds note `501`.
- Open ticket counts are `P1 = 1`, `P2 = 3`, and `P3 = 1` after vector seeding.
- Oracle Text search finds the VPN and credential-sync notes if the text index exists.
- All 6 support notes have non-null vectors after vector seeding.
- The write-action log is empty immediately after setup; the configured write demo adds action `9001`.

## Seed Vector And Hybrid Search Data

After running the SQL setup, start Ollama with `nomic-embed-text` installed and
export the Oracle connection variables used by the plugin. Then run:

```bash
uv sync --frozen --group dev
uv run --env-file .env python demo/seed_support_note_embeddings.py
```

The seeder is safe to rerun. It adds two tickets and three support notes,
generates embeddings for every support note, synchronizes the Oracle Text
index, and verifies exact and semantic search. Credentials and wallet files
are read from the environment and must not be committed.
