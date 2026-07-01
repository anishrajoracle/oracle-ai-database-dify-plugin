# Privacy Policy

Last updated: July 2, 2026

This policy describes the data handled by the Knowledge Retrieval for Oracle Database plugin for Dify.

## Data processed

The plugin processes the following data only to provide its tools:

- Oracle connection settings: database user, password, DSN or host/port/service name, and optional wallet paths and wallet password.
- Tool configuration and inputs: SQL, bind values, search text, table and column names, query vectors, result limits, and hybrid-search weights.
- Oracle responses: column metadata, result rows, search scores, row counts, and database error diagnostics.

These values may contain personal, confidential, financial, health, authentication, or other sensitive information depending on the connected database and the workflow inputs.

## Purpose and data flow

At invocation time, Dify supplies the configured provider credentials and tool inputs to the plugin. The plugin uses them to open a connection to the Oracle database endpoint selected by the workspace user, execute the requested read operation, and return the result or a redacted error to Dify.

The plugin does not send data to an author-operated service, advertising service, analytics service, or any endpoint other than the configured Oracle database. Data is also processed by the Dify deployment running the plugin; Dify Cloud users should review the [Dify Privacy Policy](https://dify.ai/privacy), and self-hosted users should review their deployment operator's policy. If the database is hosted by Oracle Cloud or another provider, that provider processes the connection and query data under its own terms. Oracle's services privacy policy is available at [oracle.com/legal/privacy/services-privacy-policy.html](https://www.oracle.com/legal/privacy/services-privacy-policy.html).

## Storage, logging, and retention

The plugin has no persistent data store, creates no user profile, and adds no telemetry. Connection settings, inputs, and results are held only as needed for an invocation. Configured secrets are redacted from errors returned by the plugin.

Dify may store provider credentials and retain workflow inputs, outputs, or logs according to the Dify deployment's configuration and policies. The connected Oracle database or its hosting provider may independently audit or log connections and SQL. Those systems, not this plugin, control that retention. Users should use the relevant Dify and Oracle administration tools to review or delete retained data.

## Security responsibilities

- Use a dedicated, least-privileged Oracle account with only the required `SELECT` grants. The plugin's SQL checks do not replace database authorization.
- Use TCPS, Oracle Native Network Encryption, or another deployment-appropriate encrypted connection. Transport encryption depends on the supplied DSN, wallet, and database configuration; the plugin does not force TLS.
- Ensure the Dify runtime is authorized to reach the database. Wallet files and configuration directories must be mounted into a self-hosted plugin runtime and must never be included in a plugin package or source repository.
- Limit access to Dify workflows because returned rows and Oracle diagnostics may contain sensitive information.

## Deletion and data requests

The plugin maintains no separate data store for the author to delete. Remove its provider credentials or uninstall the plugin to stop future processing. Contact the Dify deployment operator regarding Dify-held configuration or logs and the database operator regarding database or audit data.

## Changes and contact

Material changes to this policy will be published in the source repository with the plugin update. Questions and privacy requests can be submitted through [GitHub Issues](https://github.com/anishrajoracle/oracle-ai-database-dify-plugin/issues). Do not include credentials, SQL bind values, query results, or personal data in an issue.
