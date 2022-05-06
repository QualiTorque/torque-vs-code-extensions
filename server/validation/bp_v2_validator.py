from server.ats.trees.blueprint_v2 import BlueprintV2Tree
from server.validation.common import ValidationHandler
from pygls.workspace import Document

class BlueprintSpec2Validator(ValidationHandler):
    def __init__(self, tree: BlueprintV2Tree, document: Document) -> None:
        self.tree = tree
        super().__init__(tree, document)

    def _get_grains_names(self):
        return [node.key.text for node in self.tree.grains.nodes]
    
    def _validate_grain_dep_exists(self):
        for grain in self.tree.grains.nodes:
            grain_name = grain.key.text
            grains_list = self._get_grains_names()
            depend = grain.value.depends_on if grain.value else None

            if depend is None:
                continue
                
            if depend.text not in grains_list:
                self._add_diagnostic(
                    depend.value,
                    message=f"The grain '{grain_name}' depends on undefined resource",
                )
            
            if depend.text == grain_name:
                self._add_diagnostic(
                    depend.value,
                    message=f"The grain '{grain_name}' cannot be dependent onx§x itself",
                )
            

    def validate(self):
        self._validate_grain_dep_exists()
        return self._diagnostics

