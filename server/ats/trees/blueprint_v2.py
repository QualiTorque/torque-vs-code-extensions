from typing import Dict, List
from dataclasses import dataclass

from server.ats.trees.common import (
    BaseTree,
    MapNode,
    MappingNode,
    ObjectNode,
    Position,
    ScalarNode,
    ScalarNodesSequence,
    SequenceNode,
    TextMappingSequence,
    TextNode,
    TextNodesSequence,
)


@dataclass
class BlueprintV2InputObject(ObjectNode):
    input_type: ScalarNode = None
    display_style: ScalarNode = None
    default: ScalarNode = None
    description: ScalarNode = None
    sensitive: ScalarNode = None
    allowed_values: ScalarNodesSequence = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "type": "input_type",
                "display-style": "display_style",
                "allowed-values": "allowed_values",
            }
        )
        return mapping


@dataclass
class BluetpintV2InputNode(MappingNode):
    key: ScalarNode = None
    value: BlueprintV2InputObject = None


@dataclass
class BlueprintV2OutputObject(ObjectNode):
    value: TextNode = None
    kind: ScalarNode = None


@dataclass
class BlueprintV2OutputNode(MappingNode):
    key: ScalarNode = None
    value: BlueprintV2OutputObject = None


@dataclass
class ScriptSource(ObjectNode):
    path: ScalarNode = None
    store: ScalarNode = None


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
    post_helm_install: ScriptOutputsObject = None
    post_kubernetes_install: ScriptOutputsObject = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "pre-tf-init": "pre_tf_init",
                "pre-tf-destroy": "pre_tf_destroy",
                "post-helm-install": "post_helm_install",
                "post-kubernetes-install": "post_kubernetes_install"
            }
        )
        return mapping


@dataclass
class CommandObject(ObjectNode):
    command: TextNode = None
    name: ScalarNode = None

    def get_shortened_form_property(self):
        self.command = TextNode()
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


@dataclass
class GrainSpecNode(ObjectNode):
    @dataclass
    class GrainAuthenticationObject(ObjectNode):
        role_arn: TextNode = None
        external_id: TextNode = None

        def _get_field_mapping(self) -> Dict[str, str]:
            mapping = super()._get_field_mapping()
            mapping.update(
                {
                    "role-arn": "role_arn",
                    "external-id": "external_id",
                }
            )
            return mapping

    @dataclass
    class SpecSourceNode(ObjectNode):
        store: ScalarNode = None
        path: ScalarNode = None
    
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

    @dataclass
    class SpecHostNode(ObjectNode):
        cloud_account: TextNode = None
        compute_service: TextNode = None
        region: TextNode = None
        service_account: TextNode = None
        name: TextNode = None
        image: TextNode = None

        def _get_field_mapping(self) -> Dict[str, str]:
            mapping = super()._get_field_mapping()
            mapping.update(
                {
                    "cloud-account": "cloud_account",
                    "compute-service": "compute_service",
                    "service-account": "service_account",
                }
            )
            return mapping

    def get_outputs(self) -> List[ScalarNode]:
        return self._get_seq_nodes("outputs")

    def get_inputs(self):
        return self._get_seq_nodes("inputs")
    
    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update({"env-vars": "env_vars"})
        return mapping

    source: SpecSourceNode = None
    host: SpecHostNode = None
    inputs: TextMappingSequence = None
    outputs: ScalarNodesSequence = None
    commands: TextNodesSequence = None
    scripts: GrainSpecScripts = None
    tags: GrainSpecTag = None
    env_vars: TextMappingSequence = None
    region: TextNode = None
    authentication: GrainAuthenticationObject = None
    activities: ActivitiesObject = None
    namespace: TextNode = None


@dataclass
class GrainObject(ObjectNode):
    kind: ScalarNode = None
    spec: GrainSpecNode = None
    depends_on: ScalarNode = None
    tf_version: ScalarNode = None

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


## Maps:
@dataclass
class GrainsMap(MapNode):
    node_type = GrainNode


@dataclass
class BluetpintV2InputsMap(MapNode):
    node_type = BluetpintV2InputNode


@dataclass
class BlueprintV2OutputsMap(MapNode):
    node_type = BlueprintV2OutputNode


## The Blueprint Spec2 Tree


@dataclass
class BlueprintV2Tree(BaseTree):
    spec_version: ScalarNode = None
    description: ScalarNode = None
    inputs: BluetpintV2InputsMap = None
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
