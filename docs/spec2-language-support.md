# Spec2 language support — design notes

How this extension understands `spec_version: 2` blueprints, and why the code
looks the way it does. Written after the 2026-08 spec2 modernization so the
next contributor does not have to reconstruct the decisions from the tests.

## 1. Two validation layers

A spec2 document is checked twice, by two independent mechanisms:

| | JSON Schema | Python language server |
|---|---|---|
| Lives in | `client/schemas/blueprint-spec2-schema.json` | `server/` (pygls 0.11.3) |
| Runs in | the Red Hat YAML extension (`redhat.vscode-yaml`, an `extensionDependencies` entry of `client/package.json`) | our own LSP process, `server/server.py` |
| Expresses | structure, types, `additionalProperties: false`, enums, `oneOf`, hover documentation (`description`/`title`) | anything that needs to look at *another* part of the document |
| Gives the user | completion, hovers, structural errors | semantic diagnostics, `depends-on` completion (`server/completers/grain_completer.py`) |

Neither layer subsumes the other, so **both must be updated together**. Adding a
key means: add it to the schema *and* to the tree model (section 2), otherwise
the language server reports the new key as unknown while the schema accepts it.

The schema is the canonical key list. It is synced/audited against the Torque
server source (cs2018); the field-constant index there is `BlueprintFields.cs`,
and the sync recipe is kept in the maintainer's project memory
(`memory/blueprint-spec2-schema-sync.md`), not in this repo.

### Source freshness

The schema was synced against cs2018 on **2026-08-24**. Three backend changes
landed *after* that date — `inputs.<name>.optional`, server-side `pattern`
enforcement, and `target-filters.labels[].values` — and were folded in on
**2026-09-15** after re-verifying against cs2018 `origin/main` **c0f49bd04d**
and cs2018-ui **9fe9e4b01b** (section 8). The rule that produced that miss, and
which every future sync must follow: **before verifying anything against a
local cs2018 / cs2018-ui clone, fetch and compare against `origin` first, and
record the SHA you verified at** — a stale working copy answers questions about
the past. And a negative grep counts as evidence only when the same run also
contains a positive control: a pattern you *know* matches, proving the search
actually reached the source it claims to have searched.

Schema descriptions are load-bearing documentation: they are what a blueprint
author sees on hover, and they carry the semantics verified against cs2018 (for
example the `use-storage` description states the `auto-approve` coupling that
section 4 enforces). Keep them factual and short.

Wiring caveat: the schema is not associated with spec2 files automatically —
see section 7 before testing a schema change by hand.

## 2. Tree model (`server/ats/trees/blueprint_v2.py`)

The parser (`server/ats/parser.py`) builds a typed tree out of dataclasses. Each
dataclass field is a YAML key; the tree's top-level fields are exactly the 17
top-level keys of the schema (`spec_version`, `description`, `instructions`,
`metadata`, `environment`, `workflow`, `layout`, `labels`, `env_references`,
`resources`, `api_access`, `customization`, `family`, `template`, `inputs`,
`outputs`, `grains`).

* A key with no matching field produces a `Parent node does not have child`
  error, which the server publishes as a red squiggle. The tree model is
  therefore a *closed* key set, exactly like `additionalProperties: false`.
* YAML uses kebab-case, Python does not: every node that owns such keys
  overrides `_get_field_mapping()` (`"auto-approve" -> "auto_approve"`). The
  mapping is per-class and now cached in `ObjectNode._field_mapping_cache`; it
  used to be rebuilt on every attribute access.
* Properties that accept either a scalar shorthand or a nested object are
  annotated with `typing.Union` (e.g. `resources.<name>.reference`,
  `metadata.blueprint-labels` items, `deployment-engine`). A `Union` is not a
  class, so `issubclass` raises on it — `server/ats/trees/common.py` walks
  `__args__` instead, in `_get_seq_nodes`, in the `allow_vars` propagation and
  in `PropertyNode.__getattr__`.
* The shorthand exists only where the server declares `[YamlShortSyntax]` on
  the property (or gives it a type converter). `spec.target` does **not**: it
  is an object-only property like `spec.agent`, so the tree models it as
  `GrainSpecTargetObject` alone and a scalar `target: my-target` is reported,
  not accepted — both layers agree, which is what
  `TestTargetHasNoScalarForm` (`tests/test_spec2_server_parity.py`) pins.
  See section 11.

### Free-form sections

`FreeFormNode` / `FreeFormProperty` model sections that are free-form on the
server side too, and would otherwise drown the user in false "unknown key"
errors: `customization`, an inline ansible `inventory-file`, terraform provider
`attributes`, input-source `overrides`, `environment.tags` / `labels`,
`family.members`, backend workspace `tags`. They accept any nested mapping,
sequence or scalar without validating names.

