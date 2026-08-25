"""P1 semantic validations for spec2 blueprints.

Every rule here mirrors a server-side validation verified in the Torque
source (cs2018) during the 2026-08 schema audit:
- a resource requirement takes exactly one of selector / reference
- a grain takes at most one of agent / target
- grain mode is per-kind (terraform: managed/no-termination; argocd: data,
  mandatory; other kinds: managed only)
- auto-approve: false requires runner storage (use-storage must not be false)
- workflow: scope must be space/env/env_resource; space-scoped workflows
  allow only manual triggers; manual triggers take no event/cron; event
  triggers require event and take no cron; cron triggers require cron and
  take no event; timeout must be an integer >= 5 when it is not a Liquid
  expression
"""
import unittest
from unittest.mock import MagicMock

from server.ats.parser import Parser
from server.validation.bp_v2_validator import BlueprintSpec2Validator


def validate(doc):
    tree = Parser(doc).parse()
    document = MagicMock()
    document.lines = doc.splitlines(True)
    return BlueprintSpec2Validator(tree, document).validate()


def messages(doc):
    return [d.message for d in validate(doc)]


GRAIN = """spec_version: 2
grains:
  deploy_app:
    kind: {kind}
    spec:
{spec}
"""


class TestResourceRequirementRules(unittest.TestCase):
    def test_selector_and_reference_together_flagged(self):
        msgs = messages(
            """spec_version: 2
resources:
  db_hosts:
    selector:
      type: switch
    reference: 'res-1'
"""
        )
        self.assertTrue(any("selector" in m and "reference" in m for m in msgs))

    def test_requirement_with_neither_flagged(self):
        msgs = messages(
            """spec_version: 2
resources:
  db_hosts: {}
"""
        )
        self.assertTrue(any("selector" in m and "reference" in m for m in msgs))

    def test_selector_only_ok(self):
        msgs = messages(
            """spec_version: 2
resources:
  db_hosts:
    selector:
      type: switch
"""
        )
        self.assertFalse(any("selector" in m and "reference" in m for m in msgs))

    def test_reference_only_ok(self):
        msgs = messages(
            """spec_version: 2
resources:
  db_hosts:
    reference: 'res-1'
"""
        )
        self.assertFalse(any("selector" in m and "reference" in m for m in msgs))


class TestAgentTargetExclusivity(unittest.TestCase):
    def test_agent_and_target_together_flagged(self):
        msgs = messages(
            GRAIN.format(
                kind="terraform",
                spec="""      source:
        path: modules/app
      agent:
        name: agent1
      target:
        name: target1""",
            )
        )
        self.assertTrue(any("agent" in m and "target" in m for m in msgs))

    def test_target_only_ok(self):
        msgs = messages(
            GRAIN.format(
                kind="terraform",
                spec="""      source:
        path: modules/app
      target:
        name: target1""",
            )
        )
        self.assertFalse(any("agent" in m and "target" in m for m in msgs))


class TestGrainModeRules(unittest.TestCase):
    def test_terraform_no_termination_ok(self):
        msgs = messages(
            GRAIN.format(
                kind="terraform",
                spec="""      source:
        path: modules/app
      mode: no-termination""",
            )
        )
        self.assertFalse(any("mode" in m.lower() for m in msgs))

    def test_terraform_data_mode_flagged(self):
        msgs = messages(
            GRAIN.format(
                kind="terraform",
                spec="""      source:
        path: modules/app
      mode: data""",
            )
        )
        self.assertTrue(any("mode" in m.lower() for m in msgs))

    def test_argocd_without_mode_flagged(self):
        msgs = messages(
            GRAIN.format(
                kind="argocd",
                spec="""      application: my-app
      application-namespace: argocd""",
            )
        )
        self.assertTrue(any("mode" in m.lower() for m in msgs))

    def test_argocd_data_mode_ok(self):
        msgs = messages(
            GRAIN.format(
                kind="argocd",
                spec="""      application: my-app
      application-namespace: argocd
      mode: data""",
            )
        )
        self.assertFalse(any("mode" in m.lower() for m in msgs))

    def test_helm_managed_mode_ok(self):
        msgs = messages(
            GRAIN.format(
                kind="helm",
                spec="""      source:
        path: charts/app
      mode: managed""",
            )
        )
        self.assertFalse(any("mode" in m.lower() for m in msgs))


class TestAutoApproveStorageCoupling(unittest.TestCase):
    def test_manual_approval_with_storage_disabled_flagged(self):
        msgs = messages(
            GRAIN.format(
                kind="terraform",
                spec="""      source:
        path: modules/app
      auto-approve: false
      agent:
        name: agent1
        use-storage: false""",
            )
        )
        self.assertTrue(any("use-storage" in m or "storage" in m.lower() for m in msgs))

    def test_manual_approval_with_storage_ok(self):
        msgs = messages(
            GRAIN.format(
                kind="terraform",
                spec="""      source:
        path: modules/app
      auto-approve: false
      agent:
        name: agent1""",
            )
        )
        self.assertFalse(any("use-storage" in m or "storage" in m.lower() for m in msgs))


WORKFLOW = """spec_version: 2
workflow:
{workflow}
grains:
  do_work:
    kind: shell
    spec:
      agent:
        name: agent1
      activities:
        deploy:
          commands:
            - 'echo hi'
"""


