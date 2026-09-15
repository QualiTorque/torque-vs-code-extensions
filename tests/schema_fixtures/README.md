# Schema fixture corpus

A CI-enforced regression corpus for `client/schemas/blueprint-spec2-schema.json`,
driven by [`tests/test_schema_fixtures.py`](../test_schema_fixtures.py).

Each fixture is a **minimal, generic** blueprint: one feature family per file,
just enough YAML to mean something. They stand in for the real blueprints in the
internal ZeroTouch repositories without carrying any of their content — no
hostnames, addresses, repository or product names, credentials or company names.
Write `example`, `my-grain`, `My Input`, `scripts`, `modules/app`, `agent-1`,
`my-cluster` and the like, always.

## The contract

| | |
|---|---|
| `valid/<feature>.yaml` | must validate with **zero** errors |
| `invalid/<defect>.yaml` | must produce **at least one** error, and every `# expect-error:` line must match some message |
| `required-paths.txt` | all 232 paths listed — the key paths the real blueprints use — must be exercised by at least one `valid/` fixture |
| the schema itself | every **property** (352), every **enum member** (115) and every **definition** (58) it declares must be exercised by at least one `valid/` fixture |

An `invalid/` fixture that produces no error at all is the failure this corpus
exists to catch: the dead key that the schema accepts and the server then drops
without a word.

The last row is the only one with nothing to maintain. `required-paths.txt` is
the floor the *real* blueprints set; full schema coverage is the ceiling, and
it is computed on every run — `PathClassifier` reports what the fixtures
reached, `SchemaEnumerator` reports what there is to reach, and the difference
is the failure message. Add a property to the schema and this corpus asks for a
fixture the same day, by name:

```
FAIL: test_every_declared_property_is_used (element='BlueprintInputObject.searchable')
BlueprintInputObject.searchable is declared by the schema but no valid fixture
uses it (1 of 352 properties uncovered).
```

Definition names come from the `$ref` a node was reached through, so a property
is identified as `<definition>.<key>` (`Backend.bucket`), a user-chosen key as
`<definition>.<name>`, and an inline sub-object borrows a dotted name from
where it sits (`Torque-Blueprint-Spec2.environment.collaborators`).

The counts in the table are therefore descriptions of today's schema, not
constants in the code — nothing has to be bumped when the schema grows.

Something the schema declares that *no valid document can reach* is excused in
`EXCLUDED_PROPERTIES` / `EXCLUDED_ENUM_VALUES` / `EXCLUDED_DEFINITIONS` in the
test module, each entry with a comment saying why. Unreachable is the bar:
"writing that fixture is awkward" is not a reason, and neither is "this key is
uninteresting" — an uninteresting key is exactly the kind that rots unnoticed.
All three lists are empty today, and an entry that stops matching the schema is
itself a failure, so they cannot rot either.

Matching runs against **all** error messages, nested `oneOf`/`anyOf` sub-errors
included — most interesting keys sit inside a combinator, where the outermost
message is only ever "is not valid under any of the given schemas".

## Adding a fixture

*A shape that must keep working* → drop a file in `valid/`. Start it with
`spec_version`, keep it as small as it can be while still meaningful, and open it
with a comment saying what it pins.

*A defect that must keep being reported* → drop a file in `invalid/` with one or
more header lines:

```yaml
# expect-error: <case-insensitive substring that must appear in some error message>
```

Match on the distinctive part of the message (`'display-name' was unexpected`,
`'arm' is not one of`, `'path' is a required property`) rather than on a whole
sentence, so that a jsonschema upgrade does not rewrite your expectation out from
under you. CI runs two versions and they do not word things alike — a `minItems`
failure reads `is too short` in 4.17 (the last release for Python 3.7) and
`should be non-empty` in 4.18+ — so pin the offending **value**, not the
library's phrasing. If you are unsure what the schema says, run the suite: a
failure prints every message with its JSON path.

If a new valid fixture adds coverage, nothing else is needed. If the *schema*
gains a key that real blueprints already use, add it to `required-paths.txt` as
well — and the easiest way to get that right is to regenerate the file.

*A new key, enum member or definition in the schema* → the coverage tests name
it for you. Put it in whichever `valid/` fixture already covers its
neighbourhood; start a new file only when it is a feature family of its own.
Keep a value that must be listed in full (a trigger event list, a provider
list) in one place, so the next member has an obvious home.

## Regenerating `required-paths.txt`

The file lists the schema-accepted key paths that the 528 spec2 blueprints in
the six internal ZeroTouch repositories actually use — `<name>` standing for a
user-chosen key and `[]` for a list level. It is what makes "the corpus is based
on the real blueprints" a checkable claim rather than a promise.

Regeneration needs the local corpus, which is deliberately not in this
repository. From a machine that has it checked out:

```
python tools/blueprint-corpus/classify_corpus_paths.py \
    client/schemas/blueprint-spec2-schema.json <out-dir> <corpus-root>...
```

Copy the resulting `<out-dir>/required-paths.txt` over this one, keep the header
lines, and add a valid fixture for every path that appears. The same run writes
`rejected-paths.txt` — the keys real blueprints use that the schema refuses —
which is where the `invalid/` fixtures come from.

The test loads that script by file path (the directory name has a hyphen, so it
is not importable as a package) and reuses its `PathClassifier` for the coverage
check, so the normalization in CI is the same code that produced this file.

## Running it

```
python -m unittest tests.test_schema_fixtures -v
```

It is also picked up by `python -m unittest discover tests/`. Only `pyyaml` and
`jsonschema` are needed — no pygls, no server stack — and it runs on Python 3.7
and 3.12 alike.