A grain's `spec.inputs` values (`GrainInputMapping`) are `Union[FreeFormNode,
TextNode]` for the same reason: a terraform or ansible input takes a list or an
object just as well as a scalar (the schema types the value as
`string|number|boolean|object|array`), and modelling it as a scalar killed the
parse of the whole file. `spec.env-vars` stays scalar-only — the server's
contract there really is a scalar.

Two node types decide whether Liquid is allowed in a value: `ScalarNode`
(`allow_vars = False`, "Variables are not allowed here") and `TextNode`. Grain
`spec.authentication` entries are `TextNode`s: the server resolves them, and
they normally *are* an expression (`{{ .inputs["AWS Credentials"] }}`).

They are also deliberately **not expression-validated**
(`ExpressionValidationVisitor.visit_node` returns early on them, skipping the
whole subtree): the `{{ }}` inside them belongs to another dialect — the launch
form uses the UI's own template syntax (`{{ inputs.x }}`, no leading dot) and an
ansible inventory may hold Jinja. Validating them as grain Liquid would be
wrong. See `test_free_form_sections_not_expression_validated`.

### Flow style YAML

`allowed-values: ["a", "b"]` and `agent: {name: x}` are ordinary YAML and the
server accepts them, but pyyaml's token stream for a flow collection is not the
one the parser is built around (it consumes tokens, not the composed document).
Rather than teach every branch about flow tokens, `Parser._rewrite_flow_tokens`
translates the stream into the block one it already handles, before parsing:

```
[a, b]   ->  BlockSequenceStart Entry a Entry b BlockEnd
{k: v}   ->  BlockMappingStart Key k Value v BlockEnd
```

An empty `[]` / `{}` is dropped entirely — a block collection is *opened* by its
first element, so an empty one looks exactly like a key with no value — and a
trailing comma separates nothing and emits no entry. A block-only stream passes
through untouched, which is what keeps `tests/test_ast.py` byte-identical.

### Sequences written at the key's indentation

```yaml
overrides:
- x: 1
```
produces no `BlockSequenceStartToken`, so the token that closes the sequence is
really the parent's and the parser has to unwind one level more (the
`SEQUENCE_LIKE_NODES` branch in `_process_token`). The node holding such a
sequence may be a `SequenceNode`, the `UnprocessedNode` placeholder, or a
`FreeFormNode` — which models mappings and sequences with the same type. That
branch also closes the enclosing map element (`My Input:` under `inputs:`),
without which the next key of the map is written over the current element and
the entry disappears from the model.

### A scalar where an object belongs

`agent: my-agent`, `target: my-target` — a scalar handed to a property the tree
models as an object only. The value is wrong (the server's deserializer drops
it too), but *how* it is reported matters more than that it is: `Parser` used to
raise `ParserError` there, which aborts the parse and leaves `server.py` with
one diagnostic and no tree — every other error in the file disappears, exactly
the failure mode the previous subsection exists to avoid. It now records a
`NodeError` ("Scalar cannot be accepted here. Object expected") on the property
and skips the value, leaving the stacks as an accepted scalar would, so the
rest of the document is still parsed and still diagnosed.

### Characters pyyaml refuses to read

`yaml.reader` raises `ReaderError` on C1 control bytes (typically mojibake, a
double encoded em-dash) *before* scanning, which would wipe every diagnostic in
the file; the server's YamlDotNet accepts them. `_remove_invalid_characters`
replaces them with a space, one for one, so every reported position still lines
up with the document the client holds.

## 3. Dead fields policy

These were parsed by older Torque versions and are ignored by the server today.
Neither layer accepts them any more — flagging them is the point, so that an
author who copies an old blueprint learns the field does nothing:

| Field | Status |
|---|---|
| `grains.<n>.spec.host` | replaced by `spec.agent`; absent from schema and from `GrainSpecNode` |
| `grains.<n>.spec.agent.image` | ignored by the server; explicitly noted in the `SpecHostNode` docstring |
| `inputs.<n>.display-style` | superseded by `style` (`text`/`radio`/`multi-select`/`duration`) |

`TestSpec2DeadFieldsStayDead` guards `host` and `agent.image`. Do not "fix"
those diagnostics by re-adding the fields.

## 4. Semantic validation rules (`server/validation/bp_v2_validator.py`)

Everything below needs cross-node knowledge, which JSON Schema cannot express
(or, for `mode`, cannot express *per kind* — the schema lists the union of the
allowed values and the server narrows it).

| Rule | Implementation | cs2018 provenance |
|---|---|---|
| A resource requirement has exactly one of `selector` / `reference` | `_validate_resource_requirements` (the schema also has a `oneOf`, which is why this one is duplicated) | `BlueprintResourceRequirementsValidator` |
| A grain defines `agent` **or** `target`, never both | `_validate_agent_and_target_exclusivity` | `GrainAgentValidator` / `GrainTargetValidator` |
| `mode` per kind: terraform `managed`\|`no-termination`; argocd `data` and it is mandatory; any other kind `managed` only | `_validate_grain_mode` + the `grain_modes` / `default_grain_modes` / `kinds_requiring_mode` tables | `GrainModeValidator` options |
| `auto-approve: false` cannot run with `use-storage: false` (the runner must keep the plan while it awaits approval); `use-storage` is read from `spec.agent` or from `spec.target.runner-configuration-override` | `_validate_auto_approve_requires_storage` + `_get_use_storage_property` | `GrainHostValidator` |
| Workflow `scope` in `space`\|`env`\|`env_resource`; `space` scope allows manual triggers only; `manual` takes no `event`/`cron`; `event` requires `event` and forbids `cron`; `cron` requires `cron` and forbids `event`; `timeout` is an integer >= 5 (minutes) — `scope` and `timeout` are now pinned in the schema as well (section 10), so those two are duplicated on purpose like the resource-requirement `oneOf`; the trigger combinations still need cross-node knowledge | `_validate_workflow*`, `workflow_scopes`, `workflow_min_timeout` | `WorkflowYamlValidator` |
| Duplicate grain outputs / duplicate grain spec inputs / duplicate or unknown or self `depends-on` entries | `_validate_no_duplicates_in_grain_outputs`, `_validate_no_duplicates_in_grain_spec`, `_validate_no_duplicates_in_deps`, `_validate_grain_dep_exists` | pre-existing |

Conventions worth keeping:

* Anything containing `{{` is skipped (`_is_expression`) — a Liquid value cannot
  be checked statically, and guessing produces false errors.
* Read values through `_prop_value` / `_prop_text` and report through
  `_report`/`_anchor`, which fall back to the first node that actually has a
  position. Half-typed documents have nodes without values and values without
  positions (see section 6).
* `_check_unused_blueprint_inputs` is the only *warning*; everything else is an
  error. It is a regex scan over the raw document text, so a reference from a
  free-form section still counts as usage. It has to accept every spelling an
  input can be reached by (`_input_usage_regex`): `.inputs.NAME`, `inputs.NAME`,
  `.inputs["NAME"]`, `.inputs.["NAME"]`, `inputs["NAME"]`, either quote style.
  Matching only the first of those produced a false warning on roughly every
  input of every real-world blueprint that uses names with spaces.

## 5. Expression (Liquid) validation

Runs as a visitor over every `TextNode` with `allow_vars`, matching `{{ ... }}`.
Errors are attached to the node (`tree.errors`), not to the validator's
diagnostic list — `server.py` merges both before publishing.

The path is split by `split_expression_path`, not by `str.split(".")`: a
bracket access is one segment and its quotes are stripped, so `.inputs.Name`,
`.inputs["Name"]` and `.inputs.["Name"]` all yield `['inputs', 'Name']` and
every check below works on plain names. Torque's own test blueprints use the
`.inputs.["X"]` spelling, so all three have to be accepted.

* Allowed prefixes (`ExpressionValidationVisitor.prefixes`) — the root keys of
  the server's `PostCreationContext`: `inputs`, `grains`, `params`, `resources`,
  `env_references`, `management_server`, plus `bindings` **only when the
  blueprint declares a `workflow` scope** (`_get_prefixes`; the server hands a
  non-workflow blueprint an empty `BindingsContext`). Only `inputs` and `grains`
  are checked further; the rest are accepted as-is.
* **The leading dot is a convention, not syntax.** DotLiquid's own path scanner
  (`\[[^\]]+\]|[\w\-]+\??`) simply drops it, so `{{ inputs.X }}` ==
  `{{ .inputs.X }}` and `{{ envId }}` == `{{ .envId }}`. An expression whose
  first segment is a prefix is validated identically either way; a single
  segment that is not a prefix must be one of the reserved variables
  (case-insensitive): `envId`, `environmentName`, `blueprintName`, `ownerEmail`,
  `accountName`, `spaceName`, `sandboxId`. Anything else is flagged.
* Filters: the full DotLiquid/Shopify standard set plus Torque's customs
  (`key_access`, `json`, `json_escape`, `resource_property`, `resource_object`)
  — `standard_filters` + `torque_filters`. DotLiquid applies filters in a chain,
  so **any number of pipes** is allowed and each stage is checked separately. A
  filter may carry an argument (`| key_access: "hostname"`), so only the part
  before `:` is matched against the filter list.
* `.inputs.<name>` must be exactly two segments and the input must be declared
  (compared against the *unquoted* name, so bracket forms work).
* `.grains.<g>.<prop>` where `<prop>` is one of `outputs`, `scripts`,
  `activities`, `is_active` (the members of the server's `GrainsValues`). The
  referenced grain must exist and must not be the referring grain itself.
* When referenced from inside a grain, the target must be in that grain's
  **transitive `depends-on` closure** (`_get_dependencies_closure`), not only in
  its direct `depends-on`: cs2018's `GetAllDependentGrains` recurses. The
  closure is cycle-safe and cached per visitor.
* `.grains.<g>.activities.<deploy|destroy>.commands.<cmd>.outputs.<out>` is the
  context built for a shell grain's named commands. The segments are checked,
  and when the command is resolvable in the tree the output name is checked
  against its `outputs:` list; an unresolvable intermediate node is tolerated
  silently, because the document is validated while it is being typed.
* Bare `.grains.<g>.outputs` (nothing after it) is valid: it is the JSON of all
  the grain's outputs, normally piped into `key_access`. `.grains.<g>.is_active`
  is likewise a leaf.

### Where an expression error is reported

A node's `text` is the scalar's *value*, not the document's characters: a block
scalar (`command: |`, `command: >` — the usual shape of a shell grain) holds its
whole dedented body, and a multi-line quoted scalar holds the folded value. An
offset into either therefore says nothing about the line the expression is
written on; reporting `start_pos[1] + offset` put the squiggle on the block
header's line at a column far past its end (a real corpus file reported
`236:154` for an expression on line 239).

So the visitor takes the `Document` and, whenever the node spans more than one
line (`end_pos[0] != start_pos[0]`, or the text holds a newline),
`_resolve_positions_in_document` looks the matched `{{ ... }}` up in the
document's own lines between `start_pos[0]` and `end_pos[0]`. Matches are
consumed in document order, so two identical bad expressions in one block are
reported on their two separate lines. The reported range always stays inside the
line it starts on. A single-line scalar keeps the plain arithmetic (its value
does start where the node starts, plus one for an opening quote — `node.style`),
and that arithmetic is also the fallback whenever the document is unavailable
(the visitor still works with `document=None`) or the match cannot be located in
it — for example an expression a folded scalar broke across lines.

## 6. Testing

| File | Covers |
|---|---|
| `tests/test_spec2.py` | tree key coverage per section (a modern blueprint must parse with zero unknown-key errors), dead fields, expression rules |
| `tests/test_spec2_semantics.py` | the section 4 rules, plus validator/parser robustness |
| `tests/test_spec2_real_world.py` | the findings of a scan of 454 real-world blueprints: flow style YAML, unprintable bytes, bracket/dotless expression forms, the activities output path, transitive `depends-on`, the filter set, Liquid in `authentication`, and the unused-input regex |
| `tests/test_spec2_optional_and_label_values.py` | the section 8 input changes at the *schema* layer (`inputs.<n>.optional`, `target-filters.labels[].values`) |
| `tests/test_spec2_names.py` | the section 9 name rules: the grain-name regex is enforced, any input/output name is accepted, and no entry escapes validation by having an unusual name |
| `tests/test_spec2_required_parity.py` | the section 10 mandatory-field rules and the `if`/`then` conditionals, plus the assertion that `$schema` is draft-07 (without which those conditionals are dead) |
| `tests/test_spec2_closed_objects.py` | the section 10 closed objects: every server class with a fixed key set is `additionalProperties: false` here too |
| `tests/test_spec2_server_parity.py` | the rest of section 10: Terraform backend per-type fields, workflow `timeout` and `scope`, the full trigger-event list |
| `tests/test_schema_fixtures.py` | the fixture corpus below: minimal blueprints that must validate, minimal defects that must still be reported, and the coverage link back to the real corpus |
| `tests/test_schema_syntax.py` | the file itself: no duplicate keys in any object (`json.load` keeps the last duplicate silently, so nothing else would notice), UTF-8 without BOM, LF endings, draft-07 declared and meta-valid, every `$ref` resolvable |

The reference corpus is the six internal ZeroTouch blueprint repositories, and
454 is its size when walked with the canonical prune list (`.git`,
`node_modules`, `__pycache__`, `.venv`, `.tmp`) — earlier notes saying 452 or 453
came from scans that pruned differently. The corpus tooling that produces those
findings lives in [`tools/blueprint-corpus/`](../tools/blueprint-corpus/README.md).

The robustness tests exist because of one property that must never be broken:
**a half-typed document must not crash `validate()`**. `_validate` in
`server/server.py` catches the exception, logs it, and publishes the
`diagnostics` list as it stands — which at that point is empty. So a single
`AttributeError` on an unfinished `spec:` silently wipes *all* diagnostics for
the file, including the ones the user was about to act on. Every new validation
must therefore tolerate `None` nodes, `None` values and missing positions, and
should come with a "does not crash / does not hide other diagnostics" test.
`TestValidatorRobustness` and `TestParserRobustness` pin the cases found so far
(empty `spec:`, empty grain body, a `.grains.<g>.scripts...` reference to a
grain that declares no `scripts:`, variable-like keys in free-form sections,
`Union`-annotated properties); the suite is green, and it must stay that way.

Running the suite (CI: `.github/workflows/ci.yml`, ubuntu-22.04, Python 3.7 --
20.04 was retired by GitHub, and 22.04 is the newest image still offering a 3.7
build, matching the pinned `pygls`):

```
python -m unittest discover tests/
```

The pinned stack is Python 3.6/3.7 era (`pygls==0.11.3`, `pyyaml==5.4.1`,
`ruamel.yaml==0.17.10`). On a modern machine, create a Python 3.7 virtualenv and
`pip install -r server/requirements.txt` — a current Python will not install
these pins. Note that `ruamel.yaml` and `tabulate` are needed for the *whole*
suite to import (`tests/test_validator.py` reaches `server/utils/yaml_utils.py`);
the spec2 modules themselves only need pygls and pyyaml. The schema-layer test
modules (sections 8 and 9) drive the JSON Schema directly through
`jsonschema.Draft7Validator`, and `jsonschema` is *not* pulled in by
`server/requirements.txt` — CI installs it explicitly. Leave it unpinned: pip
honours `Requires-Python`, so 3.7 resolves to 4.17.3, the last release before
jsonschema dropped 3.7.

### Spell-checking

Nothing in this pipeline read prose until 2026-09: super-linter validates JSON
*syntax*, and every test here is behavioural, so four spelling and hyphenation
defects shipped in the schema's `description` strings — which is to say, in the
hover text a blueprint author reads — before a human noticed. The `spellcheck`
job in `.github/workflows/ci.yml` now runs `codespell` over the whole tree.

Its configuration lives in the repo-root `.codespellrc` so that a bare
`codespell` run locally is exactly the CI run. A genuine false positive gets an
inline `codespell:ignore <word>` on its own line (in Markdown, inside an HTML
comment at the end of that line) — see the 0.3.3 changelog quote in section 7.
Do **not** reach for `ignore-words-list` to silence one: that suppresses the
word repo-wide and forever, which is how the next typo gets through.

### The schema fixture corpus

Everything above tests the *server* layer. The schema itself was pinned only
where someone had thought to write a test, which leaves the two defects that
matter unguarded: a shape real blueprints depend on stops validating, and a dead
key starts being silently accepted. `tests/schema_fixtures/` closes that, with
minimal, generic blueprints standing in for the real ones — representative of
what they use, carrying none of their content.

Four things are enforced, by `tests/test_schema_fixtures.py`:

* `valid/<feature>.yaml` — one feature family per file, must validate with
  **zero** errors. This is also where the schema-only constructs live: the grain
  kinds (`kubernetes`, `argocd`, `opentofu`, `terragrunt`, `aws-cdk`), input
  types (`dictionary`, `file`, `parameter`, `resource`) and sections
  (`resources`, `tfvars-files`, `provider-overrides`, grain `condition`) that no
  local blueprint uses and that nothing else would notice disappearing.
* `invalid/<defect>.yaml` — must produce **at least one** error, and every
  `# expect-error: <substring>` line in its header must match some message.
  These are the dead keys the corpus scan found in the wild (`display-name`,
  grain `timeout`, `activities.teardown`, `tf-tags-disabled`, …) plus the
  removed enum members and the tightenings. A fixture here that produces no
  error at all is the failure the corpus exists to catch. Matching runs against
  **all** messages, nested `oneOf`/`anyOf` sub-errors included — most of these
  keys sit inside a combinator, where the outermost message is only ever "is not
  valid under any of the given schemas".
* `required-paths.txt` — the 232 schema-accepted key paths that the 528 local
  spec2 blueprints actually use, normalized (`<name>` for a user-chosen key,
  `[]` for a list level). The union of the paths exercised by the valid fixtures
  must cover all of them. That check is what makes "based on the real
  blueprints" a property CI verifies rather than a claim in a commit message.
* **The schema's own surface** — all 352 declared properties, all 115 enum
  members and all 58 definitions reachable from the root have to be exercised by
  some valid fixture. `required-paths.txt` is the floor the real blueprints set;
  this is the ceiling. Nothing is listed by hand: `PathClassifier` reports what
  the fixtures reached and `SchemaEnumerator` reports what the schema declares,
  and the difference is the failure message, one `subTest` per uncovered
  element. So the counts above are descriptions of today's schema, not constants
  anywhere in the code: a property added to the schema without a fixture fails CI
  the day it lands, named (`BlueprintInputObject.searchable`,
  `WorkflowTrigger.event = 'Tag Updates Detected'`). Something **no valid
  document can reach** is excused in the `EXCLUDED_*` sets in the test module
  with a reason — unreachable is the bar, not inconvenient, and "writing that
  fixture is work" is not a reason. All three sets are empty, and an exclusion
  that no longer matches the schema is itself a failure.

To add a fixture, drop a file in `valid/` (start it with `spec_version`, keep it
minimal, open it with a comment saying what it pins) or in `invalid/` with its
`# expect-error:` lines — match on the distinctive fragment of the message, not
on a whole sentence. A failing run prints every message with its JSON path, so
the expectation can be read straight off it. Expectations are matched
case-insensitively against all messages; where jsonschema itself reworded a
message between the two versions CI runs (`minItems` became "should be
non-empty" in 4.18, having been "is too short"), pin the offending *value*
rather than the wording.

`required-paths.txt` is regenerated with the classifier in
[`tools/blueprint-corpus/classify_corpus_paths.py`](../tools/blueprint-corpus/classify_corpus_paths.py),
which walks documents alongside the schema and sorts each key path into
accepted / rejected / free-form. It needs the local corpus, which is deliberately
not in this repository:

```
python tools/blueprint-corpus/classify_corpus_paths.py \
    client/schemas/blueprint-spec2-schema.json <out-dir> <corpus-root>...
```

The same run writes the `rejected-paths.txt` that the `invalid/` fixtures come
from. The test imports that script by file path — `blueprint-corpus` has a
hyphen, so it is not a package — and reuses its `PathClassifier` for the
coverage check, so CI normalizes paths with the same code that produced the
file. `SchemaEnumerator` lives in the same module for the same reason: it has
to walk the schema by exactly the classifier's rules (`$ref` renaming,
combinator spreading, `<name>` for user-chosen keys) or the two sides would
disagree about what a property is called and the coverage check would compare
nothing to nothing.

The module imports only `yaml`, `jsonschema` and the standard library, so it
runs on the pinned 3.7 stack and on a current Python alike. The 3.7 `test` job
picks it up through `discover`; the separate `schema-fixtures` job in
`.github/workflows/ci.yml` runs it on 3.12 with nothing installed but those two
libraries.

## 7. Known gaps

Two things that surprise people and are easy to mistake for bugs:

* **The schema is not wired up automatically.** `addSchemasToYamlConfig`
  (`client/src/yamlHelper.ts`) copies the existing global `yaml.schemas` value
  and writes it straight back — it adds no mapping for
  `blueprint-spec2-schema.json`, and the helper that would
  (`addSchemaToConfigAtScope`) is unused. Automatic schema configuration was
  dropped in 0.3.3 — the changelog entry reads
  "get rid of schemas configutation" (sic) — and nothing replaced it, <!-- codespell:ignore configutation -->
  so the shipped schema file is currently the reference the server model is
  synced against rather than something the user's editor picks up on its own.
  To exercise a schema change, associate it by hand — a `yaml.schemas` entry or
  a `# yaml-language-server: $schema=` comment in the test document.
* **A schema constraint may be missing on purpose.** Grain `mode` is the
  standing example: the schema lists the union of the allowed values and only
  the language server narrows it per kind (section 4). That is the layer split
  of section 1 in practice — when a value's legality depends on *context*,
  pinning it in the schema too would double-report the same mistake and force
  every future value change to land in two places. Two more, from the parity
  pass of section 10: `provider-type` and `cloud-providers` stay **soft** enums,
  because the server does not check them against a closed set and a strict enum
  here would reject a provider Torque accepts; and Terraform backend
  `skip-region-validation` is deliberately not required for `s3`, because on the
  server it is a non-nullable bool whose mandatory check can never fire. Workflow
  `scope` used to be the example in this slot — it carried no `enum`, only prose
  in its `description`. It now has a strict `enum` (`space` / `env` /
  `env_resource`): those are a closed server-side `EntityType`, not a
  context-dependent judgement, so the overlap with `_validate_workflow_scope` is
  worth it. Before "fixing" an apparently lax schema rule, check whether the
  language server already covers it — or whether the server itself is lax.

## 8. September 2026 backend changes to `inputs`

Three changes landed in cs2018 after the 2026-08-24 sync (see *Source
freshness* in section 1). All of them are about blueprint **inputs**, and all
of them were re-verified against cs2018 `origin/main` c0f49bd04d and cs2018-ui
9fe9e4b01b on 2026-09-14/15.

### 8.1 `inputs.<name>.optional` (cs2018 7571846285, 2026-08-30)

A `bool?` — tri-state, and the unset state is *not* the same as `false`.

| | |
|---|---|
| Type | `bool?` (unset / `true` / `false`) |
| Meaningful for | `string` and `dictionary` inputs only |
| Ignored for | `agent`, `credentials`, `file`, `parameter`, `input-source`, `target`, `resource` |

Two blueprint-level consequences:

* `optional: true` combined with a `pattern` that rejects the empty string is a
  **blueprint validation error** — `BLUEPRINT_INPUT_OPTIONAL_CONFLICTS_WITH_PATTERN`.
  The two statements contradict each other: the input may be left blank, and
  blank is not an accepted value. Note the asymmetry — a pattern the server
  cannot evaluate (an invalid or unresolvable regex) never fails the blueprint
  on *this* rule; it simply cannot be shown to conflict.
* `optional: false` rejects an empty value at launch —
  `BLUEPRINT_INPUTS_EMPTY_VALUES_NOT_ALLOWED`.

### 8.2 Required-ness on the launch form

The launch form decides required-ness itself, in cs2018-ui
`portal/src/forms/common_logic/helpers.tsx` (`isInputMandatory`, changed
2026-08-30):

```
if (input.optional === true)  return false;
if (input.optional === false) return true;
if (!input.has_default_value && !input.pattern) return true;   // has_default_value = Default is not null, so default: "" counts
return patternRejectsEmptyValue(input.pattern);
```

What that means in practice, and it is the part that surprises people: **when
`optional` is unset, having a default makes the input optional — including an
empty default.** `default: ""` sets `has_default_value`, because the check is
"is Default non-null", not "is Default non-empty". So the older rule of thumb
"an input is required iff it has no pattern" is wrong in both directions: a
defaulted input with no pattern is *optional*, and an input with a pattern is
required only when that pattern actually rejects the empty string. An explicit
`optional` overrides all of it.

### 8.3 Server-side `pattern` enforcement (cs2018 8d62b1be5d, 2026-09-09)

`pattern` used to be a launch-form-only affordance. Torque now validates launch
values against it server-side too:

| Situation | Error |
|---|---|
| Value does not match `pattern` | `BLUEPRINT_INPUT_VALUE_DOES_NOT_MATCH_PATTERN`, using `validation-description` as the message when one is present |
| `pattern` is not a valid regex | `BLUEPRINT_INPUT_PATTERN_IS_NOT_A_VALID_REGEX` |

Two details worth knowing before tightening anything in the schema:

* The dialect is **JavaScript**, and a `/.../flags` literal is accepted as well
  as a bare pattern body. Validating `pattern` as a .NET or Python regex in this
  extension would produce false errors.
* `pattern` and `validation-description` are **Liquid-templated**. They are
  resolved over the input's `depends-on` inputs (of type `string`, `parameter`,
  `input-source` or `resource`) and over space parameters, through a new
  endpoint `catalog/any_blueprint/inputs_patterns`. So a `pattern` containing
  `{{ }}` is not statically checkable — the same reason `_is_expression` makes
  the validator skip Liquid values everywhere else (section 4).

