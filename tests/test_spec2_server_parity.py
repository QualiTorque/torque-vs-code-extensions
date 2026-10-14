"""Schema shapes brought to exact parity with the Torque server (cs2018 origin/main
c0f49bd04d, 2026-09-14). Each class names the server source it mirrors.

- Closed objects: TemplateStorageYaml (bucket-name, key-prefix, region),
  GrainTagsYaml (auto-tag, disable-tags-for), GrainBackendYaml (13 keys, with
  RemoteWorkspace items name/prefix/project/tags) and the four *-files entries
  (TfVarsFileYaml etc.: exactly one key, `source`). All are fixed key sets that
  the deserializer would silently prune, so the schema must report extras.
- workflow.timeout: WorkflowYamlValidator.ValidateTimeout - a Liquid-resolvable
  string that must parse as an integer >= 5 (BlueprintErrors.TIMEOUT_INVALID_VALUE).
- workflow.scope: WorkflowYamlValidator.ValidateScope - one of EntityType
  (space, env, env_resource); the server compares case-insensitively, the schema
  pins the canonical lowercase spelling.
- Workflow trigger events: EnvironmentWorkflowEvent has 15 members including
  "Tag Updates Detected", which the schema lacked.

Re-checked at cs2018 c3635fcfd7 (2026-10-14), which added:
- WorkflowYamlValidator.ValidateWorkflowBlueprint (e07340e3ba, 2026-10-13): any
  number of grains may set `built-in`, but none in a `space`-scoped workflow
  (BUILTIN_ACTION_NOT_SUPPORTED_FOR_WORKFLOW_SCOPE; the old one-built-in-grain
  limit was removed). Two older rules of the same validator, missing from the
  schema until now: an `env_resource` workflow needs a non-empty `resource-types`
  or `label-selector` (RESOURCE_SELECTOR_IS_EMPTY), and a `space` workflow takes
  manual triggers only (ValidateTriggers, AUTOMATIC_WORKFLOW_TRIGGERS_NOT_SUPPORTED).
  Scopes are compared there against the exact lowercase spellings.
- BlueprintGrainsValidator.ValidateGrainsCount (892f5cfd90, 2026-10-06):
  BlueprintLimits.MaxGrainsPerEnvironment = 600 (TOO_MANY_GRAINS); validation
  without nested blueprints loaded counts the top-level entries only.
"""
import io
import json
import os
import unittest

