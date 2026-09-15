"""Classify every YAML key path of a blueprint against the spec2 JSON schema.

Read-only. Walks a document (or a whole tree of documents) alongside
`client/schemas/blueprint-spec2-schema.json` and sorts each observed key path
into one of three buckets:

* ACCEPTED  - the path resolves to a schema node, so the key is understood;
* REJECTED  - the enclosing object is closed (`additionalProperties: false`)
              and declares no such property, so the key is dead in the wild:
              the author wrote it, the server drops it, nobody is told;
* FREE-FORM - the schema allows anything at that point, so descending further
              says nothing. The walk stops there.

Names sitting at a `patternProperties` / `additionalProperties` position are
user-chosen, so they are normalized to the literal `<name>`; a list level is
normalized to `[]`. That normalization is what makes paths comparable across
blueprints, and it is why `tests/test_schema_fixtures.py` imports this module
instead of re-implementing it - the fixture corpus' coverage check has to
normalize exactly the way the corpus scan did.

Schema-element coverage
-----------------------
A walk also records, alongside the paths, *which schema elements* the document
touched: `visited_properties` (definition, property), `visited_enum_values`
(definition, property, value) and `visited_definitions`. `enumerate_schema`
computes the same three sets from the schema alone, so
`tests/test_schema_fixtures.py` can assert that the fixture corpus reaches every
property, every enum member and every definition the schema declares. A schema
property added without a fixture then fails CI instead of going untested.

Definition names are carried through `$ref` - a node reached through
`#/definitions/X` is named `X`, and its `allOf`/`oneOf`/`anyOf` branches inherit
that name. An inline sub-schema has no name of its own, so it takes a
dotted one derived from where it sits (`Torque-Blueprint-Spec2.environment`,
`Backend.workspaces`), which keeps two unrelated inline objects that happen to
share a property name from covering for each other.

Regenerating `tests/schema_fixtures/required-paths.txt`
------------------------------------------------------
This needs the local blueprint corpus (the internal ZeroTouch repositories),
which is deliberately NOT in this repository - fixtures never carry real
content. From a machine that has the corpus checked out:

    python tools/blueprint-corpus/classify_corpus_paths.py \\
        client/schemas/blueprint-spec2-schema.json <out-dir> <corpus-root>...

It writes `<out-dir>/required-paths.txt` (the accepted paths, one per line) and
`<out-dir>/rejected-paths.txt` (the dead keys, with counts and an example
file), and prints a summary. Copy `required-paths.txt` over
`tests/schema_fixtures/required-paths.txt`, keeping its three-line header up to
date, and add a fixture for every newly required path.

Only `pyyaml` is needed on top of the standard library, and the module imports
cleanly on Python 3.7 (all command-line behaviour lives under `__main__`).
"""
import io
import json
import os
import re
import sys
from collections import Counter

import yaml

#: Directories a corpus scan must never descend into.
PRUNE = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tmp"}

#: A document is a spec2 blueprint when its `spec_version` starts with a 2.
SPEC2 = re.compile(r"^spec_version:\s*['\"]?2", re.M)

#: Name given to a schema node that was not reached through a `$ref` and has no
#: enclosing definition either - in practice only the document root.
ROOT_NAME = "<root>"

#: The normalized segment for a user-chosen key (`patternProperties` /
#: `additionalProperties`), used both in paths and in inline definition names.
NAME_SEGMENT = "<name>"

#: Schema keywords whose branches are spread into siblings rather than nested.
COMBINATORS = ("allOf", "oneOf", "anyOf")

#: Keywords that make a combinator's non-combinator siblings worth keeping: if
#: the base carries any of these it declares children of its own, so it has to
#: stay alongside the spread branches instead of being dropped.
_CHILD_BEARING_KEYWORDS = (
    "properties",
    "patternProperties",
    "additionalProperties",
    "items",
)


