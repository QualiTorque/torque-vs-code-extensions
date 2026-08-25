import unittest
from unittest.mock import MagicMock

from server.ats.parser import Parser
from server.validation.bp_v2_validator import BlueprintSpec2Validator


def parse(doc):
    return Parser(doc).parse()


def validate(doc):
    """Parses the document, runs the spec2 validator and returns
    (tree, diagnostics). Expression errors land on the tree's errors,
    semantic checks in the returned diagnostics."""
    tree = parse(doc)
    document = MagicMock()
    document.lines = doc.splitlines(True)
    validator = BlueprintSpec2Validator(tree, document)
    diagnostics = validator.validate()
    return tree, diagnostics


def unknown_key_errors(tree):
    return [e for e in tree.errors if "does not have child" in e.message]


class TestSpec2TreeCoversModernBlueprint(unittest.TestCase):
    """The tree model must recognize every YAML key the Torque server parses.
    An unrecognized key produces a 'Parent node does not have child' error,
    which the language server publishes as a (false) error diagnostic."""

    def assert_parses_clean(self, doc):
        tree = parse(doc)
        errors = unknown_key_errors(tree)
        messages = [e.message for e in errors]
        self.assertEqual([], messages)

    def test_top_level_sections(self):
        self.assert_parses_clean(
            """spec_version: 2
description: modern blueprint
instructions:
  text: how to use
metadata:
  display-name: Modern
  estimated-ccu: '5'
  blueprint-labels:
    - key: team
      value: infra
environment:
  environment_name: my-env
labels:
  - env: dev
env_references:
  net:
    labels-selector: 'env=dev'
resources:
  vm_pool:
    selector:
      type: vcenter_vm
      quantity: 2
  fixed_box:
    reference: 'res-abc123'
api_access:
  service_account: svc@acme.com
layout:
  source:
    store: repo
    path: layouts/l.yaml
"""
        )

    def test_grain_level_fields(self):
        self.assert_parses_clean(
            """spec_version: 2
grains:
  deploy_app:
    kind: terraform
    depends-on: other_grain
    tf-version: 1.5.5
    when: 'true'
    env-labels:
      on-success:
        - stage: done
    condition:
      - type: approval
        message: please approve
        channels:
          - type: group
            groups:
              - admins
    spec:
      source:
        store: repo
        path: modules/app
        branch: main
        tag: v1.0
        commit: abc123
      inputs:
        - vpc: '10.0.0.0/16'
      outputs:
        - hostname
"""
        )

    def test_grain_spec_fields(self):
        self.assert_parses_clean(
            """spec_version: 2
grains:
  deploy_app:
    kind: terraform
    spec:
      source:
        path: modules/app
      target:
        name: my-target
        runner-configuration-override:
          isolated: true
      backend:
        type: s3
        bucket: my-bucket
        region: us-east-1
        key-prefix: envs
      tfvars-files:
        - source:
            path: vars/prod.tfvars
      workspace-directories:
        - source:
            path: dirs/extra
            name: extra
      provider-overrides:
        - name: aws
          source: hashicorp/aws
          version: '~>5.0'
      target-resource:
        - module.app
      auto-approve: false
      auto-retry: true
      version: 1.5.5
      mode: managed
      env_configuration: true
      command-arguments: '--parallelism=2'
"""
        )

    def test_helm_kubernetes_cfn_argocd_ansible_fields(self):
        self.assert_parses_clean(
            """spec_version: 2
grains:
  chart:
    kind: helm
    spec:
      source:
        path: charts/app
        chart-version: 1.0.0
      target-namespace: apps
      release: my-release
      values-files:
        - source:
            path: values/dev.yaml
      commands:
        - dep up ./chart
  stack:
    kind: cloudformation
    spec:
      source:
        path: templates/stack.yaml
      region: us-east-1
      stack-name-prefix: myprefix
      template-storage:
        bucket-name: my-bucket
        region: us-east-1
  gitops:
    kind: argocd
    spec:
      application: my-app
      application-namespace: argocd
      deployment-engine: engine1
      mode: data
  play:
    kind: ansible
    spec:
      source:
        path: playbooks/site.yaml
      inventory-file:
        all:
          hosts:
            web1: {}
      on-destroy:
        source:
          path: playbooks/teardown.yaml
"""
        )

    def test_agent_section_fields(self):
        self.assert_parses_clean(
            """spec_version: 2
grains:
  runner:
    kind: shell
    spec:
      agent:
        name: my-agent
        region: us-east-1
        service-account: my-sa
        runner-namespace: my-ns
        isolated: true
        storage-size: 800
        use-storage: false
        kubernetes:
          pod-labels:
            - app: torque
          pod-annotations:
            - note: x
          node-selector:
            - pool: runners
          tolerations:
            - key: dedicated
              operator: Equal
              value: torque
              effect: NoSchedule
          permissions:
            destination-context-name: ctx
            secret-name: sec
            secret-namespace: ns
        docker:
          permissions:
            secret-path: /run/secrets/x
      files:
        - source: repo
          path: scripts/run.sh
          tag: v1
      activities:
        deploy:
          commands:
            - name: run
              command: ./run.sh
              outputs:
                - result
        destroy:
          commands:
            - 'echo bye'
"""
        )

    def test_script_hooks(self):
        self.assert_parses_clean(
            """spec_version: 2
grains:
  infra:
    kind: opentofu
    spec:
      source:
        path: modules/net
      opentofuvars-files:
        - source:
            path: vars/dev.tfvars
      scripts:
        pre-tofu-init:
          source:
            path: scripts/init.sh
          arguments: '--fast'
        pre-tofu-destroy:
          source:
            path: scripts/destroy.sh
        post-tofu-plan:
          source:
            path: scripts/plan.sh
  legacy:
    kind: terraform
    spec:
      source:
        path: modules/app
      scripts:
        pre-tf-init:
          source:
            path: scripts/a.sh
        post-tf-plan:
          source:
            path: scripts/b.sh
        pre-tf-destroy:
          source:
            path: scripts/c.sh
  play:
    kind: ansible
    spec:
      source:
        path: playbooks/site.yaml
      scripts:
        pre-ansible-run:
          source:
            path: scripts/pre.sh
          outputs:
            - token
  cdk_app:
    kind: aws-cdk
    spec:
      source:
        path: cdk/app
      scripts:
        pre-aws-cdk-deploy:
          source:
            path: scripts/pre.sh
        post-aws-cdk-deploy:
          source:
            path: scripts/post.sh
"""
        )

    def test_input_fields(self):
        self.assert_parses_clean(
            """spec_version: 2
inputs:
  Plain Input:
    type: string
    style: text
    default: abc
    description: a value
    sensitive: false
    pattern: '^$|^https?://.+$'
    validation-description: Empty or a URL
  Chosen VM:
    type: input-source
    source-name: my-vcenter-source
    depends-on: Plain Input
    searchable: true
    overrides:
      - filter_pattern: 'web.*'
  Uploaded:
    type: file
    max-size-MB: 1
    max-files: 2
    allowed-formats:
      - txt
  Cred:
    type: credentials
    allowed-credential-providers:
      - vsphere
  Target Pick:
    type: target
    target-filters:
      cloud-providers:
        - aws
      labels:
        - key: env
          value: dev
  Hosts:
    type: resource
    style: multi-select
    resource-selector:
      type: vcenter_vm
      reservable-only: true
  Params Map:
    type: parameter
    parameter-name: my-parameter
"""
        )

    def test_output_sensitive_field(self):
        self.assert_parses_clean(
            """spec_version: 2
outputs:
  admin_password:
    value: 'static'
    kind: regular
    quick: true
    sensitive: true
"""
        )


