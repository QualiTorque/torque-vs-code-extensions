"""The spec2 schema is customer-facing: the Torque web UI fetches it live from this
repository's master branch and shows its descriptions on hover, and anyone can read
the raw file. Every title, description and $comment must therefore read as product
documentation - no server class or method names, no error codes, no source-file
paths, no internal tooling or repository names, no numbers from our private
blueprint corpus. Provenance for a rule belongs in docs/spec2-language-support.md,
not in the schema.

Runs on any Python with only the standard library and the schema file.
"""
import io
import json
import os
import re
import unittest

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "client", "schemas", "blueprint-spec2-schema.json"
)

# Patterns that must never appear in customer-facing text.
BANNED_EVERYWHERE = {
    "server class or method name": re.compile(
        r"\b[A-Z][A-Za-z0-9]*(Yaml|Validator|Fields|Service|Processor|Handler|Helper|Resolver"
        r"|Profile|Consts|Evaluator|Extractor|Deserializer|Mapping|Descriptor|Factory|Context)\b"
    ),
    "error code": re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+){2,}\b"),
    "source file or path": re.compile(r"\b\w+\.(cs|tsx?|py|json|md|yaml)\b|[A-Za-z]:\\|/server/|portal/src"),
    "internal tooling word": re.compile(
        r"\b(cs2018|AutoMapper|YamlMember|YamlShortSyntax|IgnoreUnmatchedProperties|SmartEnum"
        r"|isMandatory|deserializ\w*|IsNullOrEmpty|TryParse|OrdinalIgnoreCase|StringComparer"
        r"|GetExtension|Draft\d|draft-\d|jsonschema|DotLiquid|RunnerMgmt)\b"
    ),
    "internal corpus or repository": re.compile(
        r"\b(corpus|ZeroTouch|zero-touch|vmaas|Compute3|zt-test|bmaas|\d+ of \d+ real)\b"
    ),
    "line reference": re.compile(r"\bline ~?\d+\b|\.cs:\d+"),
    "R&D voice": re.compile(r"\b(we|our|R&D|RnD|the coordinator|the other agent|todo|TODO|FIXME)\b"),
}

# JSON Schema keywords are the language this file is written in, so a $comment may
# name them; a description shown to a blueprint author may not.
BANNED_IN_DESCRIPTIONS = {
    "JSON Schema keyword in prose": re.compile(
        r"\b(allOf|oneOf|anyOf|additionalProperties|patternProperties|unevaluatedProperties"
        r"|propertyNames|\$ref|\$comment|subschema)\b"
    ),
    "implementation voice": re.compile(r"\bthe server\b|\bserver-side\b|\bthe deserializer\b|\bthe parser\b"),
}


def texts():
    with io.open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    found = []

    def walk(node, path):
        if isinstance(node, dict):
            for key in ("title", "description", "markdownDescription", "$comment"):
                value = node.get(key)
                if isinstance(value, str):
                    found.append((path.replace("/definitions/", ""), key, value))
            for key, value in node.items():
                if key not in ("title", "description", "markdownDescription", "$comment"):
                    walk(value, path + "/" + key)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, path + "/" + str(i))

    walk(schema, "")
    return found


class TestSchemaTextIsCustomerFacing(unittest.TestCase):
    def test_no_internal_identifiers_anywhere(self):
        for path, key, value in texts():
            for label, pattern in BANNED_EVERYWHERE.items():
                match = pattern.search(value)
                with self.subTest(path=path, key=key, rule=label):
                    self.assertIsNone(
                        match, "%s in %s [%s]: %r" % (label, path, key, match and match.group(0))
                    )

    def test_descriptions_speak_to_blueprint_authors(self):
        for path, key, value in texts():
            if key == "$comment":
                continue
            for label, pattern in BANNED_IN_DESCRIPTIONS.items():
                match = pattern.search(value)
                with self.subTest(path=path, key=key, rule=label):
                    self.assertIsNone(
                        match, "%s in %s [%s]: %r" % (label, path, key, match and match.group(0))
                    )

    def test_every_description_is_a_sentence(self):
        # a description that is a bare fragment ("Helm release name") is acceptable; one that is
        # empty or whitespace is not
        for path, key, value in texts():
            if key in ("description", "markdownDescription"):
                with self.subTest(path=path):
                    self.assertTrue(value.strip(), "empty description at %s" % path)


if __name__ == "__main__":
    unittest.main()