def spread_node(node, name, defs, note_definition, recurse):
    """Flatten one schema node into the `(definition, schema)` pairs it can be.

    The single implementation behind `PathClassifier.deref` (which walks the
    schema alongside a document) and `SchemaEnumerator.flatten` (which walks the
    schema alone). Both must apply exactly the same naming rules or the coverage
    numbers they produce stop lining up, so they share this function and differ
    only in what they hand it:

    * `defs` - the `#/definitions` map `$ref` targets are looked up in;
    * `note_definition` - called with every `$ref` target name, so each caller
      records the visit in its own set;
    * `recurse` - the caller's own method, so recursion stays within the caller
      (its `$ref` bookkeeping and, for `deref`, its document context).
    """
    out = []
    if not isinstance(node, dict):
        return out
    if "$ref" in node:
        target = node["$ref"].split("/")[-1]
        note_definition(target)
        return recurse(defs[target], target)
    combos = [c for k in COMBINATORS for c in node.get(k, [])]
    if combos:
        base = {k: v for k, v in node.items() if k not in COMBINATORS}
        if any(k in base for k in _CHILD_BEARING_KEYWORDS):
            out.append((name, base))
        for c in combos:
            out.extend(recurse(c, name))
        return out
    return [(name, node)]


def enum_member(value, members):
    """The member of `members` that `value` really is, or `None`.

    Plain `in` is wrong here: Python says `True == 1` and `1 == 1.0`, so a
    boolean document value would silently "cover" a numeric enum member it has
    nothing to do with. Booleans only ever match booleans.
    """
    for member in members:
        if isinstance(value, bool) != isinstance(member, bool):
            continue
        if value == member:
            return member
    return None


