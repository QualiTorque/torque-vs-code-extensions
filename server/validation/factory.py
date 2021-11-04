from pygls.workspace import Document
from .srv_validator import ServiceValidationHandler
from .app_validator import AppValidationHandler
from .bp_validatior import BlueprintValidationHandler
from ..ats.trees.common import BaseTree


class ValidatorFactory:
    kind_validators_map = {
        'blueprint': BlueprintValidationHandler,
        'application': AppValidationHandler,
        'terraform': ServiceValidationHandler
    }

    @classmethod
    def get_validator(cls, tree: BaseTree, text_doc: Document):
        if tree.kind is None:
            raise ValueError("Unable to validate document. 'kind' property is not defined")

        kind = tree.kind.text.lower()

        if kind not in cls.kind_validators_map:
            options = ", ".join(list(cls.kind_validators_map.keys()))
            raise ValueError(f"'kind' property is not correct. Must be in {options}")

        validator_cls: type = cls.kind_validators_map[kind]

        return validator_cls(tree, text_doc)
