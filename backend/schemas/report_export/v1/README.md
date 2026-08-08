# SentinelScan Report Export Schema -- v1

Status: **DRAFT, awaiting approval.** Nothing in Stage 3's ingestion
pipeline has been implemented against this yet -- this directory is the
proposed contract only.

## Why this exists

Stage 3 needs a JSON Schema to validate incoming reports against before
anything is persisted (Section 15: a Report is always treated as inert
data; Section 11 step 3-4: schema validation and source-edition
detection happen before normalization). No official schema existed yet,
so this was designed bottom-up from what SentinelScan Cloud's own
domain models (Report, Asset, Finding, ReportAsset --
`src/sentinelscan_cloud/domain/`) already commit to persisting, plus
what Section 12 (Correlation, Risk Scoring, Prioritization, Threat
Reference Correlation) implies the ingested data needs to contain to
support those modules later.

**This means real assumptions were made without a source spec to check
them against.** They're called out explicitly in "Open questions"
below -- please treat that section as the actual thing to review, more
than the JSON Schema syntax itself.

## Files

```
v1/
  common.schema.json      -- shared envelope + Asset/Finding $defs, used by both editions
  discover.schema.json    -- SentinelScan Discover profile (references common.schema.json)
  operate.schema.json     -- SentinelScan Operate profile (references common.schema.json)
  examples/
    discover_example.json -- a minimal but complete valid Discover export
    operate_example.json  -- a minimal but complete valid Operate export
```

## Design decisions

### 1. One shared payload shape at v1, not two structurally different ones

Discover and Operate produce the *same* envelope/Asset/Finding shape in
this proposal -- `discover.schema.json` and `operate.schema.json` are
thin wrappers that just pin `source_edition` and `producer.product` to
a const and pull every real field definition from `common.schema.json`.

This was a judgment call made in the absence of real examples of either
product's actual export format. If Discover and Operate genuinely
produce structurally different data (e.g. Operate findings are
event-timestamped individually with no single "scan window" the way a
Discover sweep has), that's a real structural difference this draft
doesn't capture and the two schemas should diverge for real. **Please
confirm or correct this.**

### 2. Open `extensions` / `evidence` bags as the forward-compatibility valve

The envelope, Asset, and Finding shapes are otherwise closed
(`additionalProperties: false`) -- an unrecognized top-level field is a
validation failure, not silently ignored, because the envelope is a
hard contract Section 3-4's schema validation step is supposed to
enforce.

Inside `Asset.extensions` and `Finding.evidence`, though,
`additionalProperties: true` deliberately. Producer-specific or
not-yet-formalized data (open ports, OS fingerprint, CVE IDs, log
excerpts, runtime/container context, whatever either product actually
emits) goes there. Stage 3's schema validation passes it through
without inspecting it; nothing downstream trusts or executes it
(Section 15 -- a Report is inert data, and that applies inside these
bags too, not just at the top level).

### 3. `schema_version` and how Cloud is meant to pick a schema

`schema_version` is a `"MAJOR.MINOR"` string. The proposed contract:

* A MINOR bump is only ever additive (new optional field) -- old
  payloads stay valid against a newer schema, and Stage 3 doesn't need
  a new schema file for it.
* A MAJOR bump means a real breaking change -- a new schema file
  (`v2/`), and Stage 3 has to explicitly add support for it. An
  unrecognized major version should be rejected with a clear "unsupported
  schema_version" error, not silently coerced.

Stage 3 (not yet implemented) would look at `(source_edition,
schema_version)` to choose which schema file to validate the payload
against.

### 4. Field length limits mirror existing DB columns, and are enforced as rejections, not silent truncation

`Finding.title` is capped at the schema level to match
`Finding.title`'s `String(500)` column, `Asset.identifier` /
`Asset.display_name` at 255 to match their columns, etc. A payload that
exceeds these is proposed to be **rejected outright** at schema
validation (Section 15's stance on never silently mutating untrusted
input), not truncated to fit. **Please confirm silent truncation isn't
actually what's wanted instead** -- it would be a real product/UX
decision, not just a validation nicety.

