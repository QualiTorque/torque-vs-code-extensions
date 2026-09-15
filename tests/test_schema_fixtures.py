"""Regression corpus for the spec2 JSON schema.

`tests/schema_fixtures/` holds minimal, generic blueprints that stand in for the
real ones:

* `valid/*.yaml`   - must validate with **zero** errors;
* `invalid/*.yaml` - must produce **at least one** error, and every
                     `# expect-error: <substring>` line in the file's header
                     must be satisfied by some error message;
* `required-paths.txt` - the schema-accepted key paths that 528 local spec2
                     blueprints actually use. The union of the paths exercised
                     by the valid fixtures has to cover all of them, which is
                     what ties this hand-written corpus to the real one.

Three defect classes are covered that nothing else here catches: a shape real
blueprints rely on stops validating, a dead key starts being silently accepted,
and a schema-only construct (a grain kind or input type no local blueprint uses)
quietly disappears.

Matching is done against **all** error messages, nested `oneOf`/`anyOf`
sub-errors included, because most interesting keys sit inside a combinator and
the outermost message is only ever "is not valid under any of the given
schemas".

Fixtures never contain real content - no hostnames, addresses, repository or
product names, credentials or company names. `example`, `my-grain`, `agent-1`
and friends, always.

Imports are limited to `yaml`, `jsonschema` and the standard library, so the
module runs unchanged on Python 3.7 (the pinned server stack) and on 3.12 (the
`schema-fixtures` CI job).
"""
import io
import json
import os
import unittest

import yaml
from jsonschema import Draft6Validator
from jsonschema.exceptions import best_match

try:  # Python 3.5+; spelled out so the failure mode is obvious on an older one.
    import importlib.util as _importlib_util
except ImportError:  # pragma: no cover
    _importlib_util = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCHEMA_PATH = os.path.join(REPO, "client", "schemas", "blueprint-spec2-schema.json")
FIXTURES = os.path.join(HERE, "schema_fixtures")
VALID_DIR = os.path.join(FIXTURES, "valid")
INVALID_DIR = os.path.join(FIXTURES, "invalid")
REQUIRED_PATHS = os.path.join(FIXTURES, "required-paths.txt")

#: Header marker of an invalid fixture, one line per expected error substring.
EXPECT_PREFIX = "# expect-error:"


def _load_classifier_module():
    """Import the corpus classifier by path.

    `tools/blueprint-corpus` has a hyphen in it, so it is not importable as a
    package. Loading it by file path is what lets the coverage check normalize
    key paths with the very same code that produced `required-paths.txt`,
    instead of a second implementation that could drift from it.
    """
    path = os.path.join(REPO, "tools", "blueprint-corpus", "classify_corpus_paths.py")
    spec = _importlib_util.spec_from_file_location("blueprint_corpus_classifier", path)
    module = _importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


classifier_module = _load_classifier_module()

