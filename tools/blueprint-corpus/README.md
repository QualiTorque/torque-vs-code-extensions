# Blueprint corpus tooling

Two human-operated scripts for turning a **customer** blueprint repository into a
validation corpus for this extension without leaking the customer's data.

| Script | Job | Needs |
|---|---|---|
| `sanitize_blueprints.py` | Redact secrets into a separate sanitized copy | Python 3.7+, stdlib only |
| `validate_blueprints.py` | Run both validation layers over a corpus, write reports | Python 3.7+, `pyyaml`, `jsonschema` |

## Governing rules

1. **Sanitize first.** Nothing touches a raw customer drop before
   `sanitize_blueprints.py` has produced a sanitized copy and `residual-scan.txt`
   is clean.
2. **An AI must never read the corpus, the raw reports, or the sanitized
   blueprints** — not the raw drop, not the sanitized tree, not `summary.txt`,
   `findings.txt`, `findings.json`, `path-map.txt`, or either sanitization report.
   The one file designed to be shared with an AI or pasted into a chat is
   **`safe-summary.txt`**.
3. **The originals are never modified.** The sanitizer writes only to a separate
   output directory, opens every source read-only in binary mode, and sha256-hashes
   every file under the input tree before and after the run — a mismatch aborts
   with exit code 4. The validator opens the corpus read-only.
4. **Neither script makes a network call.** The sanitizer has no sockets, no
   `urllib`, no `subprocess` at all; the validator shells out only to
   `git rev-parse --short HEAD` for its report header.

## TL;DR workflow

All paths are examples — substitute your own.

1. Pre-scan the drop read-only — writes nothing but a report, safe against the original:

```bash
python sanitize_blueprints.py --scan-only C:\corpus\raw --report-dir C:\corpus\scan-report
```

2. Sanitize into a new, empty directory:

```bash
python sanitize_blueprints.py --in C:\corpus\raw --out C:\corpus\sanitized
```

3. Read the sanitization report:

```bash
notepad C:\corpus\sanitized\_sanitization-report\sanitization-report.txt
```

4. Read the residual scan — it must show zero findings; skim its REVIEW section by hand:

```bash
notepad C:\corpus\sanitized\_sanitization-report\residual-scan.txt
```

5. Validate the **sanitized** directory:

```bash
python validate_blueprints.py --in C:\corpus\sanitized --report-dir C:\corpus\validation-report
```

6. Read the summary yourself — CRASHES first, then NEW clusters, then UNEXPECTED PROPERTIES:

```bash
notepad C:\corpus\validation-report\summary.txt
```

7. Share only this file, and only if you want help interpreting the run:

```bash
notepad C:\corpus\validation-report\safe-summary.txt
```

## Setup

The sanitizer needs **Python 3.7+ and nothing else** — deliberately
dependency-free so it can be read in one sitting and run air-gapped. The
validator additionally needs:

```bash
pip install pyyaml jsonschema
```

**The two pygls modes.** `server/validation/*` and `server/ats/trees/common.py`
import from `pygls`, and this repo pins `pygls==0.11.3`, which only installs on
Python 3.6/3.7. **Real pygls** matches CI — make a Python 3.7 virtualenv and
`pip install -r server/requirements.txt` (a current Python will not install these
pins). The **built-in stub** is used automatically when `import pygls` fails, i.e.
on any modern Python, and provides only the names those modules touch (`Position`,
`Range`, `Diagnostic`, `DiagnosticSeverity`, `Document`). The stub route is fine
for everyday use: it was verified to produce **byte-identical reports** to real
pygls on the 454-file internal reference corpus — the six internal ZeroTouch
repositories, walked with the canonical prune list (`.git`, `node_modules`,
`__pycache__`, `.venv`, `.tmp`). Every report header states which mode ran.

### Re-verifying the pygls stub

Repeat this after changing anything under `server/`. Run the same corpus twice,
once per mode, into different report directories — first with the Python 3.7
virtualenv that has real pygls 0.11.3 installed:

