# PR0161A — Standard Result Technical Debt Register

This file records the concrete contract debt observed in production on 2026-09-17.

It is documentation only. No behavior is changed in PR0161A.

## TD-0161-01 — `scan_date_time` representation violates/underspecifies Contract v1

### Existing contract

Standard Model Result Contract v1 states:

- timestamps are RFC3339-compatible;
- timezone information is present;
- fractional seconds are omitted;
- the mapper may normalize representation;
- the mapper must not invent missing acquisition times or change timestamp meaning.

### Observed production evidence

Bremen job/source metadata:

```json
{
  "scan_date_time": "2025-05-28 10:19:55"
}
```

Bremen Standard Result:

```json
{
  "scan_date_time": "2025-05-28T10:19:55"
}
```

Aramina Standard Result:

```json
{
  "scan_date_time": "2025-05-14T12:55:46+00:00"
}
```

### Problems

1. separator normalization is occurring (` ` -> `T`) in at least one path;
2. Bremen has no timezone offset in the public Standard Result;
3. Aramina is offset-aware;
4. attaching UTC to Bremen solely to satisfy the schema would fabricate semantics unless the source/package can prove UTC;
5. the common contract therefore needs a truthful rule for timezone-unavailable source metadata.

### Required resolution

PR0161 must define one deterministic contract and implementation for both workflows.

It must distinguish:
- syntactic normalization;
- authoritative timezone enrichment;
- unknown timezone.

Do not silently invent timezone information.

## TD-0161-02 — failed workflow report loses safe diagnostics

### Observed production evidence

Successful report shapes:

- Bremen success: 63 scalar values, `payload` present, `standard_result` present;
- Aramina success: 38 scalar values, `payload` present, `standard_result` present.

Failed report endpoint shape:

- 6 scalar values;
- no `payload`;
- no `standard_result`;
- `report.status = "unavailable"`;
- `report.reason_code = "REPORT_NOT_AVAILABLE"`.

At the same time `GET /api/jobs/{job_id}` contains useful safe structured failure data such as:

- workflow status;
- failure;
- failure stage;
- failure reason code;
- remediation;
- allowlisted preprocessing diagnostics for Aramina.

### Problem

A report client must fall back to job-detail-specific knowledge to explain a failed analysis.

The workflow report endpoint does not provide a useful normalized failure contract.

### Required resolution

Define an additive normalized failure-report envelope shared by Bremen and Aramina.

It should contain only safe public fields and must not expose:

- raw exceptions;
- tracebacks;
- local paths;
- S3 bucket/key;
- tokens;
- model package internals;
- checksums unless explicitly part of a public contract.

Backward compatibility with existing `REPORT_NOT_AVAILABLE` handling must be considered.

## TD-0161-03 — missing metadata representation is inconsistent

### Observed examples

```json
{
  "eoscan_version": null
}
```

and:

```json
{
  "mammography_suspicious_field": ""
}
```

Historical Standard Result paths also used empty strings for unavailable string metadata.

### Problem

The schema does not currently make the field-level `null` vs `""` policy sufficiently explicit.

That can force clients to implement model-specific missing-value handling.

### Required resolution

For every touched common field in PR0161, define whether unavailable data is represented as:

- `null`;
- `""`;
- omitted.

Do not fabricate semantic values.

For the newly requested `referring_physician`, the requested v1 behavior is:

```json
"referring_physician": ""
```

when no authoritative value exists.

## Non-debt note — `analysis_author`

`analysis_author` is request/caller metadata.

Observed batch output:

```json
"analysis_author": "Bremen batch compatibility smoke"
```

This value was supplied by `POST /api/jobs`.

It must not be reclassified as model-owned or H5-owned metadata.