class TestSpec2DeadFieldsStayDead(unittest.TestCase):
    """The server ignores these fields; the tree model must NOT accept them."""

    def test_spec_host_is_unknown(self):
        tree = parse(
            """spec_version: 2
grains:
  deploy_app:
    kind: terraform
    spec:
      host:
        name: agent1
"""
        )
        self.assertTrue(any("host" in e.message for e in unknown_key_errors(tree)))

    def test_agent_image_is_unknown(self):
        tree = parse(
            """spec_version: 2
grains:
  deploy_app:
    kind: terraform
    spec:
      agent:
        name: agent1
        image: custom:latest
"""
        )
        self.assertTrue(any("image" in e.message for e in unknown_key_errors(tree)))


class TestSpec2ExpressionValidation(unittest.TestCase):
    def expression_errors(self, doc):
        tree, _ = validate(doc)
        return [e.message for e in tree.errors if "does not have child" not in e.message]

    def test_resources_prefix_allowed(self):
        errors = self.expression_errors(
            """spec_version: 2
resources:
  vm_pool:
    selector:
      type: vcenter_vm
grains:
  deploy_app:
    kind: terraform
    spec:
      source:
        path: modules/app
      inputs:
        - vm_name: '{{ .resources.vm_pool.name }}'
"""
        )
        self.assertEqual([], errors)

    def test_dynamic_values_allowed(self):
        errors = self.expression_errors(
            """spec_version: 2
outputs:
  url:
    value: 'https://app-{{ envId }}.example.com'
  name_out:
    value: '{{ environmentName }}'
"""
        )
        self.assertEqual([], errors)

    def test_downcase_pipe_still_allowed(self):
        errors = self.expression_errors(
            """spec_version: 2
outputs:
  url:
    value: '{{ envId | downcase }}'
"""
        )
        self.assertEqual([], errors)

    def test_key_access_pipe_allowed(self):
        errors = self.expression_errors(
            """spec_version: 2
grains:
  producer:
    kind: terraform
    spec:
      source:
        path: modules/app
      outputs:
        - all_data
  consumer:
    kind: terraform
    depends-on: producer
    spec:
      source:
        path: modules/consumer
      inputs:
        - item: '{{ .grains.producer.outputs | key_access: "hostname" }}'
"""
        )
        self.assertEqual([], errors)

    def test_free_form_sections_not_expression_validated(self):
        # customization uses the UI's own template dialect (no leading dot),
        # and inventory-file may hold Jinja - neither is Torque grain Liquid
        errors = self.expression_errors(
            """spec_version: 2
customization:
  launch-form:
    actions:
      download_report:
        type: button
        url: 'https://acme.com/{{ params.region }}/report'
    inputs:
      - name: advanced_input
        visible: '{{ inputs.advanced }}'
grains:
  play_grain:
    kind: ansible
    spec:
      source:
        path: playbooks/site.yaml
      inventory-file:
        all:
          vars:
            jinja_thing: '{{ hostvars[inventory_hostname] }}'
"""
        )
        self.assertEqual([], errors)

    def test_unknown_prefix_still_flagged(self):
        errors = self.expression_errors(
            """spec_version: 2
outputs:
  bad:
    value: '{{ .bogus.thing }}'
"""
        )
        self.assertTrue(errors)

    def test_unknown_bare_word_still_flagged(self):
        errors = self.expression_errors(
            """spec_version: 2
outputs:
  bad:
    value: '{{ notavariable }}'
"""
        )
        self.assertTrue(errors)


class TestSpec2ExistingDiagnosticsStillWork(unittest.TestCase):
    def test_duplicate_grain_outputs_flagged(self):
        _, diagnostics = validate(
            """spec_version: 2
grains:
  deploy_app:
    kind: terraform
    spec:
      source:
        path: modules/app
      outputs:
        - hostname
        - hostname
"""
        )
        self.assertTrue(
            any("Multiple declarations of output" in d.message for d in diagnostics)
        )

    def test_depends_on_unknown_grain_flagged(self):
        _, diagnostics = validate(
            """spec_version: 2
grains:
  deploy_app:
    kind: terraform
    depends-on: ghost_grain
    spec:
      source:
        path: modules/app
"""
        )
        self.assertTrue(
            any("depends on undefined grain" in d.message for d in diagnostics)
        )


if __name__ == "__main__":
    unittest.main()


class TestEnvReferencesExpressions(unittest.TestCase):
    def test_env_references_prefix_allowed(self):
        tree, _ = validate(
            """spec_version: 2
env_references:
  net:
    labels-selector: 'env=dev'
outputs:
  vpc:
    value: '{{ .env_references.net.outputs.vpc_id }}'
"""
        )
        errors = [e.message for e in tree.errors]
        self.assertEqual([], errors)
