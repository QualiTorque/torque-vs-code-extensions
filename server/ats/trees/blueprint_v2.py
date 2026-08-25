from dataclasses import dataclass, field
from typing import Dict, List, Union

from server.ats.trees.common import (
    BaseTree,
    MapNode,
    MappingNode,
    ObjectNode,
    Position,
    PropertyNode,
    ScalarNode,
    ScalarNodesSequence,
    SequenceNode,
    TextMappingSequence,
    TextNode,
    TextNodesSequence,
    YamlNode,
)


# ---------------------------------------------------------------------------
# Free form (permissive) content
#
# Some sections of a spec2 blueprint are free form on the server side as well
# (an inline ansible inventory, terraform provider attributes, input source
# overrides, the whole 'customization' section...). Modelling them key by key
# would either be impossible or would produce false "unknown key" errors, so
# they are represented by FreeFormNode which accepts any nested mapping,
# sequence or scalar without validating names.
# ---------------------------------------------------------------------------
@dataclass
class FreeFormNode(ObjectNode):
    """Accepts arbitrary nested YAML content (mappings, sequences and scalars)
    without validating key names."""

    children: List[YamlNode] = field(default_factory=list)
    text_value: TextNode = None

    def get_child(self, child_name: str):
        child = FreeFormProperty(parent=self)
        key = child.get_key()

        # The parser overwrites these with the real token positions right after
        # it gets the child, but assigning the text already runs the node's
        # validation, which dereferences the positions - they must not be None.
        position = self.start_pos or (0, 0)
        child.start_pos = key.start_pos = position
        child.end_pos = key.end_pos = self.end_pos or position

        key.text = child_name
        self.children.append(child)
        return child

    def add(self, node: YamlNode = None):
        if node is None:
            node = FreeFormNode(parent=self)

        self.children.append(node)
        return node

    def get_shortened_form_property(self):
        # the node holds a plain scalar (an element of a free form sequence)
        self.text_value = TextNode(parent=self)
        return self.text_value

    def get_children(self):
        children = list(self.children)
        if self.text_value is not None:
            children.append(self.text_value)

        return children


@dataclass
class FreeFormProperty(PropertyNode):
    """A single 'key: value' pair inside a free form section.
    The key is a TextNode and not a ScalarNode on purpose: free form content is
    opaque to the server, so a key may legitimately look like a variable."""

    key: TextNode = None
    value: Union[FreeFormNode, TextNode] = None

    def get_value(self, expected_type: type = None):
        # PropertyNode resolves the value type through its parent's dataclass
        # fields, which does not work for dynamically created children.
        return MappingNode.get_value(self, expected_type)

    def __getattr__(self, name: str):
        value = self.__dict__.get("value")
        if value is None:
            return None

        return getattr(value, name, None)


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------
@dataclass
class StoreFileSourceObject(ObjectNode):
    """A file taken from a repository connected to the space."""

    store: ScalarNode = None
    path: ScalarNode = None


@dataclass
class SpecSourceNode(ObjectNode):
    """The asset a grain (or a script) is based on."""

    store: ScalarNode = None
    path: ScalarNode = None
    branch: TextNode = None
    tag: TextNode = None
    commit: TextNode = None
    name: TextNode = None
    chart_version: TextNode = None
    path_in_archive: TextNode = None
    resource_type: TextNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "chart-version": "chart_version",
                "path-in-archive": "path_in_archive",
                "resource-type": "resource_type",
            }
        )
        return mapping


@dataclass
class ScriptSource(SpecSourceNode):
    """Same server side type as a grain source."""


@dataclass
class SpecSourcesSequence(SequenceNode):
    node_type = SpecSourceNode


@dataclass
class SourceFileObject(ObjectNode):
    """An element of tfvars-files / values-files / workspace-directories..."""

    source: SpecSourceNode = None


@dataclass
class SourceFilesSequence(SequenceNode):
    node_type = SourceFileObject


@dataclass
class ShellGrainFile(ObjectNode):
    """An element of a shell grain's 'files' list. Note that here 'source'
    is the name of the repository, not a nested object."""

    source: ScalarNode = None
    path: ScalarNode = None
    branch: TextNode = None
    commit: TextNode = None
    tag: TextNode = None
    name: TextNode = None


@dataclass
class ShellGrainFilesSequence(SequenceNode):
    node_type = ShellGrainFile


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------
@dataclass
class ScriptObject(ObjectNode):
    source: ScriptSource = None
    arguments: TextNode = None