with io.open(SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = json.load(_f)
VALIDATOR = Draft6Validator(SCHEMA)


def fixture_files(directory):
    return sorted(fn for fn in os.listdir(directory) if fn.endswith((".yaml", ".yml")))


def read_fixture(directory, name):
    with io.open(os.path.join(directory, name), encoding="utf-8") as f:
        return f.read()


def expected_errors(text):
    """The `# expect-error:` substrings declared in a fixture's header."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(EXPECT_PREFIX):
            out.append(stripped[len(EXPECT_PREFIX):].strip())
    return out


def first_key_line(text):
    """The first line of a fixture that is neither blank nor a comment."""
    for line in text.splitlines():
        if line.strip() and not line.strip().startswith("#"):
            return line
    return ""


def json_path(path):
    return "/" + "/".join(str(p) for p in path) if path else "<document>"


def drilled_errors(error, prefix=()):
    """Yield `(path, message)` for an error and every nested sub-error.

    A `oneOf`/`anyOf` failure keeps the real reason in `error.context`, and a
    sub-error's `absolute_path` is relative to its parent's instance, so the
    parent path is carried down as a prefix.
    """
    path = tuple(prefix) + tuple(error.absolute_path)
    yield path, error.message
    for sub in error.context or []:
        for item in drilled_errors(sub, path):
            yield item


def all_messages(document):
    """Every error message the schema produces for `document`, nesting included.

    `best_match` is applied on top: it walks a different way down the combinator
    tree (following the most relevant branch) and can surface a message the
    plain recursion words differently.
    """
    collected = []
    for error in VALIDATOR.iter_errors(document):
        collected.extend(drilled_errors(error))
    match = best_match(VALIDATOR.iter_errors(document))
    if match is not None:
        collected.extend(drilled_errors(match))
    # best_match re-walks ground the recursion already covered, so the same
    # (path, message) can arrive twice. Dedupe, keeping the original order.
    out, seen = [], set()
    for item in collected:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def format_messages(messages):
    return "\n".join("    %s: %s" % (json_path(p), m) for p, m in messages)


def required_paths():
    out = []
    with io.open(REQUIRED_PATHS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


class TestValidFixtures(unittest.TestCase):
    """Every shape the real blueprints rely on still validates."""

    def test_valid_fixtures_have_no_errors(self):
        names = fixture_files(VALID_DIR)
        self.assertTrue(names, "no valid fixtures found in %s" % VALID_DIR)
        for name in names:
            with self.subTest(fixture=name):
                text = read_fixture(VALID_DIR, name)
                document = yaml.safe_load(text)
                self.assertIsInstance(
                    document, dict, "%s must parse as a YAML mapping" % name)
                self.assertTrue(
                    first_key_line(text).startswith("spec_version"),
                    "%s must start with spec_version" % name)
                messages = all_messages(document)
                self.assertEqual(
                    [], messages,
                    "%s is expected to validate, but the schema reports:\n%s"
                    % (name, format_messages(messages)))


class TestInvalidFixtures(unittest.TestCase):
    """Every defect the schema is supposed to catch is still caught.

    A fixture that produces no error at all is the real failure here: that is
    the silently-accepted dead key this corpus exists to prevent.
    """

    def test_invalid_fixtures_report_the_expected_errors(self):
        names = fixture_files(INVALID_DIR)
        self.assertTrue(names, "no invalid fixtures found in %s" % INVALID_DIR)
        for name in names:
            with self.subTest(fixture=name):
                text = read_fixture(INVALID_DIR, name)
                document = yaml.safe_load(text)
                self.assertIsInstance(
                    document, dict, "%s must parse as a YAML mapping" % name)
                expectations = expected_errors(text)
                self.assertTrue(
                    expectations,
                    "%s declares no '%s' line, so it pins nothing"
                    % (name, EXPECT_PREFIX))
                # Only the deliberate missing-spec_version fixture may omit it.
                if not any("spec_version" in e for e in expectations):
                    self.assertTrue(
                        first_key_line(text).startswith("spec_version"),
                        "%s must start with spec_version" % name)

                messages = all_messages(document)
                self.assertTrue(
                    messages,
                    "%s is expected to be rejected, but the schema accepts it "
                    "- a defect is being silently swallowed" % name)
                blob = "\n".join(m for _, m in messages).lower()
                unmatched = [e for e in expectations if e.lower() not in blob]
                self.assertEqual(
                    [], unmatched,
                    "%s: no error message matches %s. Reported:\n%s"
                    % (name, unmatched, format_messages(messages)))


class TestRequiredPathCoverage(unittest.TestCase):
    """The corpus really is derived from the real blueprints.

    Every key path the 528 local spec2 blueprints use has to be exercised by at
    least one valid fixture, so that a shape going missing from the schema
    breaks a test instead of breaking a customer.
    """

    def test_valid_fixtures_cover_every_required_path(self):
        classifier = classifier_module.PathClassifier(SCHEMA)
        for name in fixture_files(VALID_DIR):
            document = yaml.safe_load(read_fixture(VALID_DIR, name))
            classifier.walk(document, rel=name)
        covered = set(classifier.accepted)

        required = required_paths()
        self.assertTrue(required, "%s lists no paths" % REQUIRED_PATHS)
        missing = [p for p in required if p not in covered]
        self.assertEqual(
            [], missing,
            "%d of %d required key paths are not exercised by any valid "
            "fixture:\n%s" % (len(missing), len(required),
                              "\n".join("    " + p for p in missing)))


class TestPathClassifier(unittest.TestCase):
    """The path normalization itself, where a subtle bug costs real coverage.

    A schema node whose `type` is a *list* containing "object" - the input
    `default`, typed `["integer", "string", "boolean", "object"]` - is an object
    schema. Miss that and the node becomes invisible to `children_for_key`,
    which reports the keys underneath it as dead. They are not dead: the node
    declares no properties and does not close itself, so anything is allowed
    there and the walk has to stop with a free-form marker instead.

    A false REJECT is not cosmetic - `rejected-paths.txt` is where the
    `invalid/` fixtures come from, so a phantom entry there becomes a fixture
    asserting that a perfectly legal key must be refused.
    """

    #: A dictionary input whose default is an object - legal, and the shape
    #: that used to be misclassified.
    DICTIONARY_INPUT = {
        "spec_version": 2,
        "inputs": {
            "settings": {
                "type": "dictionary",
                "default": {"key": "value"},
            }
        },
    }

    def test_union_typed_node_is_an_object_schema(self):
        is_object = classifier_module.PathClassifier.is_object
        self.assertTrue(is_object({"type": ["integer", "string", "boolean", "object"]}))
        self.assertTrue(is_object({"type": "object"}))
        self.assertTrue(is_object({}), "an absent type allows an object")
        self.assertTrue(is_object({"type": "array", "properties": {"a": {}}}),
                        "declared properties make it an object schema")
        self.assertFalse(is_object({"type": ["integer", "string"]}))
        self.assertFalse(is_object({"type": "string"}))

    def test_object_default_classifies_as_free_form_not_rejected(self):
        # The schema really does accept it, so the classifier must not disagree.
        self.assertEqual([], all_messages(self.DICTIONARY_INPUT))

        classifier = classifier_module.PathClassifier(SCHEMA)
        classifier.walk(self.DICTIONARY_INPUT, rel="synthetic")
        self.assertEqual(
            {}, dict(classifier.rejected),
            "no key of a dictionary input with an object default is dead")
        self.assertIn("/inputs/<name>/default", classifier.accepted)
        self.assertIn("/inputs/<name>/default/**", classifier.freeform)


if __name__ == "__main__":
    unittest.main()
