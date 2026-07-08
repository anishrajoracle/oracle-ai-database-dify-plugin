-- Oracle Live Data Assistant demo seed data.
--
-- Run this as the same Oracle user configured in the Dify Oracle AI Database
-- plugin authorization. The script is safe to rerun: it drops and recreates
-- only DEMO_* objects used by the plugin demo.

SET DEFINE OFF;
SET SERVEROUTPUT ON;

PROMPT Resetting Oracle Live Data Assistant demo objects...

BEGIN
  EXECUTE IMMEDIATE 'DROP INDEX DEMO_SUPPORT_NOTES_CTX_IDX';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -1418 THEN
      DBMS_OUTPUT.PUT_LINE('Skipping index drop; continuing demo setup.');
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE DEMO_SUPPORT_NOTES PURGE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -942 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE DEMO_SUPPORT_TICKETS PURGE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -942 THEN
      RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'DROP TABLE DEMO_CUSTOMERS PURGE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE != -942 THEN
      RAISE;
    END IF;
END;
/

CREATE TABLE DEMO_CUSTOMERS (
  CUSTOMER_ID NUMBER PRIMARY KEY,
  CUSTOMER_NAME VARCHAR2(200) NOT NULL,
  INDUSTRY VARCHAR2(100),
  REGION VARCHAR2(100),
  TIER VARCHAR2(50)
);

CREATE TABLE DEMO_SUPPORT_TICKETS (
  TICKET_ID NUMBER PRIMARY KEY,
  CUSTOMER_ID NUMBER NOT NULL REFERENCES DEMO_CUSTOMERS(CUSTOMER_ID),
  TITLE VARCHAR2(300) NOT NULL,
  SEVERITY VARCHAR2(20),
  STATUS VARCHAR2(30),
  PRODUCT VARCHAR2(100),
  CREATED_AT DATE,
  SUMMARY VARCHAR2(1000)
);

CREATE TABLE DEMO_SUPPORT_NOTES (
  ID NUMBER PRIMARY KEY,
  TICKET_ID NUMBER,
  CUSTOMER_NAME VARCHAR2(200),
  TITLE VARCHAR2(300),
  BODY CLOB,
  TAGS VARCHAR2(300),
  CREATED_AT DATE,
  EMBEDDING VECTOR(768, FLOAT32)
);

INSERT INTO DEMO_CUSTOMERS (
  CUSTOMER_ID,
  CUSTOMER_NAME,
  INDUSTRY,
  REGION,
  TIER
) VALUES (
  1,
  'Acme Bank',
  'Financial Services',
  'North America',
  'Enterprise'
);

INSERT INTO DEMO_CUSTOMERS (
  CUSTOMER_ID,
  CUSTOMER_NAME,
  INDUSTRY,
  REGION,
  TIER
) VALUES (
  2,
  'Globex Retail',
  'Retail',
  'EMEA',
  'Business'
);

INSERT INTO DEMO_CUSTOMERS (
  CUSTOMER_ID,
  CUSTOMER_NAME,
  INDUSTRY,
  REGION,
  TIER
) VALUES (
  3,
  'Northwind Health',
  'Healthcare',
  'North America',
  'Enterprise'
);

INSERT INTO DEMO_SUPPORT_TICKETS (
  TICKET_ID,
  CUSTOMER_ID,
  TITLE,
  SEVERITY,
  STATUS,
  PRODUCT,
  CREATED_AT,
  SUMMARY
) VALUES (
  1001,
  1,
  'VPN login failure after password reset',
  'P2',
  'OPEN',
  'Identity',
  DATE '2025-02-11',
  'Acme Bank users who recently changed passwords are unable to connect to VPN until identity synchronization completes.'
);

INSERT INTO DEMO_SUPPORT_TICKETS (
  TICKET_ID,
  CUSTOMER_ID,
  TITLE,
  SEVERITY,
  STATUS,
  PRODUCT,
  CREATED_AT,
  SUMMARY
) VALUES (
  1002,
  1,
  'Invoice webhook timeout',
  'P3',
  'OPEN',
  'Integration',
  DATE '2025-02-08',
  'Invoice events are timing out while the integration endpoint is under high latency.'
);

INSERT INTO DEMO_SUPPORT_TICKETS (
  TICKET_ID,
  CUSTOMER_ID,
  TITLE,
  SEVERITY,
  STATUS,
  PRODUCT,
  CREATED_AT,
  SUMMARY
) VALUES (
  1003,
  2,
  'MFA device lost',
  'P2',
  'IN_PROGRESS',
  'Identity',
  DATE '2025-02-07',
  'Globex Retail needs an MFA enrollment reset after a user lost their registered device.'
);

