-- Verification queries for demo/setup_support_ops_demo.sql followed by
-- demo/seed_support_note_embeddings.py.
--
-- Run these as the same Oracle user used by the Dify Oracle AI Database plugin.

SET DEFINE OFF;
SET SERVEROUTPUT ON;

PROMPT a) Customers. Expected: 3 rows.
SELECT customer_id, customer_name, tier
FROM demo_customers
ORDER BY customer_id;

PROMPT b) Latest open Acme Bank tickets. Expected after vector seeding: tickets 1005, 1001, and 1002.
SELECT t.ticket_id, c.customer_name, t.title, t.severity, t.status
FROM demo_support_tickets t
JOIN demo_customers c ON c.customer_id = t.customer_id
WHERE c.customer_name = 'Acme Bank'
  AND t.status <> 'CLOSED'
ORDER BY t.created_at DESC;

PROMPT c) LIKE-mode note search. Expected: note 501.
SELECT id, title
FROM demo_support_notes
WHERE customer_name = 'Acme Bank'
  AND UPPER(body) LIKE '%VPN%'
  AND UPPER(body) LIKE '%PASSWORD%'
  AND UPPER(body) LIKE '%SYNC%';

PROMPT d) Open ticket counts by severity after vector seeding. Expected: P1 = 1, P2 = 3, P3 = 1.
SELECT severity, COUNT(*) AS open_ticket_count
FROM demo_support_tickets
WHERE status <> 'CLOSED'
GROUP BY severity
ORDER BY severity;

PROMPT e) Oracle Text search if DEMO_SUPPORT_NOTES_CTX_IDX exists. Expected: notes 501 and 504.
DECLARE
  index_count NUMBER;
  result_id NUMBER;
  result_title VARCHAR2(300);
  result_score NUMBER;
  result_cursor SYS_REFCURSOR;
BEGIN
  SELECT COUNT(*)
  INTO index_count
  FROM USER_INDEXES
  WHERE INDEX_NAME = 'DEMO_SUPPORT_NOTES_CTX_IDX';

  IF index_count = 0 THEN
    DBMS_OUTPUT.PUT_LINE(
      'Skipping Oracle Text verification because DEMO_SUPPORT_NOTES_CTX_IDX does not exist.'
    );
  ELSE
    OPEN result_cursor FOR
      'SELECT id, title, SCORE(1) AS search_score ' ||
      'FROM demo_support_notes ' ||
      'WHERE CONTAINS(body, ''VPN ACCUM password ACCUM synchronization'', 1) > 0 ' ||
      'ORDER BY SCORE(1) DESC';

    LOOP
      FETCH result_cursor INTO result_id, result_title, result_score;
      EXIT WHEN result_cursor%NOTFOUND;

      DBMS_OUTPUT.PUT_LINE(
        'ID=' || result_id
        || ', TITLE=' || result_title
        || ', SEARCH_SCORE=' || result_score
      );
    END LOOP;

    CLOSE result_cursor;
  END IF;
END;
/

-- If Oracle Text index exists, this should return notes 501 and 504:
-- SELECT id, title, SCORE(1) AS search_score
-- FROM demo_support_notes
-- WHERE CONTAINS(body, 'VPN ACCUM password ACCUM synchronization', 1) > 0
-- ORDER BY SCORE(1) DESC;

PROMPT f) Vector coverage after vector seeding. Expected: TOTAL_NOTES = 6, VECTORIZED_NOTES = 6.
SELECT COUNT(*) AS total_notes,
       SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) AS vectorized_notes
FROM demo_support_notes;