```bash
C:\py37\Scripts\python.exe validate_blueprints.py --in C:\corpus\reference --report-dir C:\corpus\rep-real
```

```bash
python validate_blueprints.py --in C:\corpus\reference --report-dir C:\corpus\rep-stub
```

Then diff `summary.txt`, `findings.txt` and `safe-summary.txt`, ignoring only the
header lines that legitimately differ — `pygls`, `timestamp` and the report-path
line (add `generated_at` if you also diff `findings.json`):

```bash
for f in summary.txt findings.txt safe-summary.txt; do diff <(grep -vE '^(timestamp|pygls|generated_at) |^Reports written to' /c/corpus/rep-real/$f) <(grep -vE '^(timestamp|pygls|generated_at) |^Reports written to' /c/corpus/rep-stub/$f); done
```

The recorded result is **zero differing lines** across all three files. Anything
else means the stub has drifted from real pygls and must be fixed before its
reports are trusted.

## Script 1: `sanitize_blueprints.py`

Text-based redaction — only sensitive substrings are rewritten, so comments, flow
style, indentation quirks, CRLF, mojibake, duplicate keys and files that are not
valid YAML all survive. That is the point: those files exercise the parser
hardest. Each redaction becomes a stable `REDACTED_<CATEGORY>_<n>` placeholder.

### What it detects

**Mechanism A — secret-ish key names** redacts the **whole value**: `password`,
`client_secret`, `api-key`, `Administrator Password`, `connection_string`,
`sas_token` and friends. Keys are normalized (lower-cased, spaces/dashes folded to
underscores) so all spellings hit; a few tokens (`password`, `token`, `secret`,
`apikey`, …) also match glued, catching `mypassword`/`dbtoken`. Because the common
Torque input shape hides the secret one level down, `default`, `defaults`, `value`
and `values` are promoted to secret when an ancestor key is secret-ish:

```yaml
inputs:
  - Admin Password:
      type: password
      default: <this gets redacted>
```

**Mechanism B — value patterns** redacts substrings, keeping the surrounding
shape: PEM private keys, certificates, ssh public keys, URL userinfo (scheme and
host survive), JWTs, AWS access key ids, GitHub/Slack tokens, Google API keys,
bcrypt hashes, base64 blobs, long hex runs, plus (opt-in) e-mails, IPs, hostnames,
MACs. Crucially it also fires **inside shell command bodies**, where no key name
exists to go on: `Authorization: Bearer …` headers, `--password` / `--api-key` CLI
flags, and `SOMETHING_TOKEN=…` environment assignments.

### Categories

`--categories` takes bare names to **replace** the defaults, `+name` to add,
`-name` to drop.

| Group | Default | Covers |
|---|---|---|
| `secret` | on | PEM private keys, ssh public keys, JWT, cloud/vendor tokens, bcrypt, base64 blobs, high-entropy hex, inline CLI/env/header secrets |
| `certificate` | on | `-----BEGIN CERTIFICATE-----` blocks |
| `url-credentials` | on | `user:pass@` userinfo in URLs |
| `email` | opt-in | e-mail addresses |
| `ip` | opt-in | IPv4/IPv6 (loopback, `0.0.0.0`, `::` kept) |
| `hostname` | opt-in | FQDNs against a TLD allow-list (`localhost` kept) |
| `identifier` | opt-in | MAC addresses, serial-number-shaped tokens |

Identity scrubbing is opt-in because hostnames, IPs and e-mails change the *shape*
of the scalars under test far more than a secret does. Turn it on when the corpus
warrants the fidelity loss:

```bash
python sanitize_blueprints.py --in C:\corpus\raw --out C:\corpus\sanitized --categories +email,+ip,+hostname
```

### Three rules that keep the corpus faithful

1. **Keys are never rewritten** — only values. Blueprint structure, the thing the
   validators actually read, is untouched.
2. **Pure-Liquid values are never redacted.** A value that is entirely `{{ … }}` or
   `{% … %}` is a structural reference; Liquid spans inside longer text are
   preserved too. YAML aliases (`*name`) are never redacted and anchors keep `&name`.