@dataclass
class ScriptOutputsObject(ScriptObject):
    outputs: ScalarNodesSequence = None

    def get_outputs(self) -> List[ScalarNode]:
        return self._get_seq_nodes("outputs")


@dataclass
class GrainSpecScripts(ObjectNode):
    pre_tf_init: ScriptObject = None
    pre_tf_destroy: ScriptObject = None
    post_tf_plan: ScriptObject = None
    pre_tofu_init: ScriptObject = None
    pre_tofu_destroy: ScriptObject = None
    post_tofu_plan: ScriptObject = None
    pre_ansible_run: ScriptOutputsObject = None
    post_helm_install: ScriptOutputsObject = None
    post_kubernetes_install: ScriptOutputsObject = None
    pre_aws_cdk_deploy: ScriptOutputsObject = None
    post_aws_cdk_deploy: ScriptOutputsObject = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "pre-tf-init": "pre_tf_init",
                "pre-tf-destroy": "pre_tf_destroy",
                "post-tf-plan": "post_tf_plan",
                "pre-tofu-init": "pre_tofu_init",
                "pre-tofu-destroy": "pre_tofu_destroy",
                "post-tofu-plan": "post_tofu_plan",
                "pre-ansible-run": "pre_ansible_run",
                "post-helm-install": "post_helm_install",
                "post-kubernetes-install": "post_kubernetes_install",
                "pre-aws-cdk-deploy": "pre_aws_cdk_deploy",
                "post-aws-cdk-deploy": "post_aws_cdk_deploy",
            }
        )
        return mapping


# ---------------------------------------------------------------------------
# Shell grain activities
# ---------------------------------------------------------------------------
@dataclass
class CommandObject(ObjectNode):
    command: TextNode = None
    name: ScalarNode = None
    outputs: ScalarNodesSequence = None

    def get_outputs(self) -> List[ScalarNode]:
        return self._get_seq_nodes("outputs")

    def get_shortened_form_property(self):
        # the parent must be set, otherwise errors added to the node
        # never bubble up to the tree and are never published
        self.command = TextNode(parent=self)
        return self.command


@dataclass
class CommandsSequence(SequenceNode):
    node_type = CommandObject


@dataclass
class ActivitiesObject(ObjectNode):
    @dataclass
    class ActivityObject(ObjectNode):
        commands: CommandsSequence = None

    deploy: ActivityObject = None
    destroy: ActivityObject = None


# ---------------------------------------------------------------------------
# Execution host (agent) and runner configuration
# ---------------------------------------------------------------------------
@dataclass
class TolerationObject(ObjectNode):
    key: ScalarNode = None
    operator: ScalarNode = None
    value: TextNode = None
    effect: ScalarNode = None
    toleration_seconds: ScalarNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update({"toleration-seconds": "toleration_seconds"})
        return mapping


@dataclass
class TolerationsSequence(SequenceNode):
    node_type = TolerationObject


@dataclass
class KubernetesPermissionsObject(ObjectNode):
    destination_context_name: TextNode = None
    secret_name: TextNode = None
    secret_namespace: TextNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "destination-context-name": "destination_context_name",
                "secret-name": "secret_name",
                "secret-namespace": "secret_namespace",
            }
        )
        return mapping


@dataclass
class KubernetesObject(ObjectNode):
    pod_labels: TextMappingSequence = None
    pod_annotations: TextMappingSequence = None
    node_selector: TextMappingSequence = None
    tolerations: TolerationsSequence = None
    permissions: KubernetesPermissionsObject = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "pod-labels": "pod_labels",
                "pod-annotations": "pod_annotations",
                "node-selector": "node_selector",
            }
        )
        return mapping


@dataclass
class DockerPermissionsObject(ObjectNode):
    secret_path: TextNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update({"secret-path": "secret_path"})
        return mapping


@dataclass
class DockerObject(ObjectNode):
    permissions: DockerPermissionsObject = None


@dataclass
class RunnerConfigurationOverrideObject(ObjectNode):
    service_account: TextNode = None
    runner_namespace: TextNode = None
    isolated: ScalarNode = None
    storage_size: ScalarNode = None
    use_storage: ScalarNode = None
    kubernetes: KubernetesObject = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "service-account": "service_account",
                "runner-namespace": "runner_namespace",
                "storage-size": "storage_size",
                "use-storage": "use_storage",
            }
        )
        return mapping


@dataclass
class GrainSpecTargetObject(ObjectNode):
    name: TextNode = None
    runner_configuration_override: RunnerConfigurationOverrideObject = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {"runner-configuration-override": "runner_configuration_override"}
        )
        return mapping