### 8.4 `inputs.<name>.target-filters.labels[].values` (cs2018 eec4e2859a, 2026-09-10)

A `string[]` alternative to the existing scalar `value` on a target-filter
label. The matching semantics are AND across labels, OR within one label:

* a target must carry **all** the listed labels, and
* for each label, its value must match **any** entry of that label's `values`,
* compared **case-insensitively**.

A single label entry carrying both `value` and `values` is an error —
`BLUEPRINT_INPUT_TARGET_FILTER_LABEL_WITH_VALUE_AND_VALUES`. That is a
one-of-two-keys rule on a single node, so it is expressible in the schema (like
the resource-requirement `oneOf` of section 4) and does not need cross-node
knowledge.

## 9. What a name may be

The `inputs`, `grains` and `outputs` maps are keyed by author-chosen names, and
the server's rules for them are asymmetric (cs2018 `origin/main` c0f49bd04d):

| Name | Server rule | Source |
|---|---|---|
| Grain name | must match `^[a-zA-Z0-9 \-_]+$` — letters, digits, space, dash, underscore — with **no length limit** | `BaseGrainValidator.cs` |
| Input name | none at all: any non-empty string | — |
| Output name | none at all: any non-empty string | — |

The schema mirrors exactly that: it constrains grain names to the regex above
and accepts any input or output name.

