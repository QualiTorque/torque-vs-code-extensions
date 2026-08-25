"""Findings from validating 453 real-world spec2 blueprints (2026-08).

Each rule here was verified against the Torque server source (cs2018):
- flow-style YAML sequences are plain YAML and must parse (162 real files
  failed wholesale on them)
- expressions support bracket access (.inputs["Name With Spaces"] and the
  .inputs.["X"] spelling), the shell-grain activities output path, dotless
  prefix forms ({{ inputs.X }} - DotLiquid resolves names against the
  context Hash, the leading dot is only a convention), chained pipes, and
  the full DotLiquid filter set plus Torque's custom filters
- grain output references are valid through TRANSITIVE depends-on chains
  (cs2018 GetAllDependentGrains recurses)
- grain authentication entries take Liquid (the server resolves them)
- unprintable C1 control bytes (mojibake) must not crash the parser -
  the server's YamlDotNet tolerates them
"""
import unittest
from unittest.mock import MagicMock

from server.ats.parser import Parser
from server.validation.bp_v2_validator import BlueprintSpec2Validator


def validate(doc):
    tree = Parser(doc).parse()
    document = MagicMock()
    document.lines = doc.splitlines(True)
    diags = BlueprintSpec2Validator(tree, document).validate()
    return tree, diags


def all_errors(doc):
    tree, diags = validate(doc)
    return [e.message for e in tree.errors] + [d.message for d in diags]


class TestFlowStyleYaml(unittest.TestCase):
    def test_flow_sequence_in_allowed_values(self):
        tree, _ = validate(
            """spec_version: 2
inputs:
  My Input:
    type: string
    allowed-values: ["a", "b"]
    default: "a"
"""
        )
        self.assertEqual([], [e.message for e in tree.errors])

    def test_flow_sequence_in_commands(self):
        tree, _ = validate(
            """spec_version: 2
grains:
  runner:
    kind: shell
    spec:
      agent:
        name: agent1
      activities:
        deploy:
          commands: ['echo hi', 'echo bye']
"""
        )
        self.assertEqual([], [e.message for e in tree.errors])

    def test_flow_sequence_values_are_modeled(self):
        tree, _ = validate(
            """spec_version: 2
inputs:
  My Input:
    type: string
    allowed-values: [alpha, beta]
"""
        )
        node = tree.inputs.nodes[0].value
        values = [v.text for v in node.allowed_values.value.nodes]
        self.assertEqual(["alpha", "beta"], values)


class TestUnprintableCharacters(unittest.TestCase):
    def test_c1_control_bytes_do_not_crash(self):
        # mojibake em-dash (utf-8 bytes read as latin-1): a real blueprint
        # carries this and the server's YamlDotNet accepts it
        doc = (
            "spec_version: 2\n"
            "grains:\n"
            "  runner:\n"
            "    kind: shell\n"
            "    spec:\n"
            "      agent:\n"
            "        name: agent1\n"
            "      activities:\n"
            "        deploy:\n"
            "          commands:\n"
            "            - 'echo WARNINGâmanual cleanup'\n"
        )
        tree, _ = validate(doc)
        self.assertEqual([], [e.message for e in tree.errors])


EXPR_DOC = """spec_version: 2
inputs:
  Plain:
    type: string
  Name With Spaces:
    type: string
grains:
  producer:
    kind: shell
    spec:
      agent:
        name: agent1
      activities:
        deploy:
          commands:
            - name: discover
              command: ./discover.sh
              outputs:
                - found_ip
  middle:
    kind: shell
    depends-on: producer
    spec:
      agent:
        name: agent1
      activities:
        deploy:
          commands:
            - 'echo mid'
  consumer:
    kind: shell
    depends-on: middle
    spec:
      agent:
        name: agent1
      inputs:
{consumer_inputs}
      activities:
        deploy:
          commands:
            - 'echo done'
"""


def expr_errors(consumer_inputs):
    doc = EXPR_DOC.format(consumer_inputs=consumer_inputs)
    tree, _ = validate(doc)
    return [e.message for e in tree.errors]