class TestWorkflowRules(unittest.TestCase):
    def test_invalid_scope_flagged(self):
        msgs = messages(WORKFLOW.format(workflow="  scope: bogus_scope"))
        self.assertTrue(any("scope" in m.lower() for m in msgs))

    def test_valid_scopes_ok(self):
        for scope in ("space", "env", "env_resource"):
            msgs = messages(
                WORKFLOW.format(
                    workflow="  scope: {}\n  resource-types: aws_instance".format(scope)
                )
            )
            self.assertFalse(
                any("scope" in m.lower() for m in msgs),
                "scope '{}' was wrongly flagged: {}".format(scope, msgs),
            )

    def test_space_scope_with_cron_trigger_flagged(self):
        msgs = messages(
            WORKFLOW.format(
                workflow="""  scope: space
  triggers:
    - type: cron
      cron: '0 0 * * *'"""
            )
        )
        self.assertTrue(any("trigger" in m.lower() for m in msgs))

    def test_manual_trigger_with_cron_flagged(self):
        msgs = messages(
            WORKFLOW.format(
                workflow="""  scope: env
  triggers:
    - type: manual
      cron: '0 0 * * *'"""
            )
        )
        self.assertTrue(any("trigger" in m.lower() or "cron" in m.lower() for m in msgs))

    def test_event_trigger_without_event_flagged(self):
        msgs = messages(
            WORKFLOW.format(
                workflow="""  scope: env
  triggers:
    - type: event"""
            )
        )
        self.assertTrue(any("event" in m.lower() for m in msgs))

    def test_timeout_below_minimum_flagged(self):
        msgs = messages(
            WORKFLOW.format(
                workflow="""  scope: env
  timeout: '3'
  triggers:
    - type: manual"""
            )
        )
        self.assertTrue(any("timeout" in m.lower() for m in msgs))

    def test_timeout_valid_ok(self):
        msgs = messages(
            WORKFLOW.format(
                workflow="""  scope: env
  timeout: '30'
  triggers:
    - type: manual"""
            )
        )
        self.assertFalse(any("timeout" in m.lower() for m in msgs))




class TestValidatorRobustness(unittest.TestCase):
    """A half-typed document must never crash validate() - an escaping
    exception wipes ALL diagnostics for the file."""

    def test_empty_spec_does_not_crash_and_keeps_other_diagnostics(self):
        msgs = messages(
            """spec_version: 2
grains:
  broken_grain:
    kind: terraform
    depends-on: ghost_grain
    spec:
"""
        )
        self.assertTrue(any("depends on undefined grain" in m for m in msgs))

    def test_empty_grain_body_does_not_crash(self):
        messages(
            """spec_version: 2
grains:
  empty_grain:
"""
        )

    def test_empty_spec_in_first_grain_does_not_hide_second_grain_issues(self):
        msgs = messages(
            """spec_version: 2
grains:
  first_grain:
    kind: terraform
    spec:
  second_grain:
    kind: terraform
    spec:
      source:
        path: modules/app
      outputs:
        - hostname
        - hostname
"""
        )
        self.assertTrue(any("Multiple declarations of output" in m for m in msgs))

    def test_empty_grain_does_not_suppress_duplicate_deps_check(self):
        msgs = messages(
            """spec_version: 2
grains:
  empty_grain:
  producer:
    kind: terraform
    spec:
      source:
        path: modules/app
  consumer:
    kind: terraform
    depends-on: producer, producer
    spec:
      source:
        path: modules/consumer
"""
        )
        self.assertTrue(any("Multiple mentioning of grain" in m for m in msgs))

if __name__ == "__main__":
    unittest.main()


class TestParserRobustness(unittest.TestCase):
    """Crashes found by review: a parser/validator exception is swallowed by
    server.py and silently publishes ZERO diagnostics for the file."""

    def test_variable_like_keys_in_free_form_sections_do_not_crash(self):
        # keys that match the variables regex used to blow up in
        # FreeFormNode.get_child (text assigned before start_pos)
        messages(
            """spec_version: 2
environment:
  tags:
    $tag: v
customization:
  "{{ .inputs.x }}": v
"""
        )

    def test_scripts_expression_to_grain_without_scripts_does_not_crash(self):
        msgs = messages(
            """spec_version: 2
grains:
  producer:
    kind: helm
    spec:
      source:
        path: charts/app
  consumer:
    kind: helm
    depends-on: producer
    spec:
      source:
        path: charts/consumer
      inputs:
        - y: '{{ .grains.producer.scripts.post_helm_install.outputs.y }}'
      outputs:
        - dup
        - dup
"""
        )
        # the real diagnostics in the file must survive
        self.assertTrue(any("Multiple declarations of output" in m for m in msgs))

    def test_union_typed_property_attribute_access_returns_none(self):
        from server.ats.parser import Parser
        tree = Parser(
            """spec_version: 2
grains:
  deploy_app:
    kind: terraform
    spec:
      source:
        path: modules/app
      target:
        runner-configuration-override:
          isolated: true
"""
        ).parse()
        grain = tree.grains.nodes[0].value
        self.assertIsNone(grain.spec.target.name)

    def test_short_form_blueprint_label_expression_errors_surface(self):
        from server.ats.parser import Parser
        from server.validation.bp_v2_validator import BlueprintSpec2Validator
        doc = """spec_version: 2
metadata:
  blueprint-labels:
    - '{{ bogus_word }}'
"""
        tree = Parser(doc).parse()
        document = MagicMock()
        document.lines = doc.splitlines(True)
        BlueprintSpec2Validator(tree, document).validate()
        self.assertTrue(
            any("not a reserved variable" in e.message for e in tree.errors)
        )