# ---------------------------------------------------------------------------
# Terraform / OpenTofu specifics
# ---------------------------------------------------------------------------
@dataclass
class BackendWorkspaceObject(ObjectNode):
    name: TextNode = None
    prefix: TextNode = None
    project: TextNode = None
    tags: Union[FreeFormNode, TextNode] = None


@dataclass
class BackendWorkspacesSequence(SequenceNode):
    node_type = BackendWorkspaceObject


@dataclass
class BackendObject(ObjectNode):
    type: ScalarNode = None
    bucket: TextNode = None
    region: TextNode = None
    storage_account_name: TextNode = None
    container_name: TextNode = None
    base_address: TextNode = None
    key_prefix: TextNode = None
    skip_region_validation: ScalarNode = None
    resource_group_name: TextNode = None
    hostname: TextNode = None
    organization: TextNode = None
    token: TextNode = None
    workspaces: BackendWorkspacesSequence = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "storage-account-name": "storage_account_name",
                "container-name": "container_name",
                "base-address": "base_address",
                "key-prefix": "key_prefix",
                "skip-region-validation": "skip_region_validation",
                "resource-group-name": "resource_group_name",
            }
        )
        return mapping


@dataclass
class ProviderOverrideObject(ObjectNode):
    name: TextNode = None
    source: TextNode = None
    version: TextNode = None
    attributes: Union[FreeFormNode, TextNode] = None


@dataclass
class ProviderOverridesSequence(SequenceNode):
    node_type = ProviderOverrideObject


@dataclass
class TemplateStorageObject(ObjectNode):
    bucket_name: TextNode = None
    key_prefix: TextNode = None
    region: TextNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "bucket-name": "bucket_name",
                "key-prefix": "key_prefix",
            }
        )
        return mapping


@dataclass
class DeploymentEngineObject(ObjectNode):
    name: TextNode = None


@dataclass
class AnsibleOnDestroyObject(ObjectNode):
    source: SpecSourceNode = None
    inputs: TextMappingSequence = None
    command_arguments: TextNode = None
    scripts: GrainSpecScripts = None
    inventory_file: Union[FreeFormNode, TextNode] = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "command-arguments": "command_arguments",
                "inventory-file": "inventory_file",
            }
        )
        return mapping


# ---------------------------------------------------------------------------
# Grain spec
# ---------------------------------------------------------------------------
@dataclass
class SpecHostNode(ObjectNode):
    """The 'agent' section of a grain spec (the execution host).
    Note: 'image' is intentionally absent - the server ignores it."""

    name: TextNode = None
    region: TextNode = None
    service_account: TextNode = None
    kubernetes: KubernetesObject = None
    runner_namespace: TextNode = None
    storage_size: ScalarNode = None
    isolated: ScalarNode = None
    use_storage: ScalarNode = None
    docker: DockerObject = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "service-account": "service_account",
                "runner-namespace": "runner_namespace",
                "storage-size": "storage_size",
                "use-storage": "use_storage",
            }
        )
        return mapping


