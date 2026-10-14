"""Resource selector `any-of` and `any-provider-type` (cs2018 b1a12abc3f, 2026-10-04;
schema PR #185). See section 13 of docs/spec2-language-support.md for the server
source behind every rule pinned here.

A selector may list alternative criteria sets under `any-of`; a resource matches
when it matches the criteria at the selector's own level and at least one of the
alternatives. The same rules hold for both places a selector appears - a resource
requirement (`resources.<name>.selector`) and a resource input
(`inputs.<name>.resource-selector`) - so every test below runs against both.

- A selector needs one of type / attributes / provider-type / provider-name /
  any-of; `any-provider-type` alone does not count.
- Each alternative needs one of type / attributes / provider-type / provider-name,
  and cannot nest another `any-of`. A null alternative is an error.
- `type`, `provider-type`, `provider-name` and `any-provider-type` may each be
  given at the selector's level or inside the alternatives, never both - whatever
  the values.
- `attributes` may be given at both levels (the names must not repeat, which the
  schema cannot check - a documented gap).
"""
import io
import json
import os
import textwrap
import unittest
from unittest.mock import MagicMock

import yaml
from jsonschema import Draft7Validator

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "client", "schemas", "blueprint-spec2-schema.json"
)
with io.open(SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = Draft7Validator(json.load(_f))

GRAINS = (
    "grains:\n  app:\n    kind: shell\n    spec:\n      activities:\n"
    "        deploy:\n          commands:\n            - echo hello\n"
)


def _selector_block(selector):
    return textwrap.indent(textwrap.dedent(selector).strip("\n") + "\n", " " * 6)


def resource_doc(selector):
    """`selector` placed under resources.<name>.selector."""
    return (
        "spec_version: 2\nresources:\n  my-host:\n    selector:\n"
        + _selector_block(selector)
        + GRAINS
    )


def input_doc(selector):
    """`selector` placed under inputs.<name>.resource-selector."""
    return (
        "spec_version: 2\ninputs:\n  my-host:\n    type: resource\n"
        "    resource-selector:\n" + _selector_block(selector) + GRAINS
    )


BUILDERS = (
    ("resources.<n>.selector", resource_doc),
    ("inputs.<n>.resource-selector", input_doc),
)


def schema_errors(doc):
    return [e.message for e in SCHEMA.iter_errors(yaml.safe_load(doc))]


class SelectorCase(unittest.TestCase):
    def assert_accepted(self, selector):
        for where, build in BUILDERS:
            with self.subTest(where=where):
                self.assertEqual([], schema_errors(build(selector)))

    def assert_rejected(self, selector):
        for where, build in BUILDERS:
            with self.subTest(where=where):
                self.assertTrue(
                    schema_errors(build(selector)),
                    "the selector must be rejected at %s:\n%s" % (where, selector),
                )


class TestAnyOfAccepted(SelectorCase):
    def test_any_of_as_the_only_criterion(self):
        self.assert_accepted(
            """
            any-of:
              - type: my-resource-type
              - type: my-other-type
            """
        )

    def test_alternatives_take_every_criterion(self):
        self.assert_accepted(
            """
            any-of:
              - type: my-resource-type
                provider-type: vcenter
                provider-name: my-provider
                attributes:
                  - model: example-model
                any-provider-type: false
              - attributes:
                  - memory-gb: 64
            """
        )

    def test_any_provider_type_at_the_selector_level(self):
        self.assert_accepted(
            """
            type: my-resource-type
            any-provider-type: true
            """
        )
        self.assert_accepted(
            """
            any-provider-type: true
            any-of:
              - type: my-resource-type
              - type: my-other-type
            """
        )

    def test_any_provider_type_inside_alternatives(self):
        self.assert_accepted(
            """
            any-of:
              - type: my-resource-type
                any-provider-type: true
              - type: my-other-type
            """
        )

    def test_attributes_at_both_levels_with_different_names(self):
        self.assert_accepted(
            """
            attributes:
              - model: example-model
            any-of:
              - attributes:
                  - memory-gb: 64
              - attributes:
                  - memory-gb: 128
            """
        )

    def test_shared_criteria_at_the_selector_level(self):
        # what is common to all alternatives is written once, at the selector level
        self.assert_accepted(
            """
            provider-type: vcenter
            any-of:
              - type: my-resource-type
              - type: my-other-type
                provider-name: my-provider
            """
        )
        self.assert_accepted(
            """
            type: my-resource-type
            any-of:
              - provider-name: my-provider
              - provider-name: my-other-provider
            """
        )

    def test_selector_specific_fields_combine_with_any_of(self):
        self.assertEqual(
            [],
            schema_errors(
                resource_doc(
                    """
                    quantity: 2
                    any-of:
                      - type: my-resource-type
                    """
                )
            ),
        )
        self.assertEqual(
            [],
            schema_errors(
                input_doc(
                    """
                    reservable-only: true
                    any-of:
                      - type: my-resource-type
                    """
                )
            ),
        )


class TestAnyOfRejected(SelectorCase):
    def test_nested_any_of(self):
        self.assert_rejected(
            """
            any-of:
              - type: my-resource-type
                any-of:
                  - type: my-other-type
            """
        )

    def test_alternative_with_only_any_provider_type(self):
        # any-provider-type is not a selection criterion
        self.assert_rejected(
            """
            any-of:
              - any-provider-type: true
            """
        )

    def test_empty_alternative(self):
        self.assert_rejected(
            """
            any-of:
              - {}
            """
        )

    def test_null_alternative(self):
        self.assert_rejected(
            """
            any-of:
              -
              - type: my-resource-type
            """
        )

    def test_empty_any_of(self):
        self.assert_rejected("any-of: []\n")

    def test_selector_with_only_any_provider_type(self):
        self.assert_rejected("any-provider-type: true\n")

    def test_selector_specific_fields_are_not_alternative_criteria(self):
        self.assertTrue(
            schema_errors(
                resource_doc(
                    """
                    any-of:
                      - type: my-resource-type
                        quantity: 2
                    """
                )
            )
        )
        self.assertTrue(
            schema_errors(
                input_doc(
                    """
                    any-of:
                      - type: my-resource-type
                        reservable-only: true
                    """
                )
            )
        )


class TestAnyOfConflicts(SelectorCase):
    """A field given at the selector level may not be given inside an alternative too.

    Each test first shows that either half alone is fine, so the rejection can only
    come from the combination. The conflicting alternative is always the second one,
    and the rule is about where a field is given, not about its value."""

    def test_type_at_both_levels(self):
        self.assert_accepted(
            """
            type: my-resource-type
            any-of:
              - provider-name: my-provider
            """
        )
        self.assert_accepted(
            """
            any-of:
              - provider-name: my-provider
              - type: my-other-type
            """
        )
        self.assert_rejected(
            """
            type: my-resource-type
            any-of:
              - provider-name: my-provider
              - type: my-other-type
            """
        )

    def test_provider_type_at_both_levels(self):
        self.assert_accepted(
            """
            provider-type: vcenter
            any-of:
              - type: my-resource-type
            """
        )
        self.assert_accepted(
            """
            any-of:
              - type: my-resource-type
              - provider-type: aws
            """
        )
        self.assert_rejected(
            """
            provider-type: vcenter
            any-of:
              - type: my-resource-type
              - provider-type: aws
            """
        )

    def test_provider_name_at_both_levels(self):
        self.assert_accepted(
            """
            provider-name: my-provider
            any-of:
              - type: my-resource-type
            """
        )
        self.assert_accepted(
            """
            any-of:
              - type: my-resource-type
              - provider-name: my-provider
            """
        )
        self.assert_rejected(
            """
            provider-name: my-provider
            any-of:
              - type: my-resource-type
              - provider-name: my-other-provider
            """
        )

    def test_any_provider_type_at_both_levels(self):
        # the same value at both levels is still a conflict
        self.assert_accepted(
            """
            any-provider-type: false
            any-of:
              - type: my-resource-type
            """
        )
        self.assert_accepted(
            """
            any-of:
              - type: my-resource-type
              - type: my-other-type
                any-provider-type: false
            """
        )
        self.assert_rejected(
            """
            any-provider-type: false
            any-of:
              - type: my-resource-type
              - type: my-other-type
                any-provider-type: false
            """
        )

    def test_conflict_points_at_the_alternative(self):
        doc = yaml.safe_load(
            resource_doc(
                """
                type: my-resource-type
                any-of:
                  - provider-name: my-provider
                  - type: my-other-type
                """
            )
        )
        paths = [list(e.absolute_path) for e in SCHEMA.iter_errors(doc)]
        self.assertIn(["resources", "my-host", "selector", "any-of", 1], paths)


def parse(doc):
    from server.ats.parser import Parser

    return Parser(doc).parse()


def validate(doc):
    from server.validation.bp_v2_validator import BlueprintSpec2Validator

    tree = parse(doc)
    document = MagicMock()
    document.lines = doc.splitlines(True)
    return tree, BlueprintSpec2Validator(tree, document).validate()


FULL_SELECTOR = """
provider-type: vcenter
attributes:
  - model: example-model
any-of:
  - type: my-resource-type
    provider-name: my-provider
    attributes:
      - memory-gb: 64
    any-provider-type: true
  - type: my-other-type
"""


class TestLanguageServerParity(unittest.TestCase):
    """Whatever the schema accepts, the tree model must accept too, or the editor
    shows a false 'unknown key' error next to a schema-clean document - and what
    the schema rejects as an unknown key, the tree model reports as well."""

    def unknown_keys(self, doc):
        return [
            e.message for e in parse(doc).errors if "does not have child" in e.message
        ]

    def test_any_of_documents_have_no_unknown_keys(self):
        for where, build in BUILDERS:
            with self.subTest(where=where):
                doc = build(FULL_SELECTOR)
                self.assertEqual([], schema_errors(doc))
                self.assertEqual([], self.unknown_keys(doc))

    def test_any_provider_type_at_the_selector_level(self):
        for where, build in BUILDERS:
            with self.subTest(where=where):
                doc = build("type: my-resource-type\nany-provider-type: true\n")
                self.assertEqual([], self.unknown_keys(doc))

    def test_selector_specific_fields_combine_with_any_of(self):
        self.assertEqual(
            [],
            self.unknown_keys(resource_doc("quantity: 2\n" + FULL_SELECTOR)),
        )
        self.assertEqual(
            [],
            self.unknown_keys(input_doc("reservable-only: true\n" + FULL_SELECTOR)),
        )

    def test_nested_any_of_is_an_unknown_key_in_the_tree_too(self):
        selector = "any-of:\n  - type: my-resource-type\n    any-of:\n      - type: my-other-type\n"
        for where, build in BUILDERS:
            with self.subTest(where=where):
                self.assertTrue(self.unknown_keys(build(selector)))

    def test_selector_specific_fields_are_unknown_inside_an_alternative(self):
        self.assertTrue(
            self.unknown_keys(
                resource_doc("any-of:\n  - type: my-resource-type\n    quantity: 2\n")
            )
        )
        self.assertTrue(
            self.unknown_keys(
                input_doc(
                    "any-of:\n  - type: my-resource-type\n    reservable-only: true\n"
                )
            )
        )

    def test_liquid_inside_alternatives_is_accepted(self):
        # the alternatives' fields are resolved as Liquid patterns, like quantity
        doc = (
            "spec_version: 2\ninputs:\n  my-type:\n    type: string\n"
            "resources:\n  my-host:\n    selector:\n      any-of:\n"
            "        - type: '{{ .inputs.my-type }}'\n"
            "          provider-type: '{{ .inputs.my-type }}'\n"
            "          provider-name: '{{ .inputs.my-type }}'\n"
            "          attributes:\n            - model: '{{ .inputs.my-type }}'\n"
            + GRAINS
        )
        self.assertEqual([], schema_errors(doc))
        tree, diagnostics = validate(doc)
        self.assertEqual([], [e.message for e in tree.errors])
        self.assertEqual([], [d.message for d in diagnostics])

    def test_full_validation_is_clean(self):
        for where, build in BUILDERS:
            with self.subTest(where=where):
                tree, diagnostics = validate(build(FULL_SELECTOR))
                self.assertEqual([], [e.message for e in tree.errors])
                # the input document declares an input that no grain reads, which is
                # worth a hint but has nothing to do with the selector
                self.assertEqual(
                    [],
                    [
                        d.message
                        for d in diagnostics
                        if "is not accessed" not in d.message
                    ],
                )

    def test_half_typed_any_of_does_not_crash(self):
        for selector in ("any-of:\n", "any-of:\n  -\n", "any-of:\n  - type:\n"):
            for where, build in BUILDERS:
                with self.subTest(where=where, selector=selector):
                    validate(build(selector))


if __name__ == "__main__":
    unittest.main()
