"""Name rules of the top-level maps, mirrored from the server (cs2018 origin/main
c0f49bd04d, 2026-09-14):

- grain names: BaseGrainValidator.cs - ``^[a-zA-Z0-9 \\-_]+$`` (letters, digits,
  space, dash, underscore), NO length limit.
- input names and output names: no server rule at all - any non-empty string.

The schema used to demand 3-45 characters of a narrower alphabet and, because the
`inputs` / `grains` / `outputs` maps had no `additionalProperties`, an entry whose
name missed the pattern was silently skipped instead of validated. Real, working
blueprints name inputs 'OS' or 'Ethernet1/1 Port Group', grains 'db', outputs
'id' - none of those were being checked at all.
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


class TestInputNames(unittest.TestCase):
    def test_two_character_input_name_is_valid(self):
        self.assertEqual([], schema_errors("spec_version: 2\ninputs:\n  OS:\n    type: string\n"))

    def test_two_character_input_name_is_validated_not_skipped(self):
        errors = schema_errors("spec_version: 2\ninputs:\n  OS:\n    type: string\n    bogus: 1\n")
        self.assertTrue(errors, "an off-pattern name must still have its object validated")

    def test_input_name_with_slash_is_valid(self):
        self.assertEqual(
            [],
            schema_errors("spec_version: 2\ninputs:\n  Ethernet1/1 Port Group:\n    type: string\n"),
        )

    def test_input_name_with_slash_is_validated_not_skipped(self):
        errors = schema_errors(
            "spec_version: 2\ninputs:\n  Ethernet1/1 Port Group:\n    type: string\n    bogus: 1\n"
        )
        self.assertTrue(errors)


class TestGrainNames(unittest.TestCase):
    GRAIN = "    kind: terraform\n    spec:\n      source:\n        path: modules/app\n"

    def test_two_character_grain_name_is_valid(self):
        self.assertEqual([], schema_errors("spec_version: 2\ngrains:\n  db:\n" + self.GRAIN))

    def test_two_character_grain_name_is_validated_not_skipped(self):
        errors = schema_errors(
            "spec_version: 2\ngrains:\n  db:\n" + self.GRAIN + "      bogus: true\n"
        )
        self.assertTrue(errors)

    def test_grain_name_with_illegal_character_is_rejected(self):
        # the server rejects anything outside letters, digits, space, dash, underscore
        errors = schema_errors("spec_version: 2\ngrains:\n  bad/name:\n" + self.GRAIN)
        self.assertTrue(errors)

    def test_long_grain_name_is_valid(self):
        name = "a" * 60  # the server has no length limit
        self.assertEqual([], schema_errors("spec_version: 2\ngrains:\n  %s:\n%s" % (name, self.GRAIN)))


class TestOutputNames(unittest.TestCase):
    def test_two_character_output_name_is_valid(self):
        self.assertEqual([], schema_errors("spec_version: 2\noutputs:\n  id:\n    value: '1'\n"))

    def test_two_character_output_name_is_validated_not_skipped(self):
        errors = schema_errors("spec_version: 2\noutputs:\n  id:\n    value: '1'\n    bogus: 1\n")
        self.assertTrue(errors)


class TestOtherNameMaps(unittest.TestCase):
    """env_references and resources: the server has no name rule for either, and the
    schema's old {3,45} pattern with no additionalProperties skipped off-pattern entries."""

    def test_two_character_env_reference_name_is_valid(self):
        self.assertEqual(
            [],
            schema_errors("spec_version: 2\nenv_references:\n  db:\n    labels-selector: 'env=dev'\n"),
        )

    def test_two_character_env_reference_name_is_validated_not_skipped(self):
        errors = schema_errors(
            "spec_version: 2\nenv_references:\n  db:\n    labels-selector: 'env=dev'\n    bogus: 1\n"
        )
        self.assertTrue(errors)

    def test_two_character_resource_name_is_validated_not_skipped(self):
        errors = schema_errors("spec_version: 2\nresources:\n  vm:\n    bogus: 1\n")
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