`Finding.description` has no DB-side length limit (`Text` column), so
the schema proposes a generous sanity cap (100,000 characters) purely
as a DoS/malformed-input guard, not a real product limit. Open to being
wrong.

### 5. Asset identity is a single opaque `identifier` string, matching today's Asset model

`Asset.identifier` in the current domain model is a plain string with
no separate "this is an IP vs a hostname" column, and asset
reconciliation in Stage 3 (not yet implemented) will need to match
Assets across reports by this value. The schema requires producers to
also send `identifier_type` (`ip_v4` / `ip_v6` / `hostname` / `fqdn`),
which is **not** persisted anywhere in Cloud's current schema -- it's
there so Stage 3's normalization/reconciliation engine can apply the
right canonicalization rule (e.g. lowercase hostnames, canonical IPv6
textual form) *before* comparing identifiers, rather than comparing
raw, inconsistently-cased strings. Whether `identifier_type` should
also become a real persisted column on `Asset` is a Stage 3 design
question, not decided here.

### 6. `asset_ref` / `finding_ref` are producer-local, not Cloud primary keys

Findings reference Assets within one export via a report-local
`asset_ref` string (Assets are listed once, Findings point at them by
ref, avoiding a repeated inline Asset object per Finding). Both
`asset_ref` and `finding_ref` are scoped to a single export only --
Cloud generates its own UUID primary keys on ingest per the existing
`Report`/`Asset`/`Finding` models, which have no column to store a
producer-side ref today. If per-finding traceability back to "which
line in the original scanner output produced this" is wanted as a
persisted, queryable thing (not just present in the archived raw blob
via `Report.raw_blob_storage_key`), that's a new nullable column and a
new migration -- flagging it here rather than adding it unasked.

### 7. Finding correlation fingerprint is deliberately NOT part of this schema

Section 12.1 (Correlation: new / resolved / recurring) needs a way to
recognize "this is the same finding as one seen in a prior report for
this Asset." This draft does **not** ask producers to supply a stable
finding ID/fingerprint, and proposes Cloud computes its own fingerprint
in Stage 3 (e.g. from asset identity + normalized title + signature),
never trusting a producer-supplied ID as the correlation key --
consistent with Reports being treated as inert, unverified input
(Section 15), and avoiding two different scanners' ID schemes silently
colliding or drifting. `Finding.signature` (service / version /
configuration_pattern) is included because `ThreatReferenceEntry`
already has a `signature` column it needs to match against (Section
12.5), which is a different thing from a correlation fingerprint.
**This is a central Stage 3 design decision and is called out here
specifically for confirmation before any reconciliation code is
written.**

### 8. CVE IDs are a shared, optional field -- not Discover-only

`Finding.cve_ids` (array of `CVE-YYYY-NNNN+`-pattern strings) is
included in the shared schema rather than siloed into a
Discover-specific extension, on the assumption CVE identifiers are
valuable to correlate on regardless of which product reported them,
and Operate could plausibly report a CVE tied to a running service too.
If that's wrong for Operate, this is trivial to move into an
edition-specific extension instead.

## Open questions requiring explicit confirmation before Stage 3 uses this

1. Do Discover and Operate actually differ structurally, or is "one
   shared shape, edition-specific quirks live in `extensions`/`evidence`"
   the right v1 model?
2. Is silent truncation ever acceptable for oversized fields, or should
   an oversized field always be a hard validation rejection (this
   draft's assumption)?
3. Should `identifier_type` become a real persisted `Asset` column
   (new migration), or stay validation-only metadata that's discarded
   after normalization?
4. Should producer-local `asset_ref`/`finding_ref` be persisted for
   traceability (new nullable columns), or is the archived raw blob
   (`Report.raw_blob_storage_key`) sufficient for that already?
5. Confirm: Cloud computes its own Finding correlation fingerprint in
   Stage 3 and never trusts a producer-supplied finding ID for that
   purpose.
6. Are CVE IDs relevant to Operate findings, or Discover-only?
