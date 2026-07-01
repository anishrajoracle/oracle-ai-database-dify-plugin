# Oracle Live Data Assistant Demo Dataset

This demo dataset is for the separate Dify Oracle AI Database plugin workstream.
It is not part of the in-tree OracleVector VDB adapter PRs.

The dataset gives the Dify workflow visible Oracle results for:

- `read_only_sql`
- `external_knowledge_search`
- `external_vector_search`
- `hybrid_knowledge_search`
- read-only safety rejection

## What It Creates

The seed script creates only demo tables prefixed with `DEMO_`:

- `DEMO_CUSTOMERS`
- `DEMO_SUPPORT_TICKETS`
- `DEMO_SUPPORT_NOTES`

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

Run the setup as the same Oracle user configured in the Dify plugin connection.

With SQLcl:

```bash
sql user/password@host:1521/service @demo/setup_support_ops_demo.sql
sql user/password@host:1521/service @demo/verify_support_ops_demo.sql
```

With SQL*Plus:

```bash
sqlplus user/password@host:1521/service @demo/setup_support_ops_demo.sql
sqlplus user/password@host:1521/service @demo/verify_support_ops_demo.sql
```

Do not commit credentials, wallet files, `.env` files, or passwords.

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

## Verification Queries

Run:

```bash
sql user/password@host:1521/service @demo/verify_support_ops_demo.sql
```

The verification file checks:

- 3 customers exist.
- Acme Bank has tickets `1001`, `1002`, and `1005` open after vector seeding.
- LIKE search finds note `501`.
- Open ticket counts are `P1 = 1`, `P2 = 3`, and `P3 = 1` after vector seeding.
- Oracle Text search finds the VPN and credential-sync notes if the text index exists.
- All 6 support notes have non-null vectors after vector seeding.

## Seed Vector And Hybrid Search Data

After running the SQL setup, start Ollama with `nomic-embed-text` installed and
export the Oracle connection variables used by the plugin. Then run:

```bash
python demo/seed_support_note_embeddings.py
```

The seeder is safe to rerun. It adds two tickets and three support notes,
generates embeddings for every support note, synchronizes the Oracle Text
index, and verifies exact and semantic search. Credentials and wallet files
are read from the environment and must not be committed.
