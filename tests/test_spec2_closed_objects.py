"""Objects the Torque server deserializes with a closed key set must be closed in
the schema too (`additionalProperties: false`), otherwise a dead key is silently
accepted instead of reported - the dead-field policy of docs/spec2-language-support.md.

Script hooks (`grains.<name>.spec.scripts.<hook>`) are `ScriptYaml` on the server:
`source` + `arguments` (+ `outputs` for the helm/aws-cdk hooks). Nothing else is
read; the deserializer runs with IgnoreUnmatchedProperties(), so a stray key such
as `files:` under a hook is dropped without a word. 13 local blueprints carry
exactly that mistake (the files they list are never delivered), and the schema
let it through because the hook objects were not closed.
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


TERRAFORM = """spec_version: 2
grains:
  app:
    kind: terraform
    spec:
      source:
        path: modules/app
      scripts:
        pre-tf-init:
          source:
            store: scripts
            path: init.sh
{extra}"""

HELM = """spec_version: 2
grains:
  chart:
    kind: helm
    spec:
      source:
        path: charts/app
      target:
        name: my-cluster
      scripts:
        post-helm-install:
          source:
            store: scripts
            path: after.sh
          outputs:
            - endpoint
{extra}"""


class TestScriptHookObjectsAreClosed(unittest.TestCase):
    def test_well_formed_hook_is_valid(self):
        self.assertEqual([], schema_errors(TERRAFORM.format(extra="")))
        self.assertEqual([], schema_errors(HELM.format(extra="")))

    def test_files_under_a_hook_is_reported(self):
        errors = schema_errors(
            TERRAFORM.format(
                extra="          files:\n            - source: scripts\n              path: helper.py\n"
            )
        )
        self.assertTrue(
            errors, "a dead 'files' key under a script hook must be reported"
        )

    def test_unknown_key_under_an_outputs_hook_is_reported(self):
        errors = schema_errors(HELM.format(extra="          bogus: true\n"))
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
