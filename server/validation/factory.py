from pygls.workspace import Document
from server.ats.trees.common import BaseTree
from server.validation.app_validator import AppValidationHandler
from server.validation.bp_v2_validator import BlueprintSpec2Validator
from server.validation.bp_validatior import BlueprintValidationHandler
from server.validation.srv_validator import ServiceValidationHandler


class ValidatorFactory:
    kind_validators_map = {
        "blueprint": BlueprintValidationHandler,
        "application": AppValidationHandler,
        "terraform": ServiceValidationHandler,
    }

    @classmethod
    def get_validator(cls, tree: BaseTree, text_doc: Document):
        spec = tree.spec_version.text

        if spec in ["2-preview", '2', 2]:
            return BlueprintSpec2Validator(tree, text_doc)

        elif spec in [1, "1"]:
            if tree.kind is None:
                raise ValueError(
                    "Unable to validate document. 'kind' property is not defined"
                )

            kind = tree.kind.text.lower()

            if kind not in cls.kind_validators_map:
                options = ", ".join(list(cls.kind_validators_map.keys()))
                raise ValueError(f"'kind' property is not correct. Must be in {options}")

            validator_cls: type = cls.kind_validators_map[kind]

            return validator_cls(tree, text_doc)

        else:
            return None   