@dataclass
class GrainSpecNode(ObjectNode):
    @dataclass
    class GrainSpecTag(ObjectNode):
        auto_tag: ScalarNode = None
        disable_tags_for: ScalarNodesSequence = None

        def _get_field_mapping(self) -> Dict[str, str]:
            mapping = super()._get_field_mapping()
            mapping.update(
                {
                    "disable-tags-for": "disable_tags_for",
                    "auto-tag": "auto_tag",
                }
            )
            return mapping

    def get_outputs(self) -> List[ScalarNode]:
        return self._get_seq_nodes("outputs")

    def get_inputs(self):
        return self._get_seq_nodes("inputs")

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "env-vars": "env_vars",
                "target-namespace": "target_namespace",
                "command-arguments": "command_arguments",
                "provider-overrides": "provider_overrides",
                "auto-approve": "auto_approve",
                "auto-retry": "auto_retry",
                "built-in": "built_in",
                "values-files": "values_files",
                "workspace-directories": "workspace_directories",
                "tfvars-files": "tfvars_files",
                "opentofuvars-files": "opentofuvars_files",
                "template-storage": "template_storage",
                "application-namespace": "application_namespace",
                "deployment-engine": "deployment_engine",
                "on-destroy": "on_destroy",
                "target-resource": "target_resource",
                "stack-name-prefix": "stack_name_prefix",
                "inventory-file": "inventory_file",
            }
        )
        return mapping

    source: SpecSourceNode = None
    sources: SpecSourcesSequence = None
    inputs: TextMappingSequence = None
    outputs: ScalarNodesSequence = None
    commands: TextNodesSequence = None
    command_arguments: TextNode = None
    scripts: GrainSpecScripts = None
    tags: GrainSpecTag = None
    env_vars: TextMappingSequence = None
    env_references: TextMappingSequence = None
    region: TextNode = None
    authentication: ScalarNodesSequence = None
    activities: ActivitiesObject = None
    namespace: TextNode = None
    target_namespace: TextNode = None
    release: TextNode = None
    agent: SpecHostNode = None
    target: Union[GrainSpecTargetObject, TextNode] = None
    backend: BackendObject = None
    files: ShellGrainFilesSequence = None
    provider_overrides: ProviderOverridesSequence = None
    auto_approve: ScalarNode = None
    auto_retry: ScalarNode = None
    built_in: ScalarNode = None
    binary: ScalarNode = None
    version: TextNode = None
    values_files: SourceFilesSequence = None
    workspace_directories: SourceFilesSequence = None
    tfvars_files: SourceFilesSequence = None
    opentofuvars_files: SourceFilesSequence = None
    template_storage: TemplateStorageObject = None
    mode: TextNode = None
    application: TextNode = None
    application_namespace: TextNode = None
    deployment_engine: Union[DeploymentEngineObject, TextNode] = None
    on_destroy: AnsibleOnDestroyObject = None
    target_resource: ScalarNodesSequence = None
    stack_name_prefix: TextNode = None
    env_configuration: ScalarNode = None
    inventory_file: Union[FreeFormNode, TextNode] = None


# ---------------------------------------------------------------------------
# Grain level sections
# ---------------------------------------------------------------------------
@dataclass
class GrainLabelsObject(ObjectNode):
    """env-labels: labels applied to the environment when the grain
    succeeds or fails."""

    on_success: TextMappingSequence = None
    on_failure: TextMappingSequence = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "on-success": "on_success",
                "on-failure": "on_failure",
            }
        )
        return mapping


@dataclass
class GrainConditionChannelObject(ObjectNode):
    type: ScalarNode = None
    groups: Union[ScalarNodesSequence, ScalarNode] = None
    users: Union[ScalarNodesSequence, ScalarNode] = None
    names: Union[ScalarNodesSequence, ScalarNode] = None


@dataclass
class GrainConditionChannelsSequence(SequenceNode):
    node_type = GrainConditionChannelObject


@dataclass
class GrainConditionObject(ObjectNode):
    type: ScalarNode = None
    message: TextNode = None
    channels: GrainConditionChannelsSequence = None


@dataclass
class GrainConditionsSequence(SequenceNode):
    node_type = GrainConditionObject


@dataclass
class GrainObject(ObjectNode):
    kind: ScalarNode = None
    spec: GrainSpecNode = None
    depends_on: ScalarNode = None
    tf_version: ScalarNode = None
    when: TextNode = None
    env_labels: GrainLabelsObject = None
    condition: GrainConditionsSequence = None

    def get_deps(self) -> List[Dict]:
        if self.depends_on is None or self.depends_on.text is None:
            return []

        result = []

        deps = self.depends_on.text.split(",")
        word_end = 0

        for d in deps:
            if d == "":
                continue

            d = d.strip()

            found_on = self.depends_on.value.text.index(d, word_end)
            column_start = found_on + self.depends_on.value.start_pos[1]
            column_end = found_on + self.depends_on.value.start_pos[1] + len(d)

            start_pos = Position(self.depends_on.value.start_pos[0], column_start)
            end_pos = Position(self.depends_on.value.end_pos[0], column_end)

            result.append({"name": d, "start": start_pos, "end": end_pos})
            word_end = found_on + len(d) - 1

        return result

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "depends-on": "depends_on",
                "tf-version": "tf_version",
                "env-labels": "env_labels",
            }
        )
        return mapping


@dataclass
class GrainNode(MappingNode):
    key: ScalarNode = None
    value: GrainObject = None

    @property
    def identifier(self):
        if self.key:
            return self.key.text


# ---------------------------------------------------------------------------
# Blueprint inputs
# ---------------------------------------------------------------------------
@dataclass
class TargetLabelFilterObject(ObjectNode):
    key: ScalarNode = None
    value: TextNode = None


@dataclass
class TargetLabelFiltersSequence(SequenceNode):
    node_type = TargetLabelFilterObject


