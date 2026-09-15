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

    # -- schema navigation -------------------------------------------------

    def deref(self, node):
        """Flatten a schema node into the list of concrete object schemas it can be.

        Follows `$ref`, and spreads `allOf` / `oneOf` / `anyOf` branches into
        siblings so that a key is looked up in every branch that could carry it.
        """
        out = []
        if not isinstance(node, dict):
            return out
        if "$ref" in node:
            return self.deref(self.defs[node["$ref"].split("/")[-1]])
        combos = [c for k in ("allOf", "oneOf", "anyOf") for c in node.get(k, [])]
        if combos:
            base = {k: v for k, v in node.items() if k not in ("allOf", "oneOf", "anyOf")}
            if any(k in base for k in ("properties", "patternProperties", "additionalProperties", "items")):
                out.append(base)
            for c in combos:
                out.extend(self.deref(c))
            return out
        return [node]

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
        """Resolve one key against a list of candidate schemas.

        Returns `(segment, child_nodes)` where `segment` is the normalized path
        segment - the key itself, `<name>` for a user-chosen key, or the
        sentinels `FREE` (anything goes here) and `REJECT` (dead key).
        """
        literal, named, free = [], [], False
        for n in nodes:
            if not self.is_object(n):
                continue
            props = n.get("properties") or {}
            if key in props:
                literal.extend(self.deref(props[key]))
                continue
            hit = False
            for pat, sub in (n.get("patternProperties") or {}).items():
                if re.search(pat, key):
                    named.extend(self.deref(sub))
                    hit = True
            if hit:
                continue
            ap = n.get("additionalProperties", True)
            if isinstance(ap, dict):
                named.extend(self.deref(ap))
            elif ap is True:
                free = True
        if literal:
            return key, literal
        if named:
            return "<name>", named
        if free:
            return "FREE", []
        return "REJECT", []

    def items_for(self, nodes):
        """The schemas a list element may take, across all candidate schemas."""
        res = []
        for n in nodes:
            it = n.get("items")
            if isinstance(it, dict):
                res.extend(self.deref(it))
            elif isinstance(it, list):
                for i in it:
                    res.extend(self.deref(i))
        return res

    # -- document walking --------------------------------------------------

    def walk(self, doc, nodes=None, path="", rel=""):
        """Record every normalized key path of `doc`, descending as far as the schema knows."""
        if nodes is None:
            nodes = self.deref(self.schema)
        if isinstance(doc, dict):
            for k, v in doc.items():
                seg, kids = self.children_for_key(nodes, str(k))
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
                self.walk(v, kids, p, rel)
        elif isinstance(doc, list):
            p = path + "[]"
            self.accepted[p] += 1
            self.example.setdefault(p, rel)
            kids = self.items_for(nodes)
            for v in doc:
                self.walk(v, kids, p, rel)


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
        sys.stderr.write("usage: classify_corpus_paths.py <schema.json> <out-dir> <corpus-root>...\n")
        return 2
    schema_path, out, roots = argv[0], argv[1], argv[2:]
    schema = load_schema(schema_path)
    c, total = scan_corpus(schema, roots)

    with io.open(os.path.join(out, "required-paths.txt"), "w", encoding="utf-8") as f:
        f.write("# schema-accepted key paths observed in %d local spec2 blueprints "
                "(<name> = user-chosen key)\n" % total)
        for p in sorted(c.accepted):
            f.write(p + "\n")
    with io.open(os.path.join(out, "rejected-paths.txt"), "w", encoding="utf-8") as f:
        f.write("# observed in real blueprints but rejected by the schema (dead keys in the wild)\n")
        for p, n in sorted(c.rejected.items(), key=lambda kv: -kv[1]):
            f.write("%-70s %5d  e.g. %s\n" % (p, n, c.example[p]))

    print("blueprints %d | accepted %d | rejected %d | free-form roots %d"
          % (total, len(c.accepted), len(c.rejected), len(c.freeform)))
    print("REJECTED:")
    for p, n in sorted(c.rejected.items(), key=lambda kv: -kv[1]):
        print("  %-60s %4d  %s" % (p, n, c.example[p][:50]))
    print("FREE-FORM:")
    for p, n in sorted(c.freeform.items()):
        print("  %-60s %4d" % (p, n))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
