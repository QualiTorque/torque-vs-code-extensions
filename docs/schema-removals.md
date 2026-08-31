# Schema removals — request for approval

**Subject:** keys and values removed from the Torque blueprint `spec_version: 2`
JSON schema and from the extension's language server.
**Decision needed:** approve, or choose one of the two alternatives in
[What we are asking you to approve](#what-we-are-asking-you-to-approve).
**The gate is the merge, not the release.** Production Torque's web UI fetches
this schema live from `master` of this repo, so merging is what makes it live —
see [Where this schema is actually consumed](#where-this-schema-is-actually-consumed).

## Executive summary

- We removed 5 schema values/properties, tightened 2 shapes, deleted 7 internal
  schema definitions, and dropped 3 dead keys from the extension's language
  server. Every removed item was verified against the Torque server source to be
  something Torque does not read.
- **Nothing about deployment or runtime behavior changes.** What Torque
  *accepts* is decided by C# validators on the server, which do not use this
  file at all. No environment behaves differently; nothing needs to be
  un-deployed.
- **But the schema is live in production Torque today.** The Torque web UI
  fetches it over HTTP from `master` of this repo and feeds it to the YAML editor
  in its designer. The change reaches all Torque users within minutes of the
  merge — no extension release, no version pin.
- Measured over 527 real spec2 blueprints, **12 files (2.3%) will show a new
  error in the editor**. In all 12 the error is correct: it points at a key
  Torque already ignores today.
- **We are asking you to approve Option A** (ship the removals as implemented),
  plus a separate process recommendation: `master` of this file is effectively
  production and should be pinned.

## What changes, and where it lands

The file is `client/schemas/blueprint-spec2-schema.json`. It is a JSON Schema —
it describes which keys and values are allowed in a blueprint YAML document, and
carries the hover text an author sees for each one. It drives editor validation,
completion and hover in two places: production Torque's own designer, and the VS
Code extension.

It is **not** what Torque enforces. The Torque server validates blueprints with
its own C# validators; this file never reaches it. So no removal can change how
a blueprint deploys, how a running environment behaves, or what Torque accepts
at launch. **The only thing any removal changes is what a blueprint author is
shown while editing.**

Therefore:

| | |
|---|---|
| **Risk of a removal** | a FALSE error — the author is told something is wrong that Torque actually accepts. |
| **Benefit of a removal** | a TRUE error — the author is told a key does nothing, before shipping a silently broken blueprint. |

No removal requires a data migration, a server change, or anything to be
un-deployed. What it does require is awareness that the merge itself is the
deployment.

## Where this schema is actually consumed

| Consumer | How it gets the schema | When a change lands |
|---|---|---|
| **Torque web UI** (production) | `cs2018-ui` wires the file into `monaco-yaml` by URL — `portal/src/components/designer/yaml_view_tabs.tsx:23` and `portal/src/components/new_designer/yaml_view_tabs.tsx:14` both set `uri: "https://raw.githubusercontent.com/QualiTorque/torque-vs-code-extensions/master/client/schemas/blueprint-spec2-schema.json"` with `fileMatch: ["*"]`. There is no inlined copy; the browser fetches it at runtime. | **On merge to `master`.** Minutes, bounded only by raw.githubusercontent and browser caching. No version pin exists. |
| **VS Code extension** | Ships the file, but no longer registers it. CHANGELOG 0.3.3 records "get rid of schemas configutation", and `client/src/yamlHelper.ts::addSchemasToYamlConfig` reads the user's existing `yaml.schemas` setting and writes it back unchanged, adding no mapping. It applies only if a user wires it up by hand (a `yaml.schemas` entry, or a `# yaml-language-server: $schema=` modeline). | On the next extension release, and only for users who wired it up. |
| **Torque server** | **Not at all.** `POST /api/spaces/{space}/validations/blueprints` → `BlueprintValidationController` → `IBlueprintService.ValidateBlueprint` runs the C# validators under `Quali.Colony.Services.Common.Blueprints.V2BlueprintValidation`. A repo-wide search of cs2018 `.cs` sources for `JsonSchema`, `NJsonSchema`, `JSchema`, `blueprint-spec2` and `spec2-schema` returns zero hits, and there is no schema JSON file anywhere in the server. | Never. |

The resulting `spec2BlueprintDiagnosticOptions` is used in **six** UI surfaces:
the old designer's blueprint YAML view, the new designer's blueprint YAML view,
the setup wizard's `view_blueprints.tsx`,
`new_designer/drawers/grain_inventory_tab.tsx`,
`new_designer/side_panel/tabs/reserved_resources_tab.tsx`, and the space-level
custom workflow YAML editor
(`pages/space_level_pages/automation_inventory/workflows_v2/custom_workflow_yaml.tsx`).

The UI code carries its own note on the arrangement:
`// where we take the schema from. if this site is unreachable the schema won't apply..`

## A. Removed values and properties (5 items)

| Item | Evidence it is dead in Torque | Blueprints affected (of 527) |
|---|---|---|
| input `type: execution-host` | `BlueprintInputType` in cs2018 defines exactly `string`, `agent`, `credentials`, `parameter`, `input-source`, `file`, `dictionary`, `target`, `resource`. The server actively **rejects** unknown input types (`BlueprintInputsValidator.ValidateInputTypes` → `BLUEPRINT_INPUT_ILLEGAL_INPUT_TYPE`). | 0 |
| input `type: env` | same as above | 0 |
| grain `kind: arm` | the `GrainKind` enum in cs2018 has `helm`, `terraform`, `terragrunt`, `cloudformation`, `blueprint`, `ansible`, `kubernetes`, `shell`, `cloudshell`, `argocd`, `opentofu`, `aws-cdk` — no `arm`. | 0 |
| `grains.<name>.spec.host` | `GrainSpecYaml` has an `agent` member but no `host`; the blueprint deserializer runs with `IgnoreUnmatchedProperties()`, so the key is silently discarded. | 1 |
| `grains.<name>.spec.agent.image` | the key exists in the YAML model but is referenced nowhere in the server; runner images are chosen by RunnerMgmt's image mapping (`IRunnerImageMapping`). | 0 |

### The one affected blueprint

`vmaas/blueprints/stable/deployments/vcenter-vm-with-network.yaml` — a shell
grain declares **both** `agent: {name: ...}` and `host: {name: ...}` with the
same value. The server drops `host:`, so those two lines already do nothing
today; the grain works because `agent:` is present.

After the change the author sees one error on a line that is already inert. The
fix is to delete two lines. No deployment behavior changes.

### For balance: the same change also added a type

The same commit **added** the input type `dictionary`, which the server does
support and the schema was missing. The type list became more accurate in both
directions, not just shorter.

## B. Tightened shapes (2 items, 0 blueprints affected)

| Item | Before | After | Affected |
|---|---|---|---|
| `provider-overrides` entries | any key was accepted (`additionalProperties: true`, no properties described) | exactly `name`, `source`, `version`, `attributes`, matching cs2018's `TerraformProviderYaml` | 0 of 527 use any other key |
| `source:` blocks under script hooks, `values-files`, `workspace-directories` | a loose object — only `path`/`store` described, nothing required, unknown keys accepted | the standard source object: `path` required, unknown keys rejected | 0 of 527 |

Rationale for the second row: it is the same C# type (`ElementSourceYaml`) at
every one of those locations, so making all four share one shape removes four
independent places where the schema could drift from the server.

### The one place we are deliberately stricter than the server

That second row is worth naming explicitly, because it is the only theoretical
false-error risk in the whole set. The server accepts a source with `store` and
no `path`; it errors only when *both* are missing. Our schema requires `path`
unconditionally. So a blueprint that gave `store` alone would be accepted by
Torque and flagged by our schema.

**0 of 527 blueprints do this**, so there is no measured impact — but this is
the one item where a future blueprint could see an error Torque would not have
raised. If you would rather not carry that risk at all, this single row can be
relaxed to "`path` or `store` required" independently of everything else in this
document.

## C. Internal consolidation (7 definitions deleted, no user-visible effect)

`ScriptSource`, `TfVarsFileSourceObject`, `InstructionsSourceObject`,
`LayoutSourceObject`, `PodLabels`, `PodAnnotations` and `NodeSelector` were
merged into three shared definitions (`GrainSpecSourceObject`,
`StoreFileSourceObject`, `KeyValuePairs`). They were duplicates of each other —
for example `InstructionsSourceObject` and `LayoutSourceObject` were
byte-for-byte the same shape, as were the three pod/label maps.

**These are internal names inside the schema file. They are never anything a
blueprint author types.**

One row of the consolidation is a **loosening**, not a tightening: folding
`TfVarsFileSourceObject` into the shared source object gained it four keys it
did not previously allow (`resource-type`, `name`, `chart-version`,
`path-in-archive`). Those keys are real members of the server's
`ElementSourceYaml`, so the looser shape is the more accurate one — but for
completeness, that row accepts more than it used to, not less.

## D. Also removed from the extension's language server

This is the largest author-visible impact of the whole set.

| Item | Detail | Affected |
|---|---|---|
| `inputs.<name>.display-style` | The **schema** stopped accepting this in July 2024 (commit `c34c14b`, shirel-m, which renamed it to `style`), but the extension's Python language server kept recognizing `display-style` until now — so the extension has contradicted itself for about two years. | **11 of 527** |
| `spec.host`, `agent.image` | removed from the language-server model too, for parity with the schema (item A) | included in the 1 above |

In all 11 blueprints that still use `display-style`, the key is dead: Torque
only reads `style`. The intended presentation style has **never** taken effect
in any of those inputs. These 11 files will show a new error, and in each case
the error is correct and reveals a pre-existing latent bug that nobody could
previously see.

Note that these three keys are language-server items, so they affect VS Code
users only. The schema-side removals (A, B) are the ones that reach the Torque
web UI on merge.

## Measured impact

| | Count |
|---|---|
| Real spec2 blueprints measured | 527 |
| Blueprints that will show a new editor error | **12** (1 × `spec.host`, 11 × `display-style`) |
| Of those, errors that are factually correct | 12 of 12 |
| Blueprints whose deployment behavior changes | 0 |
| Data migrations required | 0 |

## How this was verified

1. **Server source cross-check.** Every claim in sections A–D was read out of the
   Torque server source at `C:\Work3\cs2018` — the actual enum, validator and
   YAML model definitions — not inferred from documentation or from the schema
   itself.
2. **UI consumption cross-check.** The consumer table above was read out of
   `cs2018-ui` at the file and line numbers given, confirming the live fetch from
   `master`, the absence of any inlined copy or version pin, and the six call
   sites.
3. **527-blueprint measurement.** Impact was counted over 527 real spec2
   blueprints from 10 local sources: the six ZeroTouch repos
   (`zero-touch-provisioning`, `zero-touch-automation`,
   `zero-touch-cloud-infra`, `Compute3`, `zt-test`, `vmaas`), plus `Compute`,
   `Compute2`, `torque-tunnel`, and Torque-team-authored generated fixtures in
   cs2018.
4. **Test suite.** 92 tests collected, all passing — including
   `tests/test_spec2_real_world.py`, which pins the behavior of the tightened and
   removed keys so a future contributor cannot silently re-add them.

> The numbers above come from **internal repositories only**. No customer
> blueprints were involved in this measurement.

## What we are asking you to approve

### Option A — remove (what is implemented) — **recommended**

Authors of the 12 affected files see one new error each. Each error is factually
correct and points at a key that does nothing today. Produces the most accurate
editor and the smallest schema.

### Option B — keep accepting the dead keys, flag them as warnings

A JSON Schema cannot express "warning" — both consumers (the Red Hat YAML
extension and `monaco-yaml`) report any schema violation as an error. So this
means re-adding the keys to the schema and having our own language server emit
warnings for them instead. Roughly half a day of work plus tests.

Note the asymmetry this creates now that the web UI is a consumer: warnings from
our language server exist only in VS Code, so the Torque web UI would simply
stop flagging the dead keys altogether.

Result: no new red errors anywhere, but the dead keys stay discoverable in
completion — which is how they spread in the first place.

### Option C — revert the removals entirely

Each removal is independently revertible: re-adding an enum value or a property
is a one-line schema edit, and the relevant commits (`af6394b`, `4852bf2`,
`87ad9d0`) are separable. Cost: the extension and the Torque designer keep
telling authors that dead keys are valid.

### Recommendation

**Option A.** The removals only ever surface pre-existing dead configuration;
the measured blast radius is 12 files out of 527; and every one of those 12
errors is a true statement about how Torque behaves.

Choose **Option B** if your priority is that no existing blueprint shows a new
error at all — that is the trade-off it buys, at the price of keeping dead keys
in completion and of the web UI losing the signal entirely.

## Separate process recommendation: pin this file

This is not part of the approve/reject decision above, and it is not caused by
these removals — but the removals are what surfaced it, and it applies to every
future change to this file.

**`master` of this repo is effectively production for the Torque web UI, and it
is unversioned and unpinned.** Any commit that reaches `master` — including
work-in-progress, an experiment, or a mistake — goes live to all Torque users
within minutes, with no review gate on the Torque side and no way to roll
forward or back per environment. The UI code itself acknowledges the fragility:
if `raw.githubusercontent.com` is unreachable, the schema silently does not
apply.

**Recommendation:** pin the UI's `uri` to a tag or a commit SHA rather than
`master` (a small `cs2018-ui` change in the two `yaml_view_tabs.tsx` files), or
otherwise gate this file as production — for example by serving it from Torque's
own static assets. Either way the file gets a version, and schema changes get an
intentional promotion step instead of landing on merge.

## Rollback

- **The rollback is a revert on `master`.** Because the web UI fetches from
  `master`, reverting the commit there is the rollback, and it propagates on the
  same minutes-scale cache as the change itself. Nothing else has to happen.
- **Per item.** Re-adding an enum value or a property is a one-line edit to
  `client/schemas/blueprint-spec2-schema.json`. The language-server items are a
  one-line edit each to `server/ats/trees/blueprint_v2.py`.
- **Per commit.** The three commits are separable: `af6394b` (schema sync and
  consolidation), `4852bf2` (documentation pass and dead fields), `87ad9d0`
  (language-server parity).
- **No migration.** Nothing is stored, nothing is deployed to a server, nothing
  needs to be un-deployed. VS Code users additionally need the next extension
  release either way, since the extension side is release-gated.

## Adjacent finding — not part of this approval

While confirming how the UI consumes our schema, we found that the **environment
layout** schema used by the same Torque UI is fetched from an individual's
personal GitHub repository:

```
portal/src/components/environment/v2/views/layout_yaml_view.tsx:92
uri: "https://raw.githubusercontent.com/10playqualiyarin/yarin-awesome-repo/refs/heads/master/layout_schema.json"
```

Production depending on a personal repository is an ownership and supply-chain
risk: the repository is outside the organization's control and can be renamed,
made private, or deleted by its owner. It is worth raising now because the same
class of problem already affects this work — the last extension release was made
by someone who has since left the company.

Flagged for follow-up. It is independent of the removals in this document and
needs no decision here.
