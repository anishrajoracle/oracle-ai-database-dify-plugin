# Dify Marketplace Publication Handover

This is the ordered owner checklist for taking the **Knowledge Retrieval for Oracle Database** v0.0.5 source release candidate to an approved Dify Marketplace listing.

Marketplace publication is not part of the completed MVP. Do not describe the plugin as Marketplace-published, Dify-verified, Oracle-verified, signed, or production-certified until the corresponding approval is recorded.

## Current handover state

- Source repository: `https://github.com/anishrajoracle/oracle-ai-database-dify-plugin`
- Current release line: `main`, version `0.0.5`
- Latest frozen local package: v0.0.4 from source snapshot `b41e852154c585299f48eaef681e9296356224ea`
- v0.0.4 provenance check: every one of the 26 files in its handover `.difypkg` matches that commit byte-for-byte
- v0.0.4 file SHA-256: `b8d3f5a21dddd7ae4abca8eaa5cefefb56be51d166a14ffc5d4d8733ee22b873`
- v0.0.4 Dify content checksum: `0b093d4f477d980a4605c0479a879607c62586a9befd599ca496a16d741c9775`
- v0.0.5 package status: not built; GitHub Plugin CI is enabled and passing on `main`
- Plugin identity: `anishrajoracle/oracle_ai_database`
- Distribution status: local package only; `verified: false`
- Core tools: read-only SQL, Oracle Text search, Oracle VECTOR search, and hybrid search
- Existing strengths: English README, non-empty `PRIVACY.md`, custom icon, pinned SDK/dependencies, bounded outputs, credential redaction, timeouts, unit tests, and a deterministic demo workflow
- Remaining release blockers: final publisher/brand decision, license selection, tag/release creation, exact-package live validation, final security/privacy review, and Marketplace PR review

## Publication steps — perform in this order

### 1. Accept ownership and record the publishing identity

Assign one primary maintainer and one backup. Record their GitHub usernames, support channel, expected response time, and the date ownership was accepted.

Decide whether the Marketplace publisher will remain the community identity `anishrajoracle` or use an approved Oracle organization/publisher identity. If the submission will imply Oracle sponsorship or verification, obtain Oracle open-source, legal, trademark/brand, security, and privacy approval first. Do not use an Oracle logo or claim official endorsement without written authorization.

Exit criterion: the publisher identity, primary owner, backup owner, and support channel are written in the owner record below.

### 2. Freeze one release candidate

Start from a clean branch based on the intended `main` commit. Resolve or exclude unrelated working-tree changes. Add the approved repository license, retain a monitored support link, and record the exact commit to be packaged.

Do not change source, manifest, dependencies, README, privacy text, or packaged assets after the release candidate is frozen without restarting the package-and-validation steps.

Exit criterion: `git status` is clean and the owner record contains one immutable commit SHA.

### 3. Close the remaining engineering gaps

Before requesting public distribution:

- [x] Make `ruff format --check .` pass.
- [x] Reject `NaN` and infinity in weights and vectors with `math.isfinite()` tests.
- [x] Run the full unit suite and retain its output in GitHub Actions.
- Run remote debugging or an equivalent real plugin-daemon session against Oracle.
- Exercise all four tools, the expected DML rejection, credential redaction, timeout behavior, Oracle Text mode, 768-dimensional VECTOR mode, and 0.7/0.3 hybrid mode.
- Test the minimum declared Dify version and both declared architectures where practical.
- Confirm result limits bound output and document that they do not bound database work.

Exit criterion: a dated validation record identifies the Dify version, daemon version, Oracle version, architecture, commit, and observed result for every tool.

### 4. Complete repository, privacy, and intellectual-property review

Confirm that:

- `manifest.yaml`, `README.md`, `PRIVACY.md`, and `_assets/` are present.
- README setup, required credentials, networking constraints, wallet limitations, usage, support, and known limitations match tested behavior.
- Every user-facing label, description, help string, error message, PR title, and PR body is English.
- `PRIVACY.md` declares what query text, embeddings, credentials, connection data, and returned database data are processed; where they go; whether anything is stored or logged; and what third parties receive.
- The privacy declaration covers the configured Oracle endpoint and any service the plugin itself calls. The current plugin adds no telemetry, but the deployment owner remains responsible for Oracle-side logging, retention, and access control.
- No credentials, wallets, private endpoints, production data, or real user data appear in Git, fixtures, screenshots, logs, or the package.
- The plugin name and icon are unique, accurate, sharp, and legally approved. Do not use Dify logos or unapproved Oracle artwork.

Exit criterion: the designated security/privacy reviewer and brand/IP reviewer have signed off in the owner record.

### 5. Confirm Marketplace uniqueness and version availability

Search both `https://marketplace.dify.ai` and `https://github.com/langgenius/dify-plugins` for the plugin identity, display name, and equivalent Oracle database tools.

Explain the unique value in the future PR: one read-only plugin combines relational SQL, Oracle Text, existing Oracle VECTOR rows, and weighted hybrid retrieval while keeping credentials in Dify provider authorization.

Confirm that version `0.0.5` has never been published for this plugin identity. If it has, bump the manifest version and document a meaningful change; Marketplace updates cannot reuse an existing version.

Exit criterion: the PR draft records the uniqueness search date and confirms the version is new.

### 6. Run the Marketplace mechanical preflight

Run and retain evidence for:

