from typing import Dict
from dataclasses import dataclass

from server.ats.trees.common import BaseTree, MapNode, MappingNode, ObjectNode, ScalarNode, ScalarNodesSequence, TextMappingSequence, TextNode, TextNodesSequence


@dataclass
class BlueprintV2InputObject(ObjectNode):
    input_type: ScalarNode = None
    display_style: ScalarNode = None
    default: TextNode = None
    description: TextNode = None
    # sensitive: ScalarNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping = super()._get_field_mapping()
        mapping.update(
            {
                "type": "input_type",
                "display-style": "display_style"
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

@dataclass
class BlueprintV2OutputNode(MappingNode):
    key: ScalarNode = None
    value: BlueprintV2OutputObject = None


@dataclass
class GrainSpecNode(ObjectNode):
    @dataclass
    class SpecSourceNode(ObjectNode):
        store: ScalarNode = None
        path: ScalarNode = None
    
    @dataclass
    class SpecHostNode(ObjectNode):
        cloud_account: ScalarNode = None
        compute_service: ScalarNode = None
        region: ScalarNode = None

        def _get_field_mapping(self) -> Dict[str, str]:
            mapping = super()._get_field_mapping()
            mapping.update(
                {
                    "cloud-account": "cloud_account",
                    "compute-service": "compute_service"
                }
            )
            return mapping

    source: SpecSourceNode = None
    host: SpecHostNode = None
    inputs: TextMappingSequence = None
    outputs: ScalarNodesSequence = None
    commands: TextNodesSequence = None


@dataclass
class GrainObject(ObjectNode):
    kind: ScalarNode = None
    spec: GrainSpecNode = None
    depends_on: ScalarNode = None

    def _get_field_mapping(self) -> Dict[str, str]:
        mapping =  super()._get_field_mapping()
        mapping.update({
            "depends-on": "depends_on"
        })
        return mapping


@dataclass
class GrainNode(MappingNode):
    key: ScalarNode = None
    value: GrainObject = None


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

    def get_inputs(self):
        raise NotImplementedError
