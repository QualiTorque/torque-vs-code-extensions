from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO


class StringYAML(YAML):
    def dump(self, data, stream=None, **kw):
        inefficient = False
        if stream is None:
            inefficient = True
            stream = StringIO()
        YAML.dump(self, data, stream, **kw)
        if inefficient:
            return stream.getvalue()

def format_yaml(input):
    yaml = StringYAML()
    data = yaml.load(input)
    yaml.indent(sequence=4, offset=2)
    output = yaml.dump(data)
    return output