"""Mandatory-field and conditional rules mirrored from the Torque server (cs2018
origin/main c0f49bd04d), and the draft upgrade that makes them enforceable.

The schema used `if`/`then`/`else` (approval channels, tolerations) while
declaring draft-06, where those keywords do not exist - every compliant
validator ignored them, so the rules were dead. The schema now declares draft-07
and all validators use Draft7Validator.

Rules, each with its server source:
- GrainSourceValidator: a source needs `store` or `path` (STORE_AND_PATH_MISSING);
  a family member source needs both (FAMILY_MEMBER_SOURCE_STORE/PATH_MISSING).
- GrainAgentValidator: `agent` needs `name` (GRAIN_HOST_MISSING_NAME).
- InstructionsSourceValidator / LayoutSourceValidator: instructions file must be
  `.md`, layout file must be `.yaml` (extension compared case-insensitively).
- BlueprintTemplateValidator: each placeholder needs `path`.
- GrainConditionsValidator: an approval channel needs at least one approver of
  its kind (groups / users / names).
- Toleration: operator Equal needs key and value (kubernetes semantics, already
  written as if/then in the schema - now live).
- BlueprintInputsValidator: a `parameter` input needs `parameter-name`
  (FIELD_VALUE_MISSING_AT_PATH).
- CloudFormationGrainValidator + GrainAwsRegionValidator: a cloudformation grain
  needs `region` and either `authentication` or `agent`.
- TerraformBackendValidator: `type` is mandatory; per type the server requires
  s3: bucket, region | azurerm: storage-account-name, container-name |
  gcs: bucket | http: base-address | remote: organization and a non-empty
  workspaces list whose entries carry name or prefix (hostname and token are
  optional) | cloud: nothing beyond type.
- CloudFormationGrainValidator counts `target` as a host too (isHostDefined =
  agent != null || target != null).
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
    RAW_SCHEMA = json.load(_f)
SCHEMA = Draft7Validator(RAW_SCHEMA)


def errors(doc):
    return [e.message for e in SCHEMA.iter_errors(yaml.safe_load(doc))]


def grain(kind, spec):
    body = "".join("      %s\n" % line for line in spec.splitlines())
    return "spec_version: 2\ngrains:\n  app:\n    kind: %s\n    spec:\n%s" % (kind, body)


TF_SOURCE = "source:\n  path: modules/app\n"


class TestDraft(unittest.TestCase):
    def test_schema_declares_draft_07(self):
        # if/then/else are draft-07 keywords; under draft-06 they are silently ignored
        self.assertIn("draft-07", RAW_SCHEMA["$schema"])


class TestSources(unittest.TestCase):
    def test_store_or_path_is_enough(self):
        self.assertEqual([], errors(grain("terraform", "source:\n  path: modules/app\n")))
        self.assertEqual([], errors(grain("terraform", "source:\n  store: modules\n")))

    def test_source_without_store_and_path_is_rejected(self):
        self.assertTrue(errors(grain("terraform", "source:\n  branch: main\n")))

    def test_family_member_source_needs_store_and_path(self):
        ok = "spec_version: 2\nfamily:\n  members:\n    member-a:\n      source:\n        store: blueprints\n        path: a.yaml\n"
        self.assertEqual([], errors(ok))
        self.assertTrue(errors(ok.replace("        store: blueprints\n", "")))
        self.assertTrue(errors(ok.replace("        path: a.yaml\n", "")))


class TestAgent(unittest.TestCase):
    def test_agent_needs_name(self):
        self.assertEqual([], errors(grain("terraform", TF_SOURCE + "agent:\n  name: agent-1\n")))
        self.assertTrue(errors(grain("terraform", TF_SOURCE + "agent:\n  use-storage: true\n")))


class TestFileExtensions(unittest.TestCase):
    def test_instructions_file_must_be_markdown(self):
        doc = "spec_version: 2\ninstructions:\n  source:\n    store: docs\n    path: guide.%s\n"
        self.assertEqual([], errors(doc % "md"))
        self.assertEqual([], errors(doc % "MD"))
        self.assertTrue(errors(doc % "txt"))

    def test_layout_file_must_be_yaml(self):
        doc = "spec_version: 2\nlayout:\n  source:\n    store: layouts\n    path: dashboard.%s\n"
        self.assertEqual([], errors(doc % "yaml"))
        self.assertTrue(errors(doc % "yml"))
        self.assertTrue(errors(doc % "json"))


class TestTemplatePlaceholders(unittest.TestCase):
    def test_placeholder_needs_path(self):
        ok = "spec_version: 2\ntemplate:\n  placeholders:\n    - path: inputs.region\n      hint: pick one\n"
        self.assertEqual([], errors(ok))
        self.assertTrue(errors(ok.replace("    - path: inputs.region\n      hint", "    - hint")))


def approval_grain(channel_lines):
    channel = "".join("          %s\n" % l for l in channel_lines)
    return (
        "spec_version: 2\ngrains:\n  app:\n    kind: terraform\n    condition:\n      - type: approval\n"
        "        message: approve?\n        channels:\n        - type: %s\n%s" % (channel_lines[0], channel)
    ).replace("        - type: %s\n          %s\n" % (channel_lines[0], channel_lines[0]), "        - type: %s\n" % channel_lines[0]) + "    spec:\n      source:\n        path: modules/app\n"


class TestApprovalChannels(unittest.TestCase):
    def channel(self, ctype, extra):
        return (
            "spec_version: 2\ngrains:\n  app:\n    kind: terraform\n    condition:\n      - type: approval\n"
            "        message: approve?\n        channels:\n          - type: %s\n%s"
            "    spec:\n      source:\n        path: modules/app\n" % (ctype, "".join("            %s\n" % l for l in extra))
        )

    def test_each_channel_type_needs_its_approvers(self):
        self.assertEqual([], errors(self.channel("group", ["groups:", "  - platform-team"])))
        self.assertEqual([], errors(self.channel("user", ["users:", "  - someone@example.invalid"])))
        self.assertEqual([], errors(self.channel("account_channels", ["names:", "  - ops"])))
        self.assertTrue(errors(self.channel("group", [])), "group channel without groups must be rejected")
        self.assertTrue(errors(self.channel("group", ["groups: []"])))
        self.assertTrue(errors(self.channel("user", [])))
        self.assertTrue(errors(self.channel("account_channels", [])))


class TestTolerations(unittest.TestCase):
    def test_equal_operator_needs_key_and_value(self):
        base = TF_SOURCE + "agent:\n  name: agent-1\n  kubernetes:\n    tolerations:\n      - operator: %s\n%s"
        self.assertEqual([], errors(grain("terraform", base % ("Equal", "        key: dedicated\n        value: gpu\n"))))
        self.assertEqual([], errors(grain("terraform", base % ("Exists", ""))))
        self.assertTrue(errors(grain("terraform", base % ("Equal", ""))))


class TestParameterInput(unittest.TestCase):
    def test_parameter_input_needs_parameter_name(self):
        doc = "spec_version: 2\ninputs:\n  Region:\n    type: parameter\n%s"
        self.assertEqual([], errors(doc % "    parameter-name: default-region\n"))
        self.assertTrue(errors(doc % ""))


class TestCloudFormation(unittest.TestCase):
    CFN = "source:\n  path: templates/stack.yaml\n"

    def test_region_and_credentials_or_agent(self):
        self.assertEqual([], errors(grain("cloudformation", self.CFN + "region: my-region\nagent:\n  name: agent-1\n")))
        self.assertEqual([], errors(grain("cloudformation", self.CFN + "region: my-region\nauthentication:\n  - '{{ .inputs.creds }}'\n")))
        self.assertTrue(errors(grain("cloudformation", self.CFN + "agent:\n  name: agent-1\n")), "region is mandatory")
        self.assertTrue(errors(grain("cloudformation", self.CFN + "region: my-region\n")), "authentication or agent is mandatory")

    def test_other_kinds_do_not_need_region(self):
        self.assertEqual([], errors(grain("terraform", TF_SOURCE)))


class TestBackend(unittest.TestCase):
    def backend(self, lines):
        return grain("terraform", TF_SOURCE + "backend:\n" + "".join("  %s\n" % l for l in lines))

    def test_type_is_mandatory(self):
        self.assertTrue(errors(self.backend(["bucket: my-state"])))

    def test_s3_needs_bucket_and_region(self):
        self.assertEqual([], errors(self.backend(["type: s3", "bucket: my-state", "region: my-region"])))
        self.assertTrue(errors(self.backend(["type: s3", "region: my-region"])))
        self.assertTrue(errors(self.backend(["type: s3", "bucket: my-state"])))

    def test_azurerm_needs_storage_account_and_container(self):
        self.assertEqual([], errors(self.backend(["type: azurerm", "storage-account-name: acct", "container-name: tfstate"])))
        self.assertTrue(errors(self.backend(["type: azurerm", "container-name: tfstate"])))

    def test_gcs_needs_bucket(self):
        self.assertEqual([], errors(self.backend(["type: gcs", "bucket: my-state"])))
        self.assertTrue(errors(self.backend(["type: gcs"])))

    def test_http_needs_base_address(self):
        self.assertEqual([], errors(self.backend(["type: http", "base-address: https://state.example.invalid"])))
        self.assertTrue(errors(self.backend(["type: http"])))

    def test_remote_needs_organization_and_workspaces(self):
        # ValidateTerraformRemoteFields: hostname and token are passed with isMandatory: false
        # ("Optional fields"); organization and a non-empty workspaces list are mandatory, and the
        # server's own Validate_RemoteBackend_Mandatory_Fields_Pass has neither hostname nor token.
        ok = ["type: remote", "hostname: app.example.invalid", "token: '{{ .inputs.token }}'", "organization: my-org",
              "workspaces:", "  - name: my-workspace"]
        self.assertEqual([], errors(self.backend(ok)))
        self.assertEqual([], errors(self.backend(ok[:-1] + ["  - prefix: app-"])))
        self.assertEqual([], errors(self.backend([l for l in ok if not l.startswith(("hostname", "token"))])))
        self.assertTrue(errors(self.backend(ok[:-2])), "workspaces are mandatory for remote")
        self.assertTrue(errors(self.backend(ok[:-1] + ["  - project: p"])), "a remote workspace needs name or prefix")
        self.assertTrue(errors(self.backend([l for l in ok if not l.startswith("organization")])), "organization is mandatory")

    def test_cloud_has_no_mandatory_fields_beyond_type(self):
        # ValidateTerraformCloudFields passes hostname, token and organization with isMandatory: false,
        # and ValidateCloudWorkspacesField returns when workspaces are absent.
        self.assertEqual([], errors(self.backend(["type: cloud"])))
        self.assertEqual([], errors(self.backend(["type: cloud", "hostname: app.example.invalid",
                                                   "token: '{{ .inputs.token }}'", "organization: my-org"])))


if __name__ == "__main__":
    unittest.main()