INSERT INTO DEMO_SUPPORT_TICKETS (
  TICKET_ID,
  CUSTOMER_ID,
  TITLE,
  SEVERITY,
  STATUS,
  PRODUCT,
  CREATED_AT,
  SUMMARY
) VALUES (
  1004,
  3,
  'Database upgrade validation',
  'P3',
  'CLOSED',
  'Database',
  DATE '2025-02-01',
  'Northwind Health completed database upgrade validation and closed the support request.'
);

INSERT INTO DEMO_SUPPORT_NOTES (
  ID,
  TICKET_ID,
  CUSTOMER_NAME,
  TITLE,
  BODY,
  TAGS,
  CREATED_AT
) VALUES (
  501,
  1001,
  'Acme Bank',
  'VPN password sync issue',
  'VPN password sync identity synchronization cached credentials MFA enrollment. Users who recently changed their password may be unable to connect to VPN until identity synchronization completes. The support team should refresh cached credentials, verify MFA enrollment status, and retry after the sync window. This row is intentionally worded so both Oracle Text mode and LIKE mode can find VPN, password, and sync for Acme Bank.',
  'vpn,password-sync,identity,mfa,acme-bank',
  DATE '2025-02-11'
);

INSERT INTO DEMO_SUPPORT_NOTES (
  ID,
  TICKET_ID,
  CUSTOMER_NAME,
  TITLE,
  BODY,
  TAGS,
  CREATED_AT
) VALUES (
  502,
  1002,
  'Acme Bank',
  'Webhook retry timeout',
  'webhook timeout retry policy endpoint latency integration logs. Acme Bank invoice callbacks are delayed because the customer endpoint latency is above the retry policy threshold. Review integration logs, increase retry spacing if needed, and confirm that duplicate webhook events are idempotent.',
  'webhook,timeout,integration,acme-bank',
  DATE '2025-02-08'
);

INSERT INTO DEMO_SUPPORT_NOTES (
  ID,
  TICKET_ID,
  CUSTOMER_NAME,
  TITLE,
  BODY,
  TAGS,
  CREATED_AT
) VALUES (
  503,
  1003,
  'Globex Retail',
  'MFA enrollment reset',
  'MFA enrollment lost device identity verification revoke old device. Globex Retail needs help resetting a lost MFA device. The operator should verify identity, revoke the old device, and start a new MFA enrollment flow.',
  'mfa,lost-device,identity,globex-retail',
  DATE '2025-02-07'
);

CREATE INDEX DEMO_SUPPORT_TICKETS_CUSTOMER_IDX
ON DEMO_SUPPORT_TICKETS(CUSTOMER_ID);

CREATE INDEX DEMO_SUPPORT_TICKETS_STATUS_IDX
ON DEMO_SUPPORT_TICKETS(STATUS);

CREATE INDEX DEMO_SUPPORT_NOTES_CUSTOMER_IDX
ON DEMO_SUPPORT_NOTES(CUSTOMER_NAME);

PROMPT Creating Oracle Text preference and index if available...

BEGIN
  BEGIN
    CTX_DDL.DROP_PREFERENCE('DIFY_DEMO_WORLD_LEXER');
  EXCEPTION
    WHEN OTHERS THEN
      NULL;
  END;

  CTX_DDL.CREATE_PREFERENCE('DIFY_DEMO_WORLD_LEXER', 'WORLD_LEXER');
  DBMS_OUTPUT.PUT_LINE('Created Oracle Text lexer preference DIFY_DEMO_WORLD_LEXER.');
EXCEPTION
  WHEN OTHERS THEN
    DBMS_OUTPUT.PUT_LINE(
      'Oracle Text lexer preference was not created. '
      || 'The demo can still use read_only_sql and LIKE search.'
    );
END;
/

BEGIN
  EXECUTE IMMEDIATE
    'CREATE INDEX DEMO_SUPPORT_NOTES_CTX_IDX ' ||
    'ON DEMO_SUPPORT_NOTES(BODY) ' ||
    'INDEXTYPE IS CTXSYS.CONTEXT ' ||
    'PARAMETERS (''LEXER DIFY_DEMO_WORLD_LEXER SYNC (ON COMMIT)'')';

  DBMS_OUTPUT.PUT_LINE('Created Oracle Text index DEMO_SUPPORT_NOTES_CTX_IDX.');
EXCEPTION
  WHEN OTHERS THEN
    DBMS_OUTPUT.PUT_LINE(
      'Oracle Text index was not created. '
      || 'The demo can still use read_only_sql and LIKE search.'
    );
END;
/

COMMIT;

PROMPT Oracle Live Data Assistant demo seed complete.
PROMPT Run demo/verify_support_ops_demo.sql to verify expected rows.
