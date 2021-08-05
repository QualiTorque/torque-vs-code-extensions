from server.validation.common import ValidationHandler
from typing import List
from server.constants import PREDEFINED_COLONY_INPUTS


class AppValidationHandler(ValidationHandler):
    def validate_script_files_exist(self):
        # TODO: move the code from server.py to here after having the configuration tree ready
        pass

    def validate(self, text_doc):
        super().validate()
        # errors
        self.validate_script_files_exist()

        return self._diagnostics