class PathClassifier(object):
    """Walks documents against one schema, accumulating normalized key paths.

    Counters are instance state, so one classifier can absorb a whole corpus
    (that is what the corpus scan does) or a single document (that is what the
    fixture coverage check does, one classifier per fixture or one for all).
    """

    def __init__(self, schema):
        self.schema = schema
        self.defs = schema.get("definitions", {})
        self.accepted = Counter()
        self.rejected = Counter()
        self.freeform = Counter()
        self.example = {}
        #: (definition, property) pairs the walk resolved a document key against.
        self.visited_properties = set()
        #: (definition, property, value) triples for enum members actually used.
        self.visited_enum_values = set()
        #: names of the `#/definitions/X` the walk passed through.
        self.visited_definitions = set()

    # -- schema navigation -------------------------------------------------

    def deref(self, node, name=ROOT_NAME):
        """Flatten a schema node into the `(definition, schema)` pairs it can be.

        Follows `$ref`, and spreads `allOf` / `oneOf` / `anyOf` branches into
        siblings so that a key is looked up in every branch that could carry it.
        `name` is the definition the node belongs to: a `$ref` replaces it with
        the target's name (and records the visit), combinator branches inherit
        it.
        """
        return spread_node(
            node, name, self.defs, self.visited_definitions.add, self.deref
        )

    @staticmethod
    def is_object(node):
        """True when a schema node can describe an object.

        `type` may be absent (anything goes, objects included), a string, or a
        *list* of strings - the input `default` is typed
        `["integer", "string", "boolean", "object"]`, and "object" being a
        member of that list is enough. Getting the list case wrong makes the
        node invisible to `children_for_key`, which then reports its children
        as dead keys instead of free-form.

        A node that declares properties is an object schema whatever its `type`
        says, which is the fallback.
        """
        declared = node.get("type")
        if declared is None:
            return True
        if isinstance(declared, list):
            if "object" in declared:
                return True
        elif declared == "object":
            return True
        return "properties" in node or "patternProperties" in node

    def children_for_key(self, nodes, key):
        """Resolve one key against a list of candidate `(definition, schema)` pairs.

        Returns `(segment, child_nodes, owners)` where `segment` is the
        normalized path segment - the key itself, `<name>` for a user-chosen
        key, or the sentinels `FREE` (anything goes here) and `REJECT` (dead
        key) - and `owners` lists every `(definition, property)` the key
        resolved to, which is what an enum value further down is attributed to.

        Every candidate that declares the key is recorded, not just the first.
        One document position can resolve against several definitions at once -
        `ResourceSelectorObject` redeclares the properties it inherits from
        `ResourceSelectorBaseObject` as stubs, and only the base carries their
        enums - so attributing to the first declarer alone would leave those
        enums permanently uncovered.
        """
        literal, named, free = [], [], False
        literal_owners, named_owners = [], []
        for dname, n in nodes:
            if not self.is_object(n):
                continue
            props = n.get("properties") or {}
            if key in props:
                self.visited_properties.add((dname, key))
                literal_owners.append((dname, key))
                literal.extend(self.deref(props[key], dname + "." + key))
                continue
            hit = False
            for pat, sub in (n.get("patternProperties") or {}).items():
                if re.search(pat, key):
                    named_owners.append((dname, NAME_SEGMENT))
                    named.extend(self.deref(sub, dname + "." + NAME_SEGMENT))
                    hit = True
            if hit:
                continue
            ap = n.get("additionalProperties", True)
            if isinstance(ap, dict):
                named_owners.append((dname, NAME_SEGMENT))
                named.extend(self.deref(ap, dname + "." + NAME_SEGMENT))
            elif ap is True:
                free = True
        if literal:
            return key, literal, tuple(literal_owners)
        if named:
            return NAME_SEGMENT, named, tuple(named_owners)
        if free:
            return "FREE", [], ()
        return "REJECT", [], ()

    def items_for(self, nodes):
        """The schemas a list element may take, across all candidate schemas."""
        res = []
        for dname, n in nodes:
            it = n.get("items")
            if isinstance(it, dict):
                res.extend(self.deref(it, dname))
            elif isinstance(it, list):
                for i in it:
                    res.extend(self.deref(i, dname))
        return res

    # -- document walking --------------------------------------------------

    def walk(self, doc, nodes=None, path="", rel="", owners=()):
        """Record every normalized key path of `doc`, descending as far as the schema knows.

        `owners` are the `(definition, property)` pairs whose schema produced
        `nodes`; they travel unchanged through list levels, so that an enum
        member written as a list element is still attributed to the property
        holding the list.
        """
        if nodes is None:
            nodes = self.deref(self.schema)
        if isinstance(doc, dict):
            for k, v in doc.items():
                seg, kids, key_owners = self.children_for_key(nodes, str(k))
                if seg == "REJECT":
                    p = path + "/" + str(k)
                    self.rejected[p] += 1
                    self.example.setdefault(p, rel)
                    continue
                if seg == "FREE":
                    p = path + "/**"
                    self.freeform[p] += 1
                    self.example.setdefault(p, rel)
                    continue
                p = path + "/" + seg
                self.accepted[p] += 1
                self.example.setdefault(p, rel)
                self.walk(v, kids, p, rel, key_owners)
        elif isinstance(doc, list):
            p = path + "[]"
            self.accepted[p] += 1
            self.example.setdefault(p, rel)
            kids = self.items_for(nodes)
            for v in doc:
                self.walk(v, kids, p, rel, owners)
        else:
            self.record_enum_value(nodes, doc, owners)

    def record_enum_value(self, nodes, value, owners):
        """Note a scalar that is a declared member of some candidate's `enum`.

        The declaration may sit on the property schema itself or on any
        `anyOf`/`oneOf` branch of it - `deref` has already spread those into
        siblings, so one pass over the candidates sees them all.
        """
        for _dname, n in nodes:
            members = n.get("enum")
            if not isinstance(members, list):
                continue
            member = enum_member(value, members)
            if member is None:
                continue
            for owner in owners:
                self.visited_enum_values.add((owner[0], owner[1], member))