3. **Two exemptions protect load-bearing content:**
   * `pattern:` and `validation-description:` are exempt from **both** mechanisms
     — those lines survive byte-identical. A `pattern` is a regex whose exact
     content decides Torque's required-vs-optional semantics; a placeholder inside
     it could silently flip an input from optional to required and make the corpus
     lie to the validator under test.
   * **Content-addressed keys** (`commit`, `sha`, `sha1`, `sha256`, `digest`,
     `image`, `tag`, `ref`, `revision`, `version`, `chart-version`, `path`,
     `store`, `path-in-archive`) are exempt from the **two entropy detectors
     only** (`base64-blob`, `high-entropy-hex`). Every other detector still runs
     there, so a real token pasted into `path:` is still caught. The same applies
     to `sha256:`-prefixed digests anywhere, including `docker pull …@sha256:…`
     inside a shell body.

### Output

Written to `--report-dir`, default `<DST>\_sanitization-report` (for
`--scan-only`, `<CWD>\_sanitization-report`).

| File | Purpose |
|---|---|
| `sanitization-report.txt` | The one to read: counts by category and mechanism, per-file redactions, skipped files, pruned dirs, warnings, and both known-behavior lists below |
| `sanitization-report.json` | Same data machine-readably, plus review candidates |
| `residual-scan.txt` | **The gate.** Re-scans the *output* tree; must show zero findings. Its REVIEW section lists near-misses to eyeball |

No original value reaches a report — only the first 8 hex digits of
`sha256(value)`, enough to correlate duplicates and nothing more. REVIEW reports
location, length and a category guess, never content: values the content-addressed
exemption let through, base64-ish runs below `--base64-min`, and matches for
categories left switched off.

**Known deliberate over-redactions** (expected, not bugs): credential *name*
references — `credentials: my-aws-cred` is a reference by name, but the
`credential`/`credentials`/`auth` key tokens redact it anyway (the value stays a
plain string so structure survives; `credential_name:` and `credentials_name:` are
**not** redacted); **ssh public keys**, redacted despite being public because they
identify a customer machine and operator; **non-string values** under a secret-ish
key — booleans, numbers, flow collections, each listed under WARNINGS as
"non-string value redacted".

**Known deliberate non-redactions** (expected, not misses): content addresses,
`pattern:` / `validation-description:` lines, pure Liquid and Liquid spans, YAML
anchors and aliases — the three rules above. Both lists are reprinted in every
report so nothing surprises you.

| Exit | Meaning |
|---|---|
| 0 | Success, no residual findings |
| 2 | Residual findings in the output tree, or `--self-test` failed |
| 3 | Safety refusal or bad usage |
| 4 | Unexpected error (traceback shown), or input-tree mutation detected |

Exit 3 covers the refusals that stop you destroying a drop: output equal to input,
output nested in input, input nested in output, a report or mapping path inside the
input tree, or a non-empty output directory without `--force`.

To gain confidence on your own machine, run the built-in planted-corpus test —
temp directories only, cleaned up afterwards, currently 94 checks:

```bash
python sanitize_blueprints.py --self-test
```

`--emit-mapping PATH` writes a **reversible** placeholder-to-original-value JSON
file. **It is exactly as sensitive as the original repository.** Do not share it,
do not put it in the output tree, delete it when done.

Also available: `--dry-run` (report only, no sanitized files — this also skips the
residual scan, since there is no output to scan), `--include-ext`, `--base64-min`,
`--max-file-mb`, `--force`, `--quiet`.

## Script 2: `validate_blueprints.py`

Runs the extension's two validation layers over a corpus. See
[`docs/spec2-language-support.md`](../../docs/spec2-language-support.md) section 1
for why there are two and why neither subsumes the other.

* **Layer 1 — JSON schema:** `client/schemas/blueprint-spec2-schema.json` under
  `jsonschema.Draft7Validator`; what VS Code's YAML engine shows as you type.
