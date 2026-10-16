# Respectful retrieval and source completeness (ML-126)

This implements [contract section 3](ingestion-contracts.md#3-retrievalcompleteness-contract--implemented-by-ml-126)
for new Isanti parcel acquisitions. It does not re-download or certify historical
snapshots, change county tax meanings, or implement ML-127's publication protocol.

## Acquisition checks

The adapter supplies the expected layer name and ML-125 schema callback. Before
count/ID/page queries, the client checks the layer ID/name, explicit Query,
pagination/order-by support, requested declarations, non-nullable OID declaration,
and positive integer advertised maximum. No guessed OID or alternate query strategy.
Only explicit mapped fields and no geometry are requested. Effective page size is
the smaller of the configured page size and the current advertised maximum.

For the same predicate, initial count and `returnIdsOnly` responses must agree;
counts cannot be booleans/negative/fractional, and inventories contain unique integer
IDs with the expected OID field name. Page IDs must belong to that inventory and
remain unique and ascending across page boundaries. Malformed feature/attribute
structures, missing/invalid OIDs, oversized or premature empty pages fail with
page/record diagnostics. Short nonempty pages advance by their actual length.
Explicit transfer flags must be boolean: false before the expected end, or true
at the expected end, contradict completeness and fail. Missing flags are not
proof of completeness; inventories and counts still have to reconcile.

End count, ID inventory, metadata and optional `editingInfo.lastEditDate` are
rechecked. Count changes, same-count ID replacement, requested-field declarations
(including aliases), identity/capabilities/advertised-limit changes and changed edit
tokens fail. Added unrequested fields do not change the requested schema contract.
A consistent zero-count/empty-array inventory is valid, with an empty-source warning;
it does not establish paid/current tax status.

Unchanged membership/counts cannot establish unchanged attribute values. An absent
edit token is recorded as unknown with a same-ID consistency warning; an observed
unchanged token is only an observation. Neither is a point-in-time/transactional
source guarantee. The retained Isanti metadata lacks this token; this story made
no live request to check whether the current service has changed.

## HTTP policy and configuration

[Settings](../src/mn_land/config/settings.py) now passes the effective
[RetrievalPolicy](../src/mn_land/config/retrieval.py) through `IsantiAdapter` to its
client and actual urllib transport. An explicitly injected client remains responsible
for its own configuration; conflicting real client/transport policies are rejected.
`max_retries` retains its historical name but means **total attempts**, not retries
after a first attempt.

| Control | Default and behavior |
|---|---|
| Socket timeout | Finite, positive 30 seconds per attempt; not an overall wall-clock transaction timeout. |
| Attempts | Three total per logical request. |
| Retryable HTTP | 408, 429, 500, 502, 503, 504 only. Other statuses, including 400/401/403/404 and redirects, fail. |
| Retryable application codes | Conservative explicit ArcGIS envelope allowlist 429/503/504. Generic application 500, unknown codes, schema and auth errors fail; HTTP 500 is separately retryable. |
| Network | Timeout/connection failures, selected unreachable/down/reset/refused errno values and temporary DNS retry. Certificate errors, permanent DNS and unknown reasons fail. |
| JSON | Malformed/truncated/invalid-encoding JSON has bounded retry. Non-object or non-finite JSON fails; no fabricated replacement. |
| Pacing/backoff | Sequential requests, at least one second between attempt start times; exponential retry backoff starts at one second. The wait is the maximum of pacing, backoff and server delay, never a downward clamp. |
| Retry-After | Delta-seconds or HTTP-date. Invalid/past values use fallback. If the necessary wait exceeds a budget, stop with Retry later; do not retry early. |
| Wait budgets | 60 seconds maximum single wait; 120 seconds total across the acquisition, including successful-request pacing. New capture resets the total, but preserves spacing from the prior request on the same transport. Larger acquisitions may require an explicitly reviewed budget increase. |
| Original body | 25 MiB maximum per response, read in bounded chunks. Exceeding it fails, retaining only the capped prefix with a truncation marker. Partial bodies/length mismatches are marked incomplete. |
| Inventory | One million IDs maximum, additionally constrained by the body cap. Excess count or an incomplete/mismatched inventory fails; there is no automatic ID batching. |

No concurrency, cached substitution, scheduling, credential discovery, or alternate
source is introduced. Redirects are not silently followed outside pacing/evidence
checks. Budgets are engineering protections, not permanent county limits.

## Evidence and failure boundary

New raw directories retain `layer_metadata.json`, `count_start.json`, `ids_start.json`,
ordered `page_*.json`, `count_end.json`, `ids_end.json`, and `layer_metadata_end.json`.
With the real urllib transport, `http/attempt_NNNNN.body` preserves original response
bytes (or a marked capped/incomplete prefix). Compact `.parsed.json` files preserve
successfully decoded finite JSON, including error envelopes; `.evidence.json` records
body byte counts/hashes, parsed hashes, status, outcome, attempt, timeout and wait.
HTTP failure bodies remain private raw evidence and are not printed in diagnostics.
URLs/query strings, arbitrary network reasons and server messages are not copied
into transport diagnostic messages. Treat raw bodies as sensitive public-record data.

The acquisition manifest records effective policy/page size, source observations,
timestamps, fingerprints, edit-token observations, consistency warnings, attempt
ranges per successful logical request, and all retained artifact hashes. Injected
JSON-only test transports explicitly disclose that original wire bytes are unavailable.
`failed_request.json` associates transport failures with their intended artifact;
`retrieval_failure.json` records validation/transport failure without a success manifest.
Attempts already received survive retry exhaustion or an excessive wait requirement.
CLI acquisition errors produce a clear error exit instead of an unhandled traceback.

This is **not** atomic processed publication or shared reader eligibility. A caller
may receive earlier generator pages before a later source check fails; the current
pipeline waits for acquisition completion before exporting. ML-127 will enforce
completion and hashes across all readers. Legacy snapshots are not rewritten, and
the existing filename-based reader must not be mistaken for that future guarantee.

## Offline verification

- H01-H05: [source-contract fixtures](../tests/unit/test_retrieval_contract.py), plus
  [existing pagination](../tests/unit/test_pagination.py) and adapter schema gates.
- H06-H08: [HTTP fixtures](../tests/unit/test_http_contract.py), including fake clocks,
  exact waits/attempts/timeouts, HTTP/application/network classification, malformed
  JSON, body boundaries, partial reads, failed acquisition evidence and full real
  transport-to-manifest hashing with fake responses.
- Existing normalization, join, review and provenance fixtures remain in the full
  offline suite. No original county inputs or live government API calls are needed.

Results and hosted CI evidence are recorded in [testing](testing.md).

Protocol references: Esri's [query documentation](https://developers.arcgis.com/rest/services-reference/enterprise/query-feature-service-layer/)
describes counts, ID queries and paging; its documented ID-array ceiling is one
million, so an ID inventory is not assumed unlimited. HTTP
[Retry-After semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after)
permit delay-seconds or HTTP-date. Retry selection and local budgets above are
our conservative engineering policy, not a county availability promise.
