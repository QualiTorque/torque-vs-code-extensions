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
  annotated with `typing.Union` (e.g. `target`, `deployment-engine`,
  `reference`). A `Union` is not a class, so `issubclass` raises on it —
  `server/ats/trees/common.py` walks `__args__` instead, in `_get_seq_nodes`,
  in the `allow_vars` propagation and in `PropertyNode.__getattr__`.

### Free-form sections

`FreeFormNode` / `FreeFormProperty` model sections that are free-form on the
server side too, and would otherwise drown the user in false "unknown key"
errors: `customization`, an inline ansible `inventory-file`, terraform provider
`attributes`, input-source `overrides`, `environment.tags` / `labels`,
`family.members`, backend workspace `tags`. They accept any nested mapping,
sequence or scalar without validating names.

They are also deliberately **not expression-validated**
(`ExpressionValidationVisitor.visit_node` returns early on them, skipping the
whole subtree): the `{{ }}` inside them belongs to another dialect — the launch
form uses the UI's own template syntax (`{{ inputs.x }}`, no leading dot) and an
ansible inventory may hold Jinja. Validating them as grain Liquid would be
wrong. See `test_free_form_sections_not_expression_validated`.

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
| Workflow `scope` in `space`\|`env`\|`env_resource`; `space` scope allows manual triggers only; `manual` takes no `event`/`cron`; `event` requires `event` and forbids `cron`; `cron` requires `cron` and forbids `event`; `timeout` is an integer >= 5 (minutes) | `_validate_workflow*`, `workflow_scopes`, `workflow_min_timeout` | `WorkflowYamlValidator` |
| Duplicate grain outputs / duplicate grain spec inputs / duplicate or unknown or self `depends-on` entries | `_validate_no_duplicates_in_grain_outputs`, `_validate_no_duplicates_in_grain_spec`, `_validate_no_duplicates_in_deps`, `_validate_grain_dep_exists` | pre-existing |

Conventions worth keeping:

* Anything containing `{{` is skipped (`_is_expression`) — a Liquid value cannot
  be checked statically, and guessing produces false errors.
* Read values through `_prop_value` / `_prop_text` and report through
  `_report`/`_anchor`, which fall back to the first node that actually has a
  position. Half-typed documents have nodes without values and values without
  positions (see section 6).
* `_check_unused_blueprint_inputs` is the only *warning*; everything else is an
  error. It is a regex scan over the raw document lines, so a reference from a
  free-form section still counts as usage.

## 5. Expression (Liquid) validation

Runs as a visitor over every `TextNode` with `allow_vars`, matching `{{ ... }}`.
Errors are attached to the node (`tree.errors`), not to the validator's
diagnostic list — `server.py` merges both before publishing.

* Allowed prefixes (`ExpressionValidationVisitor.prefixes`): `.inputs`,
  `.grains`, `.params`, `.resources`, `.env_references`. Only `.inputs` and
  `.grains` are checked further (`_expression_parts_validate` branches on those
  two only); `.params`, `.resources` and `.env_references` are accepted as-is.
* An expression without a leading dot must be one of the reserved variables
  (case-insensitive): `envId`, `environmentName`, `blueprintName`, `ownerEmail`,
  `accountName`, `spaceName`, `sandboxId`.
* One pipe at most; filters: `downcase`, `strip`, `key_access`. A filter may
  carry an argument (`| key_access: "hostname"`), so only the part before `:`
  is matched against the filter list.
* `.inputs.<name>` must be exactly two parts and the input must be declared.
* `.grains.<g>.outputs.<name>` / `.grains.<g>.scripts.<hook>.outputs.<name>`:
  the referenced grain must exist, must not be the referring grain itself, and
  — when referenced from inside a grain — **must be listed in `depends-on`**.
* Bare `.grains.<g>.outputs` (nothing after it) is valid: it is the JSON of all
  the grain's outputs, normally piped into `key_access`.

## 6. Testing

| File | Covers |
|---|---|
| `tests/test_spec2.py` | tree key coverage per section (a modern blueprint must parse with zero unknown-key errors), dead fields, expression rules |
| `tests/test_spec2_semantics.py` | the section 4 rules, plus validator/parser robustness |

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

Running the suite (CI: `.github/workflows/ci.yml`, ubuntu-20.04, Python 3.6 and
3.7):

```
python -m unittest discover tests/
```

The pinned stack is Python 3.6/3.7 era (`pygls==0.11.3`, `pyyaml==5.4.1`,
`ruamel.yaml==0.17.10`). On a modern machine, create a Python 3.7 virtualenv and
`pip install -r server/requirements.txt` — a current Python will not install
these pins. Note that `ruamel.yaml` and `tabulate` are needed for the *whole*
suite to import (`tests/test_validator.py` reaches `server/utils/yaml_utils.py`);
the spec2 modules themselves only need pygls and pyyaml.

## 7. Known gaps

Two things that surprise people and are easy to mistake for bugs:

* **The schema is not wired up automatically.** `addSchemasToYamlConfig`
  (`client/src/yamlHelper.ts`) copies the existing global `yaml.schemas` value
  and writes it straight back — it adds no mapping for
  `blueprint-spec2-schema.json`, and the helper that would
  (`addSchemaToConfigAtScope`) is unused. Automatic schema configuration was
  dropped in 0.3.3 ("get rid of schemas configutation") and nothing replaced it,
  so the shipped schema file is currently the reference the server model is
  synced against rather than something the user's editor picks up on its own.
  To exercise a schema change, associate it by hand — a `yaml.schemas` entry or
  a `# yaml-language-server: $schema=` comment in the test document.
* **A schema constraint may be missing on purpose.** Workflow `scope`, for
  example, has no `enum` in the schema; the allowed values live only in its
  `description` and are enforced by `_validate_workflow_scope`. That is the
  layer split of section 1 in practice: when a value's legality depends on
  context (here, which triggers the scope permits), pinning it in the schema
  too would double-report the same mistake and force every future value change
  to land in two places. Before "fixing" an apparently lax schema rule, check
  whether the language server already covers it.
