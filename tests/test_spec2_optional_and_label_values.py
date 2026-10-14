"""Backend changes that landed after the 2026-08-24 sync (cs2018 origin/main
c0f49bd04d, 2026-09-14). Each rule is mirrored from the server:

- inputs.<name>.optional (cs2018 7571846285, 2026-08-30): boolean. Only meaningful
  for 'string' and 'dictionary' inputs. 'optional: true' together with a 'pattern'
  that rejects the empty string is a blueprint validation error
  (BLUEPRINT_INPUT_OPTIONAL_CONFLICTS_WITH_PATTERN); a pattern the server cannot
  evaluate must NOT fail the blueprint (PatternEmptyValueEvaluator).
- inputs.<name>.target-filters.labels[].values (cs2018 eec4e2859a, 2026-09-10):
  list alternative to 'value' (a target matches if it carries any of the values);
  giving both 'value' and 'values' on one label is an error
  (BLUEPRINT_INPUT_TARGET_FILTER_LABEL_WITH_VALUE_AND_VALUES).

Both layers are covered: the JSON schema (what the Torque UI and the YAML
extension enforce) and the language server (tree model + semantic diagnostics).
"""
import io
import json
import os
import unittest
from unittest.mock import MagicMock

import yaml
from jsonschema import Draft7Validator
from server.ats.parser import Parser
from server.validation.bp_v2_validator import BlueprintSpec2Validator

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "client", "schemas", "blueprint-spec2-schema.json"
)
with io.open(SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = Draft7Validator(json.load(_f))


def schema_errors(doc):
    return [e.message for e in SCHEMA.iter_errors(yaml.safe_load(doc))]


def language_server(doc):
    """Returns (unknown-key errors from the tree model, semantic diagnostics)."""
    tree = Parser(doc).parse()
    document = MagicMock()
    document.lines = doc.splitlines(True)
    diagnostics = BlueprintSpec2Validator(tree, document).validate()
    unknown = [e.message for e in tree.errors if "does not have child" in e.message]
    return unknown, [d.message for d in diagnostics]


def string_input(*fields):
    return "spec_version: 2\ninputs:\n  My Input:\n    type: string\n" + "".join(
        "    %s\n" % f for f in fields
    )


def target_input_with_label(*label_fields):
    return (
        "spec_version: 2\ninputs:\n  Pick Target:\n    type: target\n"
        "    target-filters:\n      labels:\n        - key: env\n"
        + "".join("          %s\n" % f for f in label_fields)
    )


def optional_conflict_diagnostics(diagnostics):
    return [
        d for d in diagnostics if "optional" in d.lower() and "pattern" in d.lower()
    ]


def value_and_values_diagnostics(diagnostics):
    return [d for d in diagnostics if "values" in d.lower() and "env" in d]


class TestOptionalInputSchema(unittest.TestCase):
    def test_boolean_optional_is_accepted(self):
        self.assertEqual([], schema_errors(string_input("optional: true")))
        self.assertEqual([], schema_errors(string_input("optional: false")))

    def test_non_boolean_optional_is_rejected(self):
        self.assertTrue(schema_errors(string_input("optional: 'yes'")))


class TestOptionalInputLanguageServer(unittest.TestCase):
    def test_tree_model_knows_optional(self):
        for value in ("true", "false"):
            unknown, _ = language_server(string_input("optional: %s" % value))
            self.assertEqual([], unknown)

    def test_optional_true_with_pattern_rejecting_empty_is_flagged(self):
        _, diagnostics = language_server(
            string_input("optional: true", "pattern: '^[a-z]+$'")
        )
        self.assertTrue(optional_conflict_diagnostics(diagnostics), diagnostics)

    def test_optional_true_with_empty_matching_pattern_is_fine(self):
        for pattern in ("'^$|^[a-z]+$'", "'^[a-z]*$'", "'^(dev|prod)?$'"):
            _, diagnostics = language_server(
                string_input("optional: true", "pattern: %s" % pattern)
            )
            self.assertEqual([], optional_conflict_diagnostics(diagnostics), pattern)

    def test_optional_false_with_rejecting_pattern_is_fine(self):
        _, diagnostics = language_server(
            string_input("optional: false", "pattern: '^[a-z]+$'")
        )
        self.assertEqual([], optional_conflict_diagnostics(diagnostics))

    def test_unevaluable_pattern_does_not_flag(self):
        # the server treats a pattern it cannot compile as "unknown", never as a conflict
        _, diagnostics = language_server(
            string_input("optional: true", "pattern: '([a-z'")
        )
        self.assertEqual([], optional_conflict_diagnostics(diagnostics))

    def test_optional_is_ignored_on_entity_inputs(self):
        # 'optional' carries no meaning for target/agent/credentials/... inputs
        doc = (
            "spec_version: 2\ninputs:\n  Pick Target:\n    type: target\n"
            "    optional: true\n    pattern: '^[a-z]+$'\n"
        )
        _, diagnostics = language_server(doc)
        self.assertEqual([], optional_conflict_diagnostics(diagnostics))


class TestTargetLabelValuesSchema(unittest.TestCase):
    def test_values_list_is_accepted(self):
        self.assertEqual(
            [],
            schema_errors(target_input_with_label("values:", "  - dev", "  - staging")),
        )

    def test_values_must_be_a_list(self):
        self.assertTrue(schema_errors(target_input_with_label("values: dev")))

    def test_value_and_values_together_are_rejected(self):
        self.assertTrue(
            schema_errors(target_input_with_label("value: dev", "values:", "  - dev"))
        )

    def test_single_value_still_accepted(self):
        self.assertEqual([], schema_errors(target_input_with_label("value: dev")))


class TestTargetLabelValuesLanguageServer(unittest.TestCase):
    def test_tree_model_knows_values(self):
        unknown, _ = language_server(
            target_input_with_label("values:", "  - dev", "  - staging")
        )
        self.assertEqual([], unknown)

    def test_value_and_values_together_are_flagged(self):
        _, diagnostics = language_server(
            target_input_with_label("value: dev", "values:", "  - staging")
        )
        self.assertTrue(value_and_values_diagnostics(diagnostics), diagnostics)

    def test_values_alone_is_fine(self):
        _, diagnostics = language_server(target_input_with_label("values:", "  - dev"))
        self.assertEqual([], value_and_values_diagnostics(diagnostics))


if __name__ == "__main__":
    unittest.main()
