import pathlib
from server.validation.common import ValidationHandler
from typing import List
from server.constants import PREDEFINED_COLONY_INPUTS


class AppValidationHandler(ValidationHandler):
    def validate_script_files_exist(self):
        # TODO: move the code from server.py to here after having the configuration tree ready
        pass

    def _get_repo_root_path(self):
        path = pathlib.Path(self._document_path).absolute()
        if path.parents[1].name == "applications":
            return path.parents[2].absolute().as_posix()

        else:
            raise ValueError(f"Wrong document path of application file: {path.as_posix()}")

    def validate(self, text_doc):
        super().validate()
        # errors
        self.validate_script_files_exist()

        return self._diagnostics