@dataclass
class TargetFiltersObject(ObjectNode):
    cloud_providers: ScalarNodesSequence = None
    cloud_identifiers: ScalarNodesSequence = None
    labels: TargetLabelFiltersSequence = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "cloud-providers": "cloud_providers",
                "cloud-identifiers": "cloud_identifiers",
            }
        )
        return mapping


@dataclass
class InputResourceSelectorObject(ObjectNode):
    type: ScalarNode = None
    provider_type: ScalarNode = None
    provider_name: ScalarNode = None
    attributes: TextMappingSequence = None
    reservable_only: ScalarNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "provider-type": "provider_type",
                "provider-name": "provider_name",
                "reservable-only": "reservable_only",
            }
        )
        return mapping


@dataclass
class BlueprintV2InputObject(ObjectNode):
    input_type: ScalarNode = None
    parameter_name: ScalarNode = None
    style: ScalarNode = None
    default: ScalarNode = None
    description: ScalarNode = None
    sensitive: ScalarNode = None
    pattern: ScalarNode = None
    validation_description: ScalarNode = None
    allowed_values: ScalarNodesSequence = None
    searchable: ScalarNode = None
    depends_on: ScalarNode = None
    source_name: ScalarNode = None
    overrides: Union[FreeFormNode, TextNode] = None
    max_size_mb: ScalarNode = None
    max_files: ScalarNode = None
    allowed_formats: ScalarNodesSequence = None
    allowed_credential_providers: ScalarNodesSequence = None
    target_filters: TargetFiltersObject = None
    resource_selector: InputResourceSelectorObject = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "type": "input_type",
                "parameter-name": "parameter_name",
                "validation-description": "validation_description",
                "allowed-values": "allowed_values",
                "depends-on": "depends_on",
                "source-name": "source_name",
                "max-size-MB": "max_size_mb",
                "max-files": "max_files",
                "allowed-formats": "allowed_formats",
                "allowed-credential-providers": "allowed_credential_providers",
                "target-filters": "target_filters",
                "resource-selector": "resource_selector",
            }
        )
        return mapping


@dataclass
class BlueprintV2InputNode(MappingNode):
    key: ScalarNode = None
    value: BlueprintV2InputObject = None


# ---------------------------------------------------------------------------
# Blueprint outputs
# ---------------------------------------------------------------------------
@dataclass
class BlueprintV2OutputObject(ObjectNode):
    value: TextNode = None
    kind: ScalarNode = None
    quick: ScalarNode = None
    sensitive: ScalarNode = None


@dataclass
class BlueprintV2OutputNode(MappingNode):
    key: ScalarNode = None
    value: BlueprintV2OutputObject = None


# ---------------------------------------------------------------------------
# Top level sections
# ---------------------------------------------------------------------------
@dataclass
class InstructionsObject(ObjectNode):
    text: TextNode = None
    source: StoreFileSourceObject = None


@dataclass
class BlueprintIconObject(ObjectNode):
    path: ScalarNode = None


@dataclass
class BlueprintLabelObject(ObjectNode):
    key: TextNode = None
    value: TextNode = None
    initial_color: ScalarNode = None
    initial_quick_filter: ScalarNode = None

    def get_shortened_form_property(self):
        # see the note in CommandObject.get_shortened_form_property
        self.key = TextNode(parent=self)
        return self.key

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "initial-color": "initial_color",
                "initial-quick-filter": "initial_quick_filter",
            }
        )
        return mapping


@dataclass
class BlueprintLabelsSequence(SequenceNode):
    node_type = BlueprintLabelObject


@dataclass
class MetadataObject(ObjectNode):
    display_name: TextNode = None
    self_service: Union[ScalarNodesSequence, ScalarNode] = None
    estimated_ccu: TextNode = None
    icon: BlueprintIconObject = None
    blueprint_labels: BlueprintLabelsSequence = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "display-name": "display_name",
                "self-service": "self_service",
                "estimated-ccu": "estimated_ccu",
                "blueprint-labels": "blueprint_labels",
            }
        )
        return mapping


@dataclass
class EnvironmentCollaboratorsObject(ObjectNode):
    collaborators_emails: ScalarNodesSequence = None
    collaborators_groups: ScalarNodesSequence = None
    all_space_members: ScalarNode = None


