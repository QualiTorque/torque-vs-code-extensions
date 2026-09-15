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
        # a cloudformation grain also needs region and agent (or authentication/target) - see test_spec2_required_parity
        ok = ("      region: my-region\n      agent:\n        name: agent-1\n"
              "      template-storage:\n        bucket-name: my-bucket\n        region: my-region\n        key-prefix: envs/\n")
        self.assertEqual([], schema_errors(terraform_grain(ok).replace("terraform", "cloudformation")))
        self.assertTrue(schema_errors(terraform_grain(ok + "        bogus: 1\n").replace("terraform", "cloudformation")))

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
            "            prefix: app-\n            project: my-project\n            tags:\n              team: platform\n"
        )
        self.assertEqual([], schema_errors(terraform_grain(ok)))
        self.assertTrue(schema_errors(terraform_grain(ok.replace("            prefix: app-\n", "            prefix: app-\n            bogus: 1\n"))))

    def test_vars_file_entries_are_closed(self):
        ok = "      tfvars-files:\n        - source:\n            store: config\n            path: prod.tfvars\n"
        self.assertEqual([], schema_errors(terraform_grain(ok)))
        self.assertTrue(schema_errors(terraform_grain(ok + "          bogus: 1\n")))


def workflow(fields):
    return "spec_version: 2\nworkflow:\n" + "".join("  %s\n" % f for f in fields) + (
        "grains:\n  step:\n    kind: shell\n    spec:\n      agent:\n        name: agent-1\n"
        "      activities:\n        deploy:\n          commands:\n            - echo hi\n"
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
        self.assertEqual([], schema_errors(workflow(["scope: env", "timeout: '{{ .inputs.minutes }}'"])))


class TestWorkflowScope(unittest.TestCase):
    def test_server_scopes_are_accepted(self):
        for scope in ("space", "env", "env_resource"):
            self.assertEqual([], schema_errors(workflow(["scope: %s" % scope])), scope)

    def test_other_scope_is_rejected(self):
        self.assertTrue(schema_errors(workflow(["scope: environment"])))


class TestWorkflowTriggerEvents(unittest.TestCase):
    def test_tag_updates_detected_is_accepted(self):
        doc = workflow(["scope: env", "triggers:", "  - type: event", "    event:", "      - Tag Updates Detected"])
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
            "            prefix: app-\n            project: my-project\n            tags:\n              team: platform\n"
        )
        self.assertEqual([], self.unknown_keys(doc))

    def test_template_storage_fields(self):
        doc = terraform_grain(
            "      template-storage:\n        bucket-name: my-bucket\n        region: my-region\n        key-prefix: envs/\n"
        ).replace("terraform", "cloudformation")
        self.assertEqual([], self.unknown_keys(doc))


if __name__ == "__main__":
    unittest.main()