class SchemaEnumerator(object):
    """Everything the schema declares, named the way `PathClassifier` names it.

    The classifier reports what a document *reached*; this reports what there is
    to reach, so the difference is the untested surface. The two walk the schema
    with the same rules (`$ref` renaming, combinator spreading, `<name>` for
    user-chosen keys) - that symmetry is the whole point, and it is why both
    live in this one module.

    Only `properties`, `patternProperties`, `additionalProperties`, `items` and
    the combinators are descended. `if` / `then` / `else` / `not` / `contains`
    are deliberately skipped: the property names inside them restate a
    constraint on properties declared elsewhere, and counting them would demand
    fixtures for keys that do not exist.
    """

    def __init__(self, schema):
        self.schema = schema
        self.defs = schema.get("definitions", {})
        self.all_properties = set()
        self.all_enum_values = set()
        self.all_definitions = set()
        self.visit(self.flatten(schema, ROOT_NAME), ())

    def flatten(self, node, name):
        """`PathClassifier.deref` without the document - same naming rules."""
        return spread_node(
            node, name, self.defs, self.all_definitions.add, self.flatten
        )

    def visit(self, nodes, owner, stack=()):
        """Collect declarations under `nodes`, attributing enums to `owner`.

        `stack` carries the definitions currently being expanded, so that a
        definition that (transitively) references itself cannot loop forever.
        Only `$ref` targets can close a loop - an inline name only ever grows -
        and the guard is a stack, not a "seen" set, so the same definition
        reached twice by different routes is still enumerated both times.
        Sibling branches of a `oneOf` share a name and an owner (`spec_version`
        is an integer enum in one branch and a string enum in the other), which
        is the other reason a global "seen" set would lose declarations.
        """
        for dname, n in nodes:
            if dname in self.defs:
                if dname in stack:
                    continue
                below = stack + (dname,)
            else:
                below = stack
            members = n.get("enum")
            if owner and isinstance(members, list):
                for member in members:
                    self.all_enum_values.add((owner[0], owner[1], member))
            for key, sub in (n.get("properties") or {}).items():
                self.all_properties.add((dname, key))
                self.visit(self.flatten(sub, dname + "." + key), (dname, key), below)
            for sub in (n.get("patternProperties") or {}).values():
                self.visit(
                    self.flatten(sub, dname + "." + NAME_SEGMENT),
                    (dname, NAME_SEGMENT),
                    below,
                )
            ap = n.get("additionalProperties")
            if isinstance(ap, dict):
                self.visit(
                    self.flatten(ap, dname + "." + NAME_SEGMENT),
                    (dname, NAME_SEGMENT),
                    below,
                )
            item = n.get("items")
            items = item if isinstance(item, list) else [item]
            for one in items:
                # A list level is not a property of its own: its elements stay
                # attributed to the property that holds the list.
                self.visit(self.flatten(one, dname), owner, below)


def load_schema(schema_path):
    with io.open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def iter_spec2_documents(roots):
    """Yield `(path, text)` for every spec2 YAML file under `roots`, pruning noise."""
    for root in roots:
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x not in PRUNE]
            for fn in files:
                if not fn.lower().endswith((".yaml", ".yml")):
                    continue
                p = os.path.join(d, fn)
                try:
                    text = io.open(p, encoding="utf-8-sig", errors="replace").read()
                except Exception:
                    continue
                if not SPEC2.search(text):
                    continue
                yield p, text


def scan_corpus(schema, roots):
    """Classify every spec2 blueprint under `roots`. Returns `(classifier, file_count)`."""
    classifier = PathClassifier(schema)
    total = 0
    for p, text in iter_spec2_documents(roots):
        total += 1
        try:
            doc = yaml.safe_load(text)
        except Exception:
            continue
        if isinstance(doc, dict):
            rel = os.path.relpath(p, os.path.dirname(roots[0]))
            classifier.walk(doc, rel=rel)
    return classifier, total


def _main(argv):
    if len(argv) < 3:
        sys.stderr.write(
            "usage: classify_corpus_paths.py <schema.json> <out-dir> <corpus-root>...\n"
        )
        return 2
    schema_path, out, roots = argv[0], argv[1], argv[2:]
    schema = load_schema(schema_path)
    c, total = scan_corpus(schema, roots)

    with io.open(os.path.join(out, "required-paths.txt"), "w", encoding="utf-8") as f:
        f.write(
            "# schema-accepted key paths observed in %d local spec2 blueprints "
            "(<name> = user-chosen key)\n" % total
        )
        for p in sorted(c.accepted):
            f.write(p + "\n")
    with io.open(os.path.join(out, "rejected-paths.txt"), "w", encoding="utf-8") as f:
        f.write(
            "# observed in real blueprints but rejected by the schema (dead keys in the wild)\n"
        )
        for p, n in sorted(c.rejected.items(), key=lambda kv: -kv[1]):
            f.write("%-70s %5d  e.g. %s\n" % (p, n, c.example[p]))

    print(
        "blueprints %d | accepted %d | rejected %d | free-form roots %d"
        % (total, len(c.accepted), len(c.rejected), len(c.freeform))
    )
    print("REJECTED:")
    for p, n in sorted(c.rejected.items(), key=lambda kv: -kv[1]):
        print("  %-60s %4d  %s" % (p, n, c.example[p][:50]))
    print("FREE-FORM:")
    for p, n in sorted(c.freeform.items()):
        print("  %-60s %4d" % (p, n))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