* **Layer 2 — language server:** `server.ats.parser.Parser` builds the tree,
  `BlueprintSpec2Validator` (`server/validation/bp_v2_validator.py`) runs the
  semantic checks; what the extension publishes as diagnostics.

Only `spec_version: 2` files are validated by default. `--include-non-spec2`
widens this to every `*.yaml`/`*.yml`; a file that does not parse into a spec2 tree
then gets the schema and parser layers only, because the real server routes such
files to a different validator.

### Report files

Written to `--report-dir`, default `./blueprint-validation-report`.

| File | Level | Purpose |
|---|---|---|
| `summary.txt` | per `--level` | The one to read: counts, crashes, clusters, UNEXPECTED PROPERTIES table, triage, what-to-do-next |
| `findings.txt` | per `--level` | Per-file detail, one line per finding |
| `findings.json` | per `--level` | Machine readable |
| `safe-summary.txt` | **always safe** | Message templates, schema sections, rejected property *names*, counts, and anonymous `bp_0001` file ids. No blueprint values, no source lines, no raw messages, **no file names, no paths**, no directory structure |
| `path-map.txt` | **confidential** | Always written; the id-to-path key that de-anonymizes every other report, `safe-summary.txt` included. Use it locally to resolve an id |

**`--level full` vs `safe-summary.txt`** is the whole confidentiality model:
`--level full` (the default) lets `summary.txt` / `findings.txt` / `findings.json`
quote blueprint content — property names, raw messages, source lines — and stamps
each "FULL — treat as confidential", **for your eyes only**. `--level safe` strips
source lines and raw messages from those files, leaving normalized templates and
counts. `safe-summary.txt` is written **regardless of `--level`** and is the only
file designed for sharing.

`safe-summary.txt` refers to files by anonymous id **unconditionally**, whatever
`--anonymize-paths` says: a basename like `acme-prod-deploy.yaml` can identify a
customer on its own, and the one file whose purpose is to be pasted into a chat
has to be safe outright rather than safe-if-the-right-flag-was-passed. So
`--anonymize-paths` affects only the other three reports — pass it when paths in
`summary.txt` / `findings.txt` / `findings.json` are themselves identifying
(customer or code names in directory names) and you want those id-based too.

```bash
python validate_blueprints.py --in C:\corpus\sanitized --level safe --anonymize-paths
```

### Triage model

Findings are clustered by normalized message and matched against
`known_findings.json` (override with `--triage`, disable with `--no-triage`, which
labels everything NEW).

| Verdict | Meaning |
|---|---|
| `KNOWN-BLUEPRINT-DEFECT` | The blueprint really is wrong and Torque silently ignores the key. Nothing to fix in the extension |
| `KNOWN-TOOL-LIMITATION` | A false positive of our own validator, already understood |
| `NEW` | Not in the catalog |

**NEW clusters are the ones that deserve investigation.** Everything else is
already understood; a NEW cluster is either an undocumented blueprint defect or —
more interestingly — a bug in this extension's schema or validator.

| Exit | Meaning |
|---|---|
| 0 | No findings, or only KNOWN ones under the default `--fail-on new` |
| 1 | Findings, per `--fail-on` |
| 2 | Crashes in the language server |
| 3 | Setup error (missing repo, schema or dependency) |
| 4 | Unexpected error |

`--fail-on` picks what makes the exit non-zero: `none`, `findings`, `new`
(default), `crashes`. Crashes give exit 2 under every value except `none` — a
crash is never merely a finding, because the running server swallows it and the
file loses *all* diagnostics.