It did not always. The schema used to demand **3–45 characters** of every one of
those names, which was wrong twice over. It was wrong on the facts — the server
imposes no length bound on grains and no rule whatsoever on inputs and outputs,
and real blueprints in the corpus are full of short and exotic names (`OS`,
`db`, `id`, `Ethernet1/1 Port Group`). And it was wrong in its *failure mode*,
which is the part worth remembering:

> A `propertyNames` constraint only constrains the name. The schema applied to
> the **value** is chosen by `properties` / `patternProperties`, and these maps
> declared no `additionalProperties`, so an entry whose name missed the pattern
> matched no value schema at all and was simply **not validated** — no error
> about the name, and no checking of the body either.

So the very entries most likely to be malformed were the ones that escaped
every check. Closing the maps is what turns that silence into a diagnostic, and
it is the same reasoning as the closed key set of section 2: a schema that
quietly skips input it does not recognise is worse than one that rejects it.

## 10. Server parity pass (2026-09-15)

A full sweep of the schema against the Torque server — cs2018 `origin/main`
**c0f49bd04d** — for the three things a JSON Schema can state and the server
already decides on its own: which fields are **mandatory**, which objects have a
**closed** key set, and which values are a **closed** set. Sections 8 and 9 are
the parts of that sweep that touched `inputs` and names; this is the rest. Every
rule below names the server type that decides it, and each one is pinned by
`tests/test_spec2_required_parity.py`, `tests/test_spec2_closed_objects.py` or
`tests/test_spec2_server_parity.py` (section 6).