class TestExpressionForms(unittest.TestCase):
    def test_bracket_access_on_inputs(self):
        self.assertEqual(
            [], expr_errors("""        - a: '{{ .inputs["Name With Spaces"] }}'""")
        )

    def test_dot_bracket_access_on_inputs(self):
        self.assertEqual(
            [], expr_errors("""        - a: '{{ .inputs.["Name With Spaces"] }}'""")
        )

    def test_bracket_access_unknown_input_still_flagged(self):
        errors = expr_errors("""        - a: '{{ .inputs["No Such Input"] }}'""")
        self.assertTrue(any("No Such Input" in e for e in errors))

    def test_activities_output_path(self):
        self.assertEqual(
            [],
            expr_errors(
                "        - a: '{{ .grains.producer.activities.deploy.commands.discover.outputs.found_ip }}'"
            ),
        )

    def test_dotless_inputs_form(self):
        self.assertEqual([], expr_errors("        - a: '{{ inputs.Plain }}'"))

    def test_dotless_bracket_form(self):
        self.assertEqual(
            [], expr_errors("""        - a: '{{ inputs["Name With Spaces"] }}'""")
        )

    def test_bare_unknown_word_still_flagged(self):
        errors = expr_errors("        - a: '{{ notavariable }}'")
        self.assertTrue(errors)

    def test_transitive_depends_on_output_reference(self):
        # consumer depends on middle which depends on producer:
        # cs2018 GetAllDependentGrains recurses, so this is valid
        self.assertEqual(
            [],
            expr_errors(
                "        - a: '{{ .grains.producer.activities.deploy.commands.discover.outputs.found_ip }}'"
            ),
        )

    def test_unrelated_grain_output_reference_still_flagged(self):
        doc = EXPR_DOC.format(
            consumer_inputs="        - a: '{{ .grains.loner.outputs.x }}'"
        ).replace("  consumer:\n    kind: shell\n    depends-on: middle", "  consumer:\n    kind: shell")
        tree, _ = validate(doc)
        self.assertTrue([e.message for e in tree.errors])

    def test_standard_liquid_filters(self):
        self.assertEqual(
            [],
            expr_errors(
                """        - a: '{{ inputs.Plain | remove: "x" }}'
        - b: '{{ inputs.Plain | split: "," | first }}'
        - c: '{{ inputs.Plain | slice: 0, 5 }}'
        - d: '{{ inputs.Plain | json_escape }}'"""
            ),
        )

    def test_chained_pipes_allowed(self):
        self.assertEqual(
            [],
            expr_errors(
                "        - a: '{{ inputs.Plain | downcase | strip }}'"
            ),
        )

    def test_unknown_filter_still_flagged(self):
        errors = expr_errors("        - a: '{{ inputs.Plain | frobnicate }}'")
        self.assertTrue(any("frobnicate" in e for e in errors))


class TestAuthenticationAllowsLiquid(unittest.TestCase):
    def test_authentication_entries_take_expressions(self):
        tree, _ = validate(
            """spec_version: 2
inputs:
  AWS Credentials:
    type: credentials
grains:
  tfg:
    kind: terraform
    spec:
      source:
        path: modules/app
      authentication:
        - '{{ .inputs["AWS Credentials"] }}'
"""
        )
        self.assertEqual([], [e.message for e in tree.errors])


class TestUnusedInputWarning(unittest.TestCase):
    def used(self, usage_line):
        doc = """spec_version: 2
inputs:
  Name With Spaces:
    type: string
grains:
  grn:
    kind: shell
    spec:
      agent:
        name: agent1
      activities:
        deploy:
          commands:
            - %s
""" % usage_line
        _, diags = validate(doc)
        return not any("is not accessed" in d.message for d in diags)

    def test_bracket_usage_counts_as_accessed(self):
        self.assertTrue(self.used("""'echo {{ .inputs["Name With Spaces"] }}'"""))

    def test_dot_bracket_usage_counts_as_accessed(self):
        self.assertTrue(self.used("""'echo {{ .inputs.["Name With Spaces"] }}'"""))

    def test_genuinely_unused_still_warned(self):
        self.assertFalse(self.used("'echo nothing'"))


if __name__ == "__main__":
    unittest.main()
