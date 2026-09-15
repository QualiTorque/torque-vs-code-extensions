"""Syntactic health of the customer-facing spec2 schema file.

`json.load` accepts duplicate object keys and silently keeps the last one, so a
schema with two `$comment` (or two `description`, or two `properties`) keys in
one object parses, validates and passes every other test while a consumer that
keeps the FIRST occurrence sees different content. This module parses with an
`object_pairs_hook` so duplicates fail loudly, and pins the file's encoding and
declared draft. Standard library plus jsonschema only.
"""
import io
import json
import os
import unittest

from jsonschema import Draft7Validator

SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "client", "schemas", "blueprint-spec2-schema.json"
)


def load_reporting_duplicates():
    duplicates = []

    def hook(pairs):
        seen = set()
        for key, _ in pairs:
            if key in seen:
                duplicates.append(key)
            seen.add(key)
        return dict(pairs)

    with io.open(SCHEMA_PATH, encoding="utf-8") as f:
        raw = f.read()
    return raw, json.loads(raw, object_pairs_hook=hook), duplicates


class TestSchemaSyntax(unittest.TestCase):
    def test_no_duplicate_keys_in_any_object(self):
        _, _, duplicates = load_reporting_duplicates()
        self.assertEqual([], duplicates, "duplicate keys inside one object: %r" % duplicates)

    def test_encoding_is_utf8_without_bom_and_lf_only(self):
        with io.open(SCHEMA_PATH, "rb") as f:
            head = f.read(3)
            body = head + f.read()
        self.assertNotEqual(b"\xef\xbb\xbf", head, "schema must not start with a UTF-8 BOM")
        self.assertNotIn(b"\r", body, "schema must use LF line endings")
        body.decode("utf-8")  # raises on invalid UTF-8

    def test_declares_draft_07_and_is_a_valid_schema(self):
        _, schema, _ = load_reporting_duplicates()
        self.assertEqual("http://json-schema.org/draft-07/schema#", schema.get("$schema"))
        Draft7Validator.check_schema(schema)

    def test_every_ref_resolves(self):
        _, schema, _ = load_reporting_duplicates()
        definitions = set(schema.get("definitions", {}))
        dangling = []

        def walk(node):
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str):
                    if not ref.startswith("#/definitions/") or ref.split("/")[-1] not in definitions:
                        dangling.append(ref)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(schema)
        self.assertEqual([], dangling, "unresolvable $ref: %r" % dangling)


if __name__ == "__main__":
    unittest.main()
