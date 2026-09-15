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
| `required-paths.txt` | every path listed must be exercised by at least one `valid/` fixture |

An `invalid/` fixture that produces no error at all is the failure this corpus
exists to catch: the dead key that the schema accepts and the server then drops
without a word.

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
under you. If you are unsure what the schema says, run the suite: a failure
prints every message with its JSON path.

If a new valid fixture adds coverage, nothing else is needed. If the *schema*
gains a key that real blueprints already use, add it to `required-paths.txt` as
well — and the easiest way to get that right is to regenerate the file.

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