@dataclass
class EnvironmentObject(ObjectNode):
    """Environment metadata of an Environment-as-Code document."""

    environment_name: TextNode = None
    state: ScalarNode = None
    owner_email: TextNode = None
    spaces: ScalarNodesSequence = None
    collaborators: EnvironmentCollaboratorsObject = None
    description: TextNode = None
    tags: Union[FreeFormNode, TextNode] = None
    env_references_values: Union[FreeFormNode, TextNode] = None
    labels: Union[FreeFormNode, TextNode] = None


@dataclass
class WorkflowTriggerObject(ObjectNode):
    type: ScalarNode = None
    event: ScalarNodesSequence = None
    groups: ScalarNodesSequence = None
    cron: TextNode = None
    overridable: ScalarNode = None


@dataclass
class WorkflowTriggersSequence(SequenceNode):
    node_type = WorkflowTriggerObject


@dataclass
class WorkflowObject(ObjectNode):
    scope: ScalarNode = None
    label_selector: TextNode = None
    labels_selector: TextNode = None
    resource_types: TextNode = None
    timeout: TextNode = None
    triggers: WorkflowTriggersSequence = None
    enabled: ScalarNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "label-selector": "label_selector",
                "labels-selector": "labels_selector",
                "resource-types": "resource_types",
            }
        )
        return mapping


@dataclass
class LayoutObject(ObjectNode):
    source: StoreFileSourceObject = None
    exclude_from_layout: ScalarNodesSequence = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update({"exclude-from-layout": "exclude_from_layout"})
        return mapping


@dataclass
class ApiAccessObject(ObjectNode):
    service_account: TextNode = None


@dataclass
class EnvReferenceObject(ObjectNode):
    labels_selector: TextNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update({"labels-selector": "labels_selector"})
        return mapping


@dataclass
class EnvReferenceNode(MappingNode):
    key: ScalarNode = None
    value: EnvReferenceObject = None


@dataclass
class EnvReferencesMap(MapNode):
    node_type = EnvReferenceNode


@dataclass
class ResourceSelectorObject(ObjectNode):
    type: ScalarNode = None
    provider_type: ScalarNode = None
    provider_name: ScalarNode = None
    quantity: TextNode = None
    attributes: TextMappingSequence = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "provider-type": "provider_type",
                "provider-name": "provider_name",
            }
        )
        return mapping


@dataclass
class ResourceReferenceObject(ObjectNode):
    ids: TextNode = None


@dataclass
class ResourceRequirementObject(ObjectNode):
    selector: ResourceSelectorObject = None
    reference: Union[ResourceReferenceObject, TextNode] = None


@dataclass
class ResourceRequirementNode(MappingNode):
    key: ScalarNode = None
    value: ResourceRequirementObject = None


@dataclass
class ResourceRequirementsMap(MapNode):
    node_type = ResourceRequirementNode


@dataclass
class BlueprintFamilyObject(ObjectNode):
    members: Union[FreeFormNode, TextNode] = None


@dataclass
class BlueprintTemplatePlaceholderObject(ObjectNode):
    path: ScalarNode = None
    hint: TextNode = None


@dataclass
class BlueprintTemplatePlaceholdersSequence(SequenceNode):
    node_type = BlueprintTemplatePlaceholderObject


@dataclass
class BlueprintTemplateObject(ObjectNode):
    placeholders: BlueprintTemplatePlaceholdersSequence = None


# Maps:
@dataclass
class GrainsMap(MapNode):
    node_type = GrainNode


@dataclass
class BlueprintV2InputsMap(MapNode):
    node_type = BlueprintV2InputNode


@dataclass
class BlueprintV2OutputsMap(MapNode):
    node_type = BlueprintV2OutputNode


# The Blueprint Spec2 Tree


@dataclass
class BlueprintV2Tree(BaseTree):
    spec_version: ScalarNode = None
    description: ScalarNode = None
    instructions: InstructionsObject = None
    metadata: MetadataObject = None
    environment: EnvironmentObject = None
    workflow: WorkflowObject = None
    layout: LayoutObject = None
    labels: TextMappingSequence = None
    env_references: EnvReferencesMap = None
    resources: ResourceRequirementsMap = None
    api_access: ApiAccessObject = None
    customization: Union[FreeFormNode, TextNode] = None
    family: BlueprintFamilyObject = None
    template: BlueprintTemplateObject = None
    inputs: BlueprintV2InputsMap = None
    outputs: BlueprintV2OutputsMap = None
    grains: GrainsMap = None

    @property
    def input_list(self):
        return self._get_seq_nodes("inputs")

    def get_grains_names(self):
        return [node.key.text for node in self.grains.nodes]

    @property
    def grain_nodes(self):
        return self._get_seq_nodes("grains")