Also available: `--repo-root` (defaults to the script's `../..`), `--show
{clean,findings,all}`, `--max-examples N`, `--quiet`.

## How to act on results

1. **CRASHES first.** Each is a tool bug that makes the language server publish
   nothing at all for that file. Reproduce with the named file, fix, add a
   regression test under `tests/`.
2. **NEW cluster — investigate the tool.** Decide whether the blueprint is wrong
   or the schema/validator is. **Verify the key against the Torque server source
   (cs2018) before changing anything or concluding either way.** Blueprint wrong:
   add a catalog entry. Tool wrong: fix it *and* add a test — and remember both
   layers move together, so a key added to the schema must also go into the tree
   model, or the server reports it unknown while the schema accepts it.
3. **KNOWN-BLUEPRINT-DEFECT — report to the blueprint owners.** Torque silently
   drops these keys, so the blueprint does not do what its author thinks.
4. **KNOWN-TOOL-LIMITATION** — worth fixing eventually, not a surprise.

### Extending `known_findings.json`

Add an object to `clusters`:

```json
{
  "match": "unexpected property: grains.<key>.timeout",
  "kind": "blueprint-defect",
  "note": "There is no grain-level 'timeout' in the grain model; the value is ignored."
}
```

`kind` is `blueprint-defect` or `tool-limitation`. `match` is tested as a substring
first, then as a regex, against the finding's signature, template, message, path
and section — so a message with a variable part usually needs both a schema-worded
and a server-worded entry (the catalog carries pairs like
`unexpected property: inputs.<key>.optional` and `unknown key: 'optional'`).

**The rule: an entry goes in only after the behavior was verified against the
Torque server source. Never guess, and never add a row just to quieten the
report** — that turns a real signal into permanent silence.

## Reference results

Last known-good run on the internal reference corpus; use it to tell "normal" from
"something changed".

| Metric | Value |
|---|---|
| spec2 files validated | 454 |
| fully clean | 350 |
| crashes | 0 |
| findings total | ~790 |
| of which NEW | a small minority; the vast majority are KNOWN |

That corpus is the six internal ZeroTouch blueprint repositories. **It is not
customer data**, which is why it can be discussed openly. A customer corpus never
gets a row in this table.

**Out-of-sample check.** The table above is the corpus the schema, the validator
and `known_findings.json` were tuned on, so a clean run there proves less than it
looks. A second run covered 73 spec2 files the tooling and the catalog had never
seen: `C:\ZeroTouch\Compute` (31), `C:\ZeroTouch\Compute2` (36),
`C:\ZeroTouch\torque-tunnel` (4), and 2 Torque-team-authored generated fixtures
from `cs2018\server\CSBlueprintService.Tests\Domain\AutoGeneratedV2Yamls\TestFiles`.
The result that matters is **0 NEW clusters and 0 crashes on unseen blueprints** —
every finding landed in the existing catalog, so the triage model generalizes
rather than merely describing the corpus it was built from.

| Metric (out-of-sample) | Value |
|---|---|
| spec2 files validated | 73 |
| fully clean | 59 |
| with findings | 14 |
| crashes | 0 |
| findings total | 36 |
| NEW clusters | **0** (all 36 findings KNOWN) |
| exit code | 0 |

Sanitization was also **validation-neutral** on all four sources: the finding sets
before and after sanitization were identical (31/31, 36/36, 4/4, 2/2), with zero
differing files. That is the property the three fidelity rules above exist to
protect — redaction must not change what the validators see.

## Confidentiality checklist

- [ ] The raw drop was never modified — `sanitization-report.txt` confirms the
      sha256 manifests matched.
- [ ] `residual-scan.txt` shows zero residual findings.
- [ ] Its REVIEW section was skimmed by hand.
- [ ] Validation ran against the **sanitized** directory, not the raw one.
- [ ] No `--emit-mapping` file remains, or it is stored as securely as the original repo.
- [ ] The file about to be shared is `safe-summary.txt` and nothing else — it is
      free of file names by construction, no flag required.
- [ ] `path-map.txt` stays local. It is always written, and it is the key that
      resolves the ids in `safe-summary.txt` — sharing both together undoes the
      anonymization.
- [ ] `summary.txt`, `findings.txt`, `findings.json` and both sanitization
      reports stay local.
- [ ] No AI has been pointed at the corpus, the sanitized tree, or any report
      other than `safe-summary.txt`.