```bash
uv lock --check
uv sync --frozen
python -m pytest -q
ruff check .
ruff format --check .
python -m compileall main.py oracle_ai_database provider tools
pip install -r requirements.txt
```

Also confirm:

- The plugin SDK requirement is at least `dify_plugin>=0.5.0`.
- `author` contains neither `langgenius` nor `dify`.
- The version is new.
- README contains no Chinese characters; translations, if added, belong under `readme/README_<lang>.md`.
- `PRIVACY.md` is non-empty.
- The icon is a real non-template asset under `_assets/`.
- The current plugin daemon can install and repackage the plugin.

Exit criterion: all twelve Dify mechanical review categories have a passing result in the preflight record.

### 7. Package once from the frozen commit

From the directory above the plugin project, run:

```bash
dify plugin package ./oracle-ai-database-dify-plugin
```

Retain exactly one submission `.difypkg`. Record:

- semantic version;
- source commit;
- file SHA-256;
- Dify package checksum/unique identifier;
- package filename;
- build date and CLI/daemon version.

Do not substitute an older file that happens to have the same semantic version.

Exit criterion: one package maps unambiguously to one clean commit and one checksum record.

### 8. Validate the exact package in a clean Dify workspace

Install the package produced in Step 7, configure Oracle authorization, and import/rebind the unified MVP workflow. Run the Knowledge path, all four tools, and the DML rejection proof. Capture non-secret screenshots or logs showing actual status, row counts, modes, vector dimensions, note/ticket IDs, and hybrid scores.

Re-export the workflow after installing the final package so its dependency identifier matches the submission package. Never edit the package or source after this run without rebuilding and repeating validation.

Exit criterion: the exact packaged artifact completes the rehearsed workflow and its evidence bundle contains no secrets or production data.

### 9. Create the source release record

Create a signed or annotated `v0.0.5` tag and a GitHub release for the frozen source commit. Attach the same `.difypkg`, its SHA-256, release notes, compatibility information, known limitations, and support link.

This source release is not the Marketplace publication itself; it provides provenance and a recovery point.

Exit criterion: tag, release, package, commit, and checksum all agree.

### 10. Prepare the `langgenius/dify-plugins` submission

Fork `https://github.com/langgenius/dify-plugins`. Create:

```text
<approved-author>/<plugin-name>/
```

For a new plugin, add the plugin source and the single packaged `.difypkg` in that directory, following the repository's current layout and PR template. Do not include stale packages, demo recordings, credentials, wallets, caches, or unrelated project files.

Exit criterion: the fork contains one reviewable plugin directory and exactly one new submission package.

### 11. Open and shepherd the Marketplace pull request

Open an English PR against `langgenius/dify-plugins:main`. Use the current PR template and include:

- problem and unique value;
- plugin type and four-tool scope;
- publisher identity and source repository;
- tested Dify, daemon, Python, architecture, and Oracle versions;
- privacy/data-flow summary;
- security and least-privilege summary;
- package filename, source commit, SHA-256, and Dify checksum;
- live-validation evidence and non-secret screenshots;
- known limitations and support channel.

The automated review checks for one `.difypkg`, English PR text, required project files, valid author/icon/version, English README, non-empty privacy policy, dependency installation, SDK version, daemon installation, and clean repackaging. Fix failures by updating source, bumping the package evidence, rebuilding, and pushing new commits. Human review follows the automated checks.

Exit criterion: every automated check passes and all human-review conversations are resolved.

### 12. Verify publication and establish maintenance

After the PR merges, Dify publishes the plugin automatically; there is no separate Marketplace upload step. Verify the public listing and install it from Marketplace into a clean workspace. Re-run authorization and one smoke test per tool.

Record the Marketplace URL, published version, publication date, owner, support channel, and smoke-test result. Monitor issues and Dify compatibility changes. For each later release, bump the manifest version, document breaking changes, repackage, and open a new Marketplace PR. Consider Dify's automated publish-PR workflow only after the manual process is stable.

Exit criterion: the Marketplace listing is public, a clean one-click install works, all four tools pass smoke tests, and ongoing ownership is documented.

## Owner and approval record

Fill this in before opening the Marketplace PR:

```text
Primary maintainer:
Backup maintainer:
Approved publisher/author identity:
Support URL or email:
Expected support response time:
Frozen source commit:
Manifest version:
Package filename:
Package SHA-256:
Dify package checksum:
Dify version tested:
Plugin daemon/CLI version tested:
Oracle version/environment tested:
Architectures tested:
Security/privacy reviewer and date:
Brand/IP reviewer and date:
Oracle open-source/legal approval reference, if applicable:
Marketplace PR URL:
Marketplace listing URL:
Publication smoke-test date/result:
```

## Official references

- Dify Marketplace publication process: `https://docs.dify.ai/en/develop-plugin/publishing/marketplace-listing/release-to-dify-marketplace`
- Dify Plugin Development Guidelines: `https://docs.dify.ai/en/develop-plugin/publishing/standards/contributor-covenant-code-of-conduct`
- Dify Privacy Guidelines: `https://docs.dify.ai/en/develop-plugin/publishing/standards/privacy-protection-guidelines`
- Marketplace repository: `https://github.com/langgenius/dify-plugins`
- Marketplace: `https://marketplace.dify.ai`

Re-check these pages immediately before submission because Marketplace rules and repository automation can change.
