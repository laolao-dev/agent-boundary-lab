# MCPGuard-Dynamic Attempt 03 public evidence

These are clearly labelled public copies derived from the sealed
`first_blind_attempt_03` evidence. The sealed originals remain private and are
unchanged.

Sanitization affects only machine-local identity and absolute filesystem-path
metadata. It does not change scores, counts, case IDs, decisions,
classifications, methodology, false positives, false negatives, or benchmark
semantics. A file containing a sanitized value has a different public SHA-256;
an included file requiring no replacement remains byte-identical and retains its
original SHA-256. `SANITIZATION_MANIFEST.json` records both hashes and the field
selectors changed without recording the removed username or path value.

References to `.aws/credentials`, `.env`, and `.ssh/id_rsa` are synthetic fixture
references from the benchmark workspace. They preserve benchmark semantics and
do not indicate that a real credential, environment file, or private key was
published. No real credential contents are included.

Files that contained a legacy ABL Git object identifier were not copied into
this public bundle. The benchmark report supplies clean-history identifiers and
the preserved source-tree anchor instead.

Two auxiliary diagnostic/bootstrap logs are also omitted rather than rewriting
their original line endings to satisfy the Git whitespace gate. The result,
breakdown, raw, audit, integrity, conformance, and environment artifacts remain
included; every omission and its reason is listed in the manifest.

Outside this evidence directory, the publication copy of
`../benchmark_manifest.json` replaces only its ABL base-commit pointer with the
corresponding clean public commit. This metadata translation does not alter the
frozen executable integration, policy, adapter, or benchmark semantics.

## Result scope

The ABL project itself executed this evaluation on the externally authored
MCPGuard-Dynamic benchmark. “External” describes the benchmark source, not the
evaluator, and does not imply third-party validation or Meta/MCPGuard endorsement.

The frozen C-ABL result is Raw APR 34/61 (55.7%), V-APR 21/48 (43.8%), benign
success 13/21 (61.9%), and FPR 8/21 (38.1%). This is a security–utility tradeoff,
not a superiority result.

See the [public benchmark report](../../../docs/benchmarks/mcpguard_dynamic_v01.md)
for the methodology, same-session baselines, limitations, and frozen hashes.

## Clean-history disclosure

> The public repository history was identity-sanitized after the evaluation.
> The source tree used for the evaluation is byte-for-byte identical to the
> corresponding clean-history tree; only Git author, committer, and tagger
> identity metadata changed.

The clean public lineage baseline is commit
`d9c381d13500b1f69efc404eab6792e0e4f5f7e7`. The preserved evaluated-source tree
is `c6cfff8f97cf1a35901740e4803c814371443174`. This is a tree-level
reproducibility statement; it does not equate the old and clean commit objects.
