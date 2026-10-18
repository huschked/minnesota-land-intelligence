# Contextual research exports (ML-205)

The local viewer exports an explicitly previewed filtered or selected worklist,
not an offer list or a new county observation. No acquisition, reimport, replay,
source edit, outreach, balance calculation or latest-pointer update occurs.

## Use

1. Explicitly load a completed join/review and choose the research filters and
   service sort. Built-in grid download/copy remains disabled.
2. Under **Research worklist export**, choose **All filtered parcels** (all pages,
   distinct IDs) or **Selected parcel only** (the existing keyboard selector).
3. Select **Preview contextual export**. This revalidates the full pinned graph,
   hashes, candidate selection, source rows/year semantics and monetary mappings.
   Review counts, filter/order/scope, snapshot/hash, separate source dates, warnings
   and the first ten ordered IDs. Candidate years include both contributing periods.
4. Inspect **Snapshot-wide issues and source accounting**, paginated 25 entries at
   a time. These entries are independent of candidate filters and can overlap;
   their counts are not unique parcels or extra candidates. Accounting/quarantine
   summaries are included even when zero. Held/empty results can export issue-only
   context; active holds never release candidate records.
5. Click **Download contextual CSV** or **Download contextual JSON**. A native
   deferred callable revalidates and reconstructs the worklist on that click,
   comparing its semantic fingerprint with the preview before supplying bytes.
   It never serves a cached, previously validated byte blob as newly checked data.

Filter, sort, scope, selected-ID, Clear, Load or Reload changes revoke the previous
download request and clear its preview. Table/source-issue pagination and ordinary
reruns use the per-session immutable observation, without new disk reads. A download
already in flight also checks revocation after validation/serialization. The file
always names its captured scope/filters/fingerprint; this is not a live UI watch or
an atomic filesystem transaction after the final check.

If evidence changed or validation/budgets fail, no stale/partial file is supplied.
Deferred download errors are reported by the framework; **Check export status**
or the next interaction drains a per-session error queue and clears the stale
table/details/preview. Reload and explicitly preview valid evidence again. The
download thread never reads/mutates Streamlit session state. No shared trust cache,
arbitrary local-file route, external fetch or export directory is created.

## Contents and interpretation

JSON schema version 1 has `context`, ordered distinct `candidates`, and separately
ordered `issues`. Canonical money and acreage are exact base-10 strings or null,
never binary floats, unknown-as-zero substitutions or inferred sums. GIS owner
text stays separately labelled; no preferred listing/GIS owner is invented.

Context includes the selected snapshot/completion hash, pinned join/GIS/import
identities and completion hashes, listing bytes/mapping hashes, source agency/
dataset, listing publication/capture and GIS capture dates, unknown report date,
reviewed year convention, active filters/floor/scope, counts, warnings and order.
Each generation records a fresh `integrity_checked_at`; record order is deterministic,
but a new generation timestamp can change file bytes. Candidate order is the active
service sort across all pages, with nulls last and ascending parcel-ID ties. Both
prior/current year sets, source row/sheet references, category and nullable canonical
money remain separate. This is not a raw source-file dump.

Issue records retain a fixed artifact name, saved-record ordinal and allowlisted
fields from unmatched, duplicate source-row, ambiguous, unverified and (for reviews)
fiscal-group tables. Unverified-period references and source-accounting summaries
are included. Issue CSV blanks become null; other values stay source text (for
example a saved CSV year is a string). GIS diagnostic severity/field/feature/record
IDs and quarantine counts are exposed, but unrestricted reasons, raw values,
operation paths and correspondence are withheld. Complete originals stay local.
Issue order is kind, artifact and canonical field values (lexical), not a risk rank.

CSV has fixed columns and `record_type` values for candidate, issue or (when both
are empty) context-only rows. It repeats `context_json` on every row so an empty or
separated worklist cannot lose its warnings/source context. `candidate_json` retains
the complete candidate projection; period/issue JSON cells retain nested structure.
This is a research/audit CSV, not an ordinary numeric-only spreadsheet table.

Every CSV data text cell is prefixed with an apostrophe, including exact numeric
text, IDs and nested context; every field is double-quoted with standard quote
escaping. `UNKNOWN` is the fixed null marker, distinguishable from source text
`'UNKNOWN`; JSON retains actual nulls and original canonical text. Protection is
disclosed in the preview and each row's context, and never rewrites saved sources.
Some spreadsheet imports display the apostrophe. Import as text and retain it.
There is no universal CSV/re-save guarantee: do not strip protection or rely on a
re-saved CSV retaining it; use JSON for programmatic fidelity. The presentation
policy follows the quoted/text-prefix approach and limitations documented by
[OWASP CSV Injection](https://owasp.org/www-community/attacks/CSV_Injection).
This policy applies only to these new worklist downloads; original inputs and
historical CLI exports are unchanged and must not be assumed to have this protection.

Limits are engineering safeguards: at most 20,000 candidate plus issue entries,
32 MiB per generated format and per saved issue-table read, and the retained input
limits for original listing bytes. Over-budget output is refused rather than
silently truncated. CSV repeats context and can hit its byte budget before JSON;
try JSON or narrower candidate filters. Issues remain snapshot-wide.

Access, usable/buildable acres, zoning, resale value and profit remain not assessed.
Current paid status is unknown; source dates, integrity checks and historical sample
findings do not establish current debt. County accounting/identity blockers remain
unchanged. [ML-206 release evidence](reviews/local-viewer-release-2026-10-17.md)
subsequently verifies actual browser downloads/refusal and the canvas clipboard
guard, with keyboard checks and user-confirmed 200% zoom. Screen-reader and
spreadsheet re-save certification are not claimed.

## Implementation and verification

[Worklist projection/serialization](../src/mn_land/worklists.py) is pure Python;
[county issue columns](../src/mn_land/counties/isanti/worklists.py) remain in the
adapter. The [service](../src/mn_land/review_service.py) owns disk validation and
reuses ML-204's exact source-evidence checks for exported candidates. The
[thin UI](../src/mn_land/ui/worklists.py) captures immutable requests, uses revocable
deferred native downloads and renders all source text literally.
[Pure](../tests/unit/test_worklists.py), [service](../tests/unit/test_worklist_service.py)
and [AppTest](../tests/unit/test_worklist_ui.py) checks cover format fidelity,
ordering, null/zero, injection payloads, holds/issues, scope, revalidation and no
source mutation/acquisition. See [dated evidence](testing.md#ml-205-contextual-worklists).
AppTest and direct invocation of captured deferred jobs are not a browser-download
or Excel re-save conformance test.