### 10.1 The draft upgrade that had to come first

The schema declared **draft-06** while using `if`/`then`/`else` in five places
(the approval-channel and toleration conditionals). Those keywords are
**draft-07**: a compliant draft-06 validator does not know them, and an unknown
keyword is not an error but a no-op — so all five rules were **dead**, silently,
for every consumer.

The proof is a pair of documents that should have failed and did not: an
approval channel with `type: group` and no `groups`, and a toleration with
`operator: Equal` and no `key`/`value`. Each produced **0 errors under
`Draft6Validator` and 1 under `Draft7Validator`** — same schema, same document,
the declared draft being the only difference.

`$schema` now says draft-07, and every validator in `tests/` and `tools/` is a
`Draft7Validator` so that CI evaluates the file the way the consumers do. Both
consumers do support draft-07: yaml-language-server (behind
`redhat.vscode-yaml`, the extension's declared dependency — section 1) and
cs2018-ui's `monaco-yaml` 4.0.0-alpha.2, which wraps that same engine. The
corollary is a ceiling as well as a floor: a draft-2019+ keyword would be just
as dead, and must not be used here.

### 10.2 Required-field parity

| Rule | Server source |
|---|---|
| A source needs `store` **or** `path` | `GrainSourceValidator` — it reports only when *both* are missing, so the schema models an `anyOf`, not two required keys |
| A **family member** source needs both `store` and `path` | `BlueprintFamilyValidator` |
| `agent` needs `name` | `GrainAgentValidator` (`GRAIN_HOST_MISSING_NAME`) |
| An `instructions` path must end in `.md`; a `layout` path must end in `.yaml` — **not** `.yml` — both case-insensitively | `InstructionsSourceValidator` / `LayoutSourceValidator`: `Path.GetExtension(...).Equals(".md"` / `".yaml", OrdinalIgnoreCase)` |
| Every `template` placeholder needs a `path`, and it may not be blank | `BlueprintTemplateValidator` |
| An approval channel's approver list (`groups` / `users` / `names`, per channel type) holds at least one entry | `GrainConditionsValidator` (`GRAIN_APPROVAL_CHANNEL_MUST_HAVE_AT_LEAST_ONE_APPROVER`) |
| A `parameter` input needs `parameter-name` | `BlueprintInputsValidator` |
| A cloudformation grain needs `region`, and a host: one of `authentication` / `agent` / `target` | `CloudFormationGrainValidator` (`isHostDefined = agent != null \|\| target != null`) + `GrainAwsRegionValidator` |
| Workflow `timeout`: resolved as Liquid, then parsed as an integer >= 5 (minutes) | `WorkflowYamlValidator.ValidateTimeout` — modelled as `integer >= 5` \| a numeric string \| a `{{ }}` string, because the server resolves the value before parsing it and all three spellings are legal input |
| Workflow `scope` is exactly `EntityType`: `space` / `env` / `env_resource`, compared case-insensitively (the schema pins the canonical lowercase spellings) | `WorkflowYamlValidator.ValidateScope` |
| Workflow trigger events are the 15 members of `EnvironmentWorkflowEvent`, including `Tag Updates Detected`, which the schema lacked | `EnvironmentWorkflowEvent` |

### 10.3 Terraform backend

`TerraformBackendValidator` + `BackendType`. `type` is mandatory and is a closed
set — `s3`, `gcs`, `azurerm`, `http`, `cloud`, `remote` — and each type then has
its own mandatory fields, written as one `if`/`then` per type (which is what
10.1 had to unblock):

| `type` | Mandatory beyond `type` |
|---|---|
| `s3` | `bucket`, `region` |
| `azurerm` | `storage-account-name`, `container-name` |
| `gcs` | `bucket` |
| `http` | `base-address` |
| `remote` | `organization`, and a non-empty `workspaces` list whose every entry carries `name` or `prefix` (`hostname` and `token` are passed with `isMandatory: false` — optional) |
| `cloud` | nothing |

One field is deliberately *not* required: `skip-region-validation` is handed to
the server's mandatory-field check for `s3`, but it is a **non-nullable bool**
there, so its `ToString()` is never empty and the check can never fire.
Requiring it in the schema would reject documents Torque accepts — the general
rule of section 7's second bullet, in its most literal form.

### 10.4 Closed objects

An object the server deserializes into a fixed key set must be
`additionalProperties: false` here, or a dead key is silently accepted by the
extension and silently dropped by the server — the dead-fields reasoning of
section 3, applied to the schema layer:

| Schema definition | Server class |
|---|---|
| `Backend` (and its `workspaces` items: `name` / `prefix` / `project` / `tags`) | `GrainBackendYaml` / `RemoteWorkspace` |
| `TemplateStorage` | `TemplateStorageYaml` |
| `GrainTag` | `GrainTagsYaml` |
| `SourceFileObject` — exactly one key, `source` | `TfVarsFileYaml`, `HelmValuesFileYaml`, `WorkspaceDirectoriesYaml`, `OpenTofuVarsFileYaml` |
| `ScriptObject` / `ScriptOutputsObject` | `ScriptYaml` |

`ResourceSelectorBaseObject` is the one definition left open, by design: it is
an `allOf` base that other definitions extend, so closing it would reject the
extending keys.

### 10.5 Audits that found nothing to change

Worth recording, because a later reader would otherwise redo them:

* **Two-way key audit** — every `YamlMember` alias on the server's YAML types
  against every property in the schema, in both directions. The only server-side
  extras are dead constants with no `YamlMember` at all (`compute-service`,
  `cloud-account`, `role-arn`, `external-id`): nothing deserializes them, so they
  are not keys.
* All **32** input-source override keys match the provider constants exactly.
* **0** unreachable definitions in the schema.
* Input types, input styles, output kinds, trigger types, condition and channel
  types and credential providers are all already exact.
* Deliberately **not** added: the `GrainKind` members `mock-terraform` and
  `mock-helm`, which are internal test kinds — documenting them in hover text
  would advertise them to blueprint authors.
* `provider-type` and `cloud-providers` stay **soft** enums — an `anyOf` of the
  known list and a plain `string`, so the known values still complete and an
  unknown one still validates. The server never checks either against a closed
  set, so a strict `enum` would invent a rule Torque does not have.

### 10.6 Evidence that none of this rejects working blueprints

Every change above tightens the schema, and a tightening is a potential false
positive on somebody's working blueprint. So the **528** sanitized local
blueprints (`tools/blueprint-corpus/`) were re-validated after *every* change,
not once at the end: **412** fully clean, **0** crashes, **727** findings — all
of them already-KNOWN categories, **0** NEW. A single NEW finding would have
meant a rule that rejects a blueprint Torque runs today, and would have been
reverted rather than explained.

## 11. Descriptions pass (2026-09-15)

Section 10 made the schema's *shapes* match the server. This pass did the same
for its *words*. A description is not decoration here: it is the hover text a
blueprint author reads instead of the docs, and a wrong one is worse than a
missing one — it is a rule the extension invents. So all **177** existing
descriptions were re-read claim by claim against cs2018 `origin/main`
**c0f49bd04d** and the cs2018-ui source, and every claim that could not be
traced to a line of server code was either corrected or dropped.

Thirteen were wrong. Grouped by what they got wrong:

| Was | Is |
|---|---|
| The input object's summary still described the pre-2026-08-30 required-ness rule | It defers to `optional` / `default` / `pattern` (section 8.1–8.3) |
| `depends-on` was documented for dropdown-ish inputs only | `InputTypesWithDependsOnSupport` includes plain **string** inputs |
| A single-value `allowed-values` list left the user to pick it | That one value is **auto-selected**, unless the input's style is multi-select |
| `resource-selector` read as required on a resource input | It is optional; the server never requires it |
| Workflow `label-selector` described as an alias of `labels-selector` | It is a **legacy alias of `resource-types`** — the AutoMapper profile reads `ResourceTypes = LabelSelector ?? ResourceTypes` |
| `target` documented with a scalar short form | It has none: the property carries only `[YamlMember]`, there is no type converter, and **607 of 607** real usages write the object. The schema's `string` branch is removed and the tree model now types it as the object alone (section 2) |
| `spec.version` and `tf-version` read as two settings | They are the **same** setting (declaring both is an error), and `version` is exclusive with `binary` |
| `when` described as skipping the grain | It skips the grain **and every grain that depends on it** |
| `auto-tag`'s default unstated | It defaults to **true** |
| `namespace` and `target-namespace` blurred together | Spelled apart: where the grain's own release lives vs. where it deploys |
| Launch-form input types left implicit | Spelled out |

The other half of the pass was coverage: **136** properties had no description
at all — the Environment-as-Code section, every backend and template-storage
field, the kubernetes and docker runner permissions, runner configuration
overrides, approval conditions, shell `files` entries, all **32** input-source
overrides, the resource-selector stubs and the customization UI contract. Every
property in the file now carries one, which is also what makes the next audit
cheap: a property with no description is now a visible hole, not the norm.

One key was added rather than described: `customization.layout.exclude.resources`,
which the UI reads (`resources_layout_section.tsx`) and the schema did not have.
It hides one resource instance by exact name, without hiding its type or its
grain — the sibling of the `grains` and `resource-types` exclusions. It comes
with a fixture, like every other key (section 6).

**The rule this pass leaves behind.** A description that states a default, makes
an "ignored" / "required" / "only" claim, or quotes a number must cite the server
type that decides it — otherwise it must be re-verified from scratch at the next
schema sync, because nothing would record where it came from. That citation goes
in the provenance table in section 12, **not** in the schema: the schema file is
customer-facing (section 12 explains why) and carries no server identifiers, so a
`$comment` is no longer an acceptable home for one.

A layering note that explains an oddity of the file: a `description` written
next to a `$ref` is **ignored by a draft-07 validator** (the sibling keywords of
a `$ref` are), but yaml-language-server does show it on hover, and it is the
only way to say what a shared definition means *at this particular use site*.
The file therefore uses them deliberately — they are hover text, never a
constraint, and no test may rely on one being evaluated.

## 12. Provenance of schema rules

`client/schemas/blueprint-spec2-schema.json` is **customer-facing**. The Torque
web UI fetches it live from this repository's public master branch and renders
its descriptions on hover, and anyone with the raw URL can read the whole file.
Every `title`, `description` and `$comment` in it must therefore read as product
documentation: no server class or method names, no error codes, no source-file
names or line numbers, no internal tooling or repository names, and no counts
taken from our private blueprint corpus. `tests/test_schema_public_voice.py`
enforces this, and the `schema-fixtures` CI job runs it on every push.

That leaves a real need unmet, though: a rule in the schema is only trustworthy
if somebody can trace it back to the server code that decides it. Until this
pass, that trace lived in the `$comment`s themselves. It lives here now. The
table below is the verbatim content of every `$comment` the file carried before
the wording pass, split into the rule (which stayed in the schema, reworded in
plain product language) and the server source (which was removed from the schema
and is recorded only here). When a rule is next re-verified, this is the column
to start from.

### 12.1 Blueprint top level

| Schema location | Rule | Server source |
|---|---|---|
| `workflow.scope` | Accepts exactly `space`, `env` and `env_resource`, matched case-insensitively. | `WorkflowYamlValidator.ValidateScope`, `EntityType` / `BoundedEntityTypeConsts`, `StringComparer.OrdinalIgnoreCase` |
| `workflow.label-selector` | Legacy alias of `resource-types`; when both are set, `label-selector` wins. | `BlueprintsV2AutoMapperProfile` maps `ResourceTypes = LabelSelector ?? ResourceTypes` |
| `workflow.timeout` | The value is resolved as a Liquid pattern and then has to parse as an integer >= 5. The three branches are a plain integer, the same written as a string, and a Liquid expression whose resolved value is checked. | `WorkflowYamlValidator.ValidateTimeout`, `int.TryParse(...) >= 5`, `BlueprintErrors.TIMEOUT_INVALID_VALUE` |
| `instructions.source` | The path's extension must be `.md`, compared case-insensitively. The pattern sits on this use site rather than on the shared store-file source definition, which `layout` reuses with a different extension rule. | `InstructionsSourceValidator.PathExtraValidations`, `Path.GetExtension` with `OrdinalIgnoreCase`, `INSTRUCTIONS_FILE_MUST_BE_A_MARKDOWN` |
| `layout.source` | The path's extension must be `.yaml`, compared case-insensitively; `.yml` is rejected. | `LayoutSourceValidator.PathExtraValidations`, `LAYOUT_FILE_MUST_BE_A_YAML` |
| `family.members.*.source` | Both `store` and `path` are mandatory — stricter than a grain source, which needs only one of the two. | `BlueprintFamilyValidator`, `FAMILY_MEMBER_SOURCE_STORE_MISSING`, `FAMILY_MEMBER_SOURCE_PATH_MISSING` |
| `template.placeholders[]` | A placeholder whose `path` is null or whitespace is rejected. | `BlueprintTemplateValidator`, `BLUEPRINT_TEMPLATE_PLACEHOLDER_PATH_REQUIRED` |

### 12.2 Grains

| Schema location | Rule | Server source |
|---|---|---|
| `GrainObject` | A CloudFormation grain needs `region`, plus either `authentication` or a host (`agent` or `target`). | `CloudFormationGrainValidator`, `GrainAwsRegionValidator`, `CLOUDFORMATION_REGION_MISSING`, `CLOUDFORMATION_GRAIN_CREDENTIALS_AND_AGENT_ARE_MISSING` |
| `GrainObject.when` | An unmet `when` moves the grain to Skipped and skips its dependents recursively. | `GrainStateCommandHandler`, `IsWhenConditionMet`, `MarkChildrenAsSkippedRecursively` |
| `GrainSpecObject.target` | There is no scalar short form; a scalar is not read at all, so the object form is the only accepted shape. | `GrainSpecYaml.Target` carries only `[YamlMember]` — no `[YamlShortSyntax]` and no type converter; 607 of 607 usages in the local corpus write the object form |
| `GrainSpecObject.version` | `version` and the grain-level `tf-version` are the same setting, so declaring both is an error, and neither may be combined with `binary`. | `TERRAFORM_USAGE_OF_BOTH_VERSION_FIELDS_NOT_ALLOWED`, `TERRAFORM_INVALID_EXECUTABLE_PARAMETERS` |
| `GrainSpecHostObject` | An agent must carry a `name`. | `GrainAgentValidator`, `GRAIN_HOST_MISSING_NAME` |
| `GrainSpecSourceObject` | An error is raised only when both `store` and `path` are missing. With a `store` and no `path` the asset comes from the repository root; with a `path` and no `store` the path must be a public URL. | `GrainSourceValidator`, `GRAIN_SOURCE_STORE_AND_PATH_MISSING` |
| `SourceFileObject` | Holds exactly one member, `source`. | `TfVarsFileYaml`, `HelmValuesFileYaml`, `WorkspaceDirectoriesYaml` and `OpenTofuVarsFileYaml` in `GrainYaml.cs` |
| `GrainTag` | Exactly `auto-tag` and `disable-tags-for`. | `GrainTagsYaml` (`GrainYaml.cs`) |
| `GrainConditionChannelApproversObject` | At least one approver is required, so an empty list and an empty string are both rejected. | `GrainConditionsValidator.ValidateApprovers`, `GRAIN_APPROVAL_CHANNEL_MUST_HAVE_AT_LEAST_ONE_APPROVER` |

### 12.3 Terraform backend and template storage

| Schema location | Rule | Server source |
|---|---|---|
| `Backend` (key set) | A fixed set of 13 keys; anything else is dropped silently on read, which is why the schema reports the extras itself. `type` accepts only the listed values. | `GrainBackendYaml` (`GrainYaml.cs`), `BackendType` (`BackendType.cs`), `TerraformBackendValidator` |
| `Backend` (per-type fields) | `type` is mandatory, then one check per type reports the missing mandatory fields. `skip-region-validation` is checked for s3 but as a non-nullable bool's `ToString()`, so it can never be missing and stays optional. For `remote` only `organization` and `workspaces` are mandatory. For `cloud` nothing is mandatory, which is why the schema has no `cloud` branch. | `TerraformBackendValidator`, `TERRAFORM_BACKEND_TYPE_FIELD_MANDATORY`, `ValidateXxxFields`, `TERRAFORM_BACKEND_FIELD_MANDATORY`, `ValidateBackendField(..., isMandatory: false)` for `hostname` / `token` / `organization` |
| `Backend.workspaces[]` | Exactly `name`, `prefix`, `project` and `tags` (a string-to-string dictionary). | `GrainBackendYaml.RemoteWorkspace` |
| `TemplateStorage` | Exactly `bucket-name`, `key-prefix` and `region`. | `TemplateStorageYaml` (`GrainYaml.cs`) |

### 12.4 Inputs

| Schema location | Rule | Server source |
|---|---|---|
| `BlueprintInputObject` | Every input of type `parameter` must set `parameter-name`. | `BlueprintInputsValidator`, `FIELD_VALUE_MISSING_AT_PATH` reported on `parameter-name` |
| `BlueprintInputObject.depends-on` | Supported for string, parameter, input-source and resource inputs. | `InputTypesWithDependsOnSupport = String, Parameter, InputSource, Resource` |
| `BlueprintInputObject.resource-selector` | Never required. | No server error exists for its absence |

### 12.5 Resource selectors — schema mechanics, no server source

These three `$comment`s cited no server code to begin with: they describe how
this file is put together, which is exactly what a `$comment` is still allowed to
say. They were left as they were.

| Schema location | Rule | Server source |
|---|---|---|
| `ResourceSelectorBaseObject` | Shared selection criteria, inherited via `allOf`; deliberately leaves `additionalProperties` unset so the inheritors can close themselves. | — |
| `ResourceSelectorObject` | Extends the base with `quantity`. The inherited properties are re-listed with empty schemas so `additionalProperties: false` does not reject them — draft-07 `additionalProperties` is blind to properties coming from a `$ref`. On a move to draft 2019-09 or later, drop the stubs and use `unevaluatedProperties: false`. | — |
| `BlueprintInputResourceSelectorObject` | Extends the base adding nothing of its own — notably no `quantity`, which is a resource-requirement concern. Same stub trick as above. | — |