import yaml
from jsonschema import Draft7Validator

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "client", "schemas", "blueprint-spec2-schema.json"
)
with io.open(SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = Draft7Validator(json.load(_f))


def schema_errors(doc):
    return [e.message for e in SCHEMA.iter_errors(yaml.safe_load(doc))]


def terraform_grain(spec_extra):
    return (
        "spec_version: 2\ngrains:\n  app:\n    kind: terraform\n    spec:\n"
        "      source:\n        path: modules/app\n" + spec_extra
    )


class TestClosedObjects(unittest.TestCase):
    def test_template_storage_is_closed(self):
        # a cloudformation grain also needs region and agent (or
        # authentication/target) - see test_spec2_required_parity
        ok = (
            "      region: my-region\n      agent:\n        name: agent-1\n"
            "      template-storage:\n        bucket-name: my-bucket\n"
            "        region: my-region\n        key-prefix: envs/\n"
        )
        self.assertEqual(
            [],
            schema_errors(terraform_grain(ok).replace("terraform", "cloudformation")),
        )
        self.assertTrue(
            schema_errors(
                terraform_grain(ok + "        bogus: 1\n").replace(
                    "terraform", "cloudformation"
                )
            )
        )

    def test_tags_object_is_closed(self):
        ok = "      tags:\n        auto-tag: false\n        disable-tags-for:\n          - aws_s3_bucket\n"
        self.assertEqual([], schema_errors(terraform_grain(ok)))
        self.assertTrue(schema_errors(terraform_grain(ok + "        bogus: 1\n")))

    def test_backend_is_closed(self):
        ok = (
            "      backend:\n        type: s3\n        bucket: my-state\n        region: my-region\n"
            "        key-prefix: app/\n        skip-region-validation: true\n"
        )
        self.assertEqual([], schema_errors(terraform_grain(ok)))
        self.assertTrue(schema_errors(terraform_grain(ok + "        bogus: 1\n")))

    def test_backend_remote_workspaces_are_closed(self):
        ok = (
            "      backend:\n        type: remote\n        hostname: app.example\n        organization: my-org\n"
            "        token: '{{ .inputs.token }}'\n        workspaces:\n          - name: my-workspace\n"
            "            prefix: app-\n            project: my-project\n"
            "            tags:\n              team: platform\n"
        )
        self.assertEqual([], schema_errors(terraform_grain(ok)))
        self.assertTrue(
            schema_errors(
                terraform_grain(
                    ok.replace(
                        "            prefix: app-\n",
                        "            prefix: app-\n            bogus: 1\n",
                    )
                )
            )
        )

    def test_vars_file_entries_are_closed(self):
        ok = "      tfvars-files:\n        - source:\n            store: config\n            path: prod.tfvars\n"
        self.assertEqual([], schema_errors(terraform_grain(ok)))
        self.assertTrue(schema_errors(terraform_grain(ok + "          bogus: 1\n")))


def workflow(fields):
    return (
        "spec_version: 2\nworkflow:\n"
        + "".join("  %s\n" % f for f in fields)
        + (
            "grains:\n  step:\n    kind: shell\n    spec:\n      agent:\n        name: agent-1\n"
            "      activities:\n        deploy:\n          commands:\n            - echo hi\n"
        )
    )


class TestWorkflowTimeout(unittest.TestCase):
    def test_minimum_is_five_minutes(self):
        self.assertEqual([], schema_errors(workflow(["scope: env", "timeout: 5"])))
        self.assertEqual([], schema_errors(workflow(["scope: env", "timeout: '5'"])))
        self.assertEqual([], schema_errors(workflow(["scope: env", "timeout: 120"])))
        self.assertTrue(schema_errors(workflow(["scope: env", "timeout: 4"])))
        self.assertTrue(schema_errors(workflow(["scope: env", "timeout: '0'"])))
        self.assertTrue(schema_errors(workflow(["scope: env", "timeout: abc"])))

    def test_liquid_expression_is_allowed(self):
        self.assertEqual(
            [],
            schema_errors(workflow(["scope: env", "timeout: '{{ .inputs.minutes }}'"])),
        )


class TestWorkflowScope(unittest.TestCase):
    def test_server_scopes_are_accepted(self):
        for fields in (
            ["scope: space"],
            ["scope: env"],
            ["scope: env_resource", "resource-types: aws_instance"],
        ):
            self.assertEqual([], schema_errors(workflow(fields)), fields)

    def test_other_scope_is_rejected(self):
        self.assertTrue(schema_errors(workflow(["scope: environment"])))


class TestResourceScopeNeedsResourceTypes(unittest.TestCase):
    def test_resource_types_or_label_selector(self):
        self.assertEqual(
            [],
            schema_errors(
                workflow(["scope: env_resource", "resource-types: aws_instance"])
            ),
        )
        self.assertEqual(
            [],
            schema_errors(
                workflow(["scope: env_resource", "label-selector: aws_instance"])
            ),
        )

    def test_neither_is_rejected(self):
        self.assertTrue(schema_errors(workflow(["scope: env_resource"])))
        self.assertTrue(
            schema_errors(
                workflow(["scope: env_resource", "labels-selector: tier=dev"])
            ),
            "labels-selector picks blueprints, not resource types",
        )

    def test_empty_is_rejected(self):
        self.assertTrue(
            schema_errors(workflow(["scope: env_resource", "resource-types: ''"]))
        )
        self.assertTrue(
            schema_errors(
                workflow(
                    ["scope: env_resource", "resource-types: ''", "label-selector: ''"]
                )
            )
        )

    def test_other_scopes_do_not_need_it(self):
        for scope in ("space", "env"):
            self.assertEqual([], schema_errors(workflow(["scope: %s" % scope])), scope)


class TestSpaceScopeTakesManualTriggersOnly(unittest.TestCase):
    def test_manual_trigger_is_accepted(self):
        self.assertEqual(
            [],
            schema_errors(workflow(["scope: space", "triggers:", "  - type: manual"])),
        )

    def test_automatic_triggers_are_rejected(self):
        self.assertTrue(
            schema_errors(
                workflow(
                    [
                        "scope: space",
                        "triggers:",
                        "  - type: manual",
                        "  - type: cron",
                        "    cron: 0 3 * * *",
                    ]
                )
            )
        )
        self.assertTrue(
            schema_errors(
                workflow(
                    [
                        "scope: space",
                        "triggers:",
                        "  - type: event",
                        "    event:",
                        "      - Drift Detected",
                    ]
                )
            )
        )

    def test_other_scopes_take_automatic_triggers(self):
        self.assertEqual(
            [],
            schema_errors(
                workflow(
                    ["scope: env", "triggers:", "  - type: cron", "    cron: 0 3 * * *"]
                )
            ),
        )


def builtin_workflow(scope, *grain_flags):
    """A workflow blueprint with one shell grain per entry of `grain_flags`, each
    setting `built-in` to that value (None: not set at all)."""
    grains = ""
    for i, flag in enumerate(grain_flags):
        grains += (
            "  step-%d:\n    kind: shell\n    spec:\n%s      agent:\n        name: agent-1\n"
            "      activities:\n        deploy:\n          commands:\n            - echo hi\n"
            % (i, "" if flag is None else "      built-in: %s\n" % str(flag).lower())
        )
    return "spec_version: 2\nworkflow:\n  scope: %s\ngrains:\n%s" % (scope, grains)


class TestBuiltInGrains(unittest.TestCase):
    def test_several_built_in_grains_are_accepted(self):
        for scope in ("env", "env_resource"):
            doc = builtin_workflow(scope, True, True)
            if scope == "env_resource":
                doc = doc.replace(
                    "  scope: env_resource\n",
                    "  scope: env_resource\n  resource-types: aws_instance\n",
                )
            self.assertEqual([], schema_errors(doc), scope)

    def test_space_scope_takes_no_built_in_grain(self):
        self.assertTrue(schema_errors(builtin_workflow("space", True)))
        self.assertTrue(schema_errors(builtin_workflow("space", None, True)))

    def test_space_scope_without_built_in_is_accepted(self):
        self.assertEqual([], schema_errors(builtin_workflow("space", None)))
        self.assertEqual([], schema_errors(builtin_workflow("space", False, None)))

    def test_null_grain_entry_is_left_alone(self):
        doc = builtin_workflow("space", False) + "  empty-step:\n"
        self.assertEqual([], schema_errors(doc))

    def test_outside_a_workflow_built_in_is_not_restricted(self):
        doc = builtin_workflow("space", True).replace("workflow:\n  scope: space\n", "")
        self.assertEqual([], schema_errors(doc))


class TestGrainCountLimit(unittest.TestCase):
    def grains(self, count):
        body = "".join(
            "  g%d:\n    kind: shell\n    spec:\n      activities:\n        deploy:\n"
            "          commands:\n            - echo hi\n" % i
            for i in range(count)
        )
        return "spec_version: 2\ngrains:\n" + body

    def test_six_hundred_grains_are_accepted(self):
        self.assertEqual([], schema_errors(self.grains(600)))

    def test_six_hundred_and_one_grains_are_rejected(self):
        self.assertTrue(schema_errors(self.grains(601)))


class TestWorkflowTriggerEvents(unittest.TestCase):
    def test_tag_updates_detected_is_accepted(self):
        doc = workflow(
            [
                "scope: env",
                "triggers:",
                "  - type: event",
                "    event:",
                "      - Tag Updates Detected",
            ]
        )
        self.assertEqual([], schema_errors(doc))


class TestLanguageServerParity(unittest.TestCase):
    """Whatever the schema accepts, the language-server tree model must accept too,
    or the editor shows a false 'unknown key' error next to a schema-clean document."""

    def unknown_keys(self, doc):
        from server.ats.parser import Parser

        tree = Parser(doc).parse()
        return [e.message for e in tree.errors if "does not have child" in e.message]

    def test_backend_remote_workspace_fields(self):
        doc = terraform_grain(
            "      backend:\n        type: remote\n        hostname: app.example\n        organization: my-org\n"
            "        token: '{{ .inputs.token }}'\n        workspaces:\n          - name: my-workspace\n"
            "            prefix: app-\n            project: my-project\n"
            "            tags:\n              team: platform\n"
        )
        self.assertEqual([], self.unknown_keys(doc))

    def test_template_storage_fields(self):
        doc = terraform_grain(
            "      template-storage:\n        bucket-name: my-bucket\n"
            "        region: my-region\n        key-prefix: envs/\n"
        ).replace("terraform", "cloudformation")
        self.assertEqual([], self.unknown_keys(doc))


class TestTargetHasNoScalarForm(unittest.TestCase):
    """GrainSpecYaml.Target carries only [YamlMember] - no [YamlShortSyntax] and no type
    converter - so `target: my-target` (a scalar) is not deserialized by the server. 607 of
    607 real usages write the object form. The schema must not advertise a short form."""

    def test_scalar_target_is_rejected(self):
        self.assertTrue(schema_errors(terraform_grain("      target: my-target\n")))

    def test_object_target_is_accepted(self):
        self.assertEqual(
            [],
            schema_errors(terraform_grain("      target:\n        name: my-target\n")),
        )

    def test_language_server_rejects_scalar_target_too(self):
        # both layers must agree, or the editor shows a schema error next to a silent tree model
        from server.ats.parser import Parser

        tree = Parser(terraform_grain("      target: my-target\n")).parse()
        self.assertTrue(
            [e.message for e in tree.errors],
            "the tree model must report a scalar target",
        )
        ok_tree = Parser(
            terraform_grain("      target:\n        name: my-target\n")
        ).parse()
        self.assertEqual([], [e.message for e in ok_tree.errors])


if __name__ == "__main__":
    unittest.main()
