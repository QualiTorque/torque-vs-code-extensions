#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run both Torque blueprint validation layers over a corpus of blueprint YAML.

PURPOSE
-------
This is a *human-operated* test harness for the Torque VS Code extension. Point
it at a directory of spec_version 2 blueprints (typically a sanitized copy of a
customer repository, see the sibling ``sanitize_blueprints.py``) and it will run
every blueprint through the two validation layers the extension ships:

  Layer 1 - JSON schema      ``client/schemas/blueprint-spec2-schema.json``
                             evaluated with ``jsonschema.Draft6Validator``.
                             This is what VS Code's YAML/JSON-schema engine
                             shows the blueprint author as they type.

  Layer 2 - language server  ``server.ats.parser.Parser`` builds the tree and
                             ``server.validation.bp_v2_validator``
                             ``BlueprintSpec2Validator`` runs the semantic
                             checks. This is what the extension's Python
                             language server publishes as diagnostics.

The output is a set of report files for a human to read. Findings that are
already understood are filtered through a catalog (``known_findings.json``) so
that whatever is left - the *NEW* clusters - are the candidate tool bugs worth
investigating.

CONFIDENTIALITY MODEL
---------------------
Customer blueprints must not be handed to an AI, and this script is built around
that rule. It never sends anything anywhere (no network calls at all) and never
modifies the corpus (it is opened read-only). Its reports come in two levels:

  ``--level full``  (default)  Reports may quote blueprint content: property
                               names, message text and source lines. Every file
                               is stamped "FULL - treat as confidential".
                               For the human's eyes only.

  ``--level safe``             ``findings.txt`` / ``findings.json`` carry no
                               source lines and no raw messages - only
                               normalized message templates and counts.

Independently of ``--level``, the script *always* writes ``safe-summary.txt``:
message templates, schema sections, rejected property names, counts, and
anonymous ``bp_0001`` file ids - never a value, a source line, a raw message or
a file name. That is the one file the human may paste into a chat with an AI to
get help interpreting the results, and it is safe unconditionally rather than
safe-only-if-the-right-flag-was-passed: a basename like ``acme-prod-deploy.yaml``
can identify a customer by itself, so ``safe-summary.txt`` always uses ids. The
id-to-path mapping is written *only* to ``path-map.txt``, which is marked
confidential and is what the human uses to resolve an id locally.
``--anonymize-paths`` extends the same anonymization to the other three reports.

WHY THERE IS A pygls STUB IN HERE
---------------------------------
``server/validation/*`` and ``server/ats/trees/common.py`` import from ``pygls``,
and the repository pins ``pygls==0.11.3``, which only builds on Python 3.6/3.7.
On a modern interpreter the import simply fails, which would make this script
unusable. So: real pygls is used when it imports, and otherwise a minimal stub
providing exactly the handful of names those modules touch is installed into
``sys.modules``. The report header always states which mode was used.

REQUIREMENTS
------------
Python 3.7+, ``pyyaml`` and ``jsonschema``. Nothing else.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import traceback

SCRIPT_PATH = os.path.abspath(__file__)
SCRIPT_DIR = os.path.dirname(SCRIPT_PATH)
DEFAULT_REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir, os.pardir))
DEFAULT_TRIAGE_PATH = os.path.join(SCRIPT_DIR, "known_findings.json")

SCHEMA_RELPATH = os.path.join("client", "schemas", "blueprint-spec2-schema.json")

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_CRASHES = 2
EXIT_SETUP = 3
EXIT_UNEXPECTED = 4

# Soft dependency imports: a missing dependency has to become a clean exit 3
# with an actionable message rather than a traceback at import time.
try:
    import yaml

    _YAML_ERROR = None
except Exception as _exc:  # pragma: no cover - environment dependent
    yaml = None
    _YAML_ERROR = _exc

try:
    import jsonschema

    _JSONSCHEMA_ERROR = None
except Exception as _exc:  # pragma: no cover - environment dependent
    jsonschema = None
    _JSONSCHEMA_ERROR = _exc


# =============================================================================
# BEGIN pygls compatibility shim
# =============================================================================
# The language server modules this script drives import a small number of names
# from pygls. The repository pins pygls==0.11.3, whose wheel/sdist only installs
# on Python 3.6/3.7, so on any modern interpreter `import pygls` fails and the
# whole of layer 2 becomes unreachable.
#
# Rather than force the human to keep a Python 3.7 around, we install a minimal
# stand-in into sys.modules *before* the server packages are imported. The stub
# deliberately mirrors only what is actually reached:
#
#   pygls.lsp.types                    imported wholesale as `types` by
#                                      server/ats/trees/common.py, which uses
#                                      `types.Position`.
#   pygls.lsp.types.basic_structures   Diagnostic, DiagnosticSeverity, Position,
#                                      Range  (server/validation/common.py,
#                                      server/validation/bp_v2_validator.py)
#   pygls.workspace                    Document  (used as a type annotation only,
#                                      never instantiated by us - this script
#                                      passes its own CorpusDocument)
#
# Fidelity matters: the findings this script reports must be identical whether
# real pygls or the stub is in play. Everything we read off a Diagnostic
# (.message, .range.start.line, .range.start.character, .severity) is a plain
# attribute, and DiagnosticSeverity keeps pygls 0.11.3's exact member names so
# `severity.name` renders identically. The models also reject a missing required
# field or a non-integer coordinate, raising an exception named ValidationError -
# the same type name pydantic uses in real pygls - so even the pathological
# "validator built a bad Diagnostic" case is classified and rendered the same
# way in both modes.
import enum
import types as _pytypes


class _StubValidationError(ValueError):
    """Stands in for pydantic's ValidationError (same type name on purpose)."""


_StubValidationError.__name__ = "ValidationError"
_StubValidationError.__qualname__ = "ValidationError"


def _stub_int(field, value):
    if value is None or isinstance(value, bool):
        raise _StubValidationError("%s: value is not a valid integer" % field)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise _StubValidationError("%s: value is not a valid integer" % field)


class _StubPosition(object):
    __slots__ = ("line", "character")

    def __init__(self, line=None, character=None, **_ignored):
        self.line = _stub_int("line", line)
        self.character = _stub_int("character", character)

    def __eq__(self, other):
        return (
            isinstance(other, _StubPosition)
            and self.line == other.line
            and self.character == other.character
        )

    def __hash__(self):
        return hash((self.line, self.character))

    def __repr__(self):
        return "Position(line=%r, character=%r)" % (self.line, self.character)


class _StubRange(object):
    __slots__ = ("start", "end")

    def __init__(self, start=None, end=None, **_ignored):
        if start is None or end is None:
            raise _StubValidationError("range: field required")
        self.start = start
        self.end = end

    def __eq__(self, other):
        return (
            isinstance(other, _StubRange)
            and self.start == other.start
            and self.end == other.end
        )

    def __hash__(self):
        return hash((self.start, self.end))

    def __repr__(self):
        return "Range(start=%r, end=%r)" % (self.start, self.end)


class _StubDiagnosticSeverity(enum.IntEnum):
    # pygls 0.11.3 member names, verbatim.
    Error = 1
    Warning = 2
    Information = 3
    Hint = 4


class _StubDiagnostic(object):
    __slots__ = (
        "range",
        "severity",
        "code",
        "code_description",
        "source",
        "message",
        "tags",
        "related_information",
        "data",
    )

    def __init__(
        self,
        range=None,
        message=None,
        severity=None,
        code=None,
        code_description=None,
        source=None,
        tags=None,
        related_information=None,
        data=None,
        **_ignored
    ):
        if range is None:
            raise _StubValidationError("range: field required")
        if message is None:
            raise _StubValidationError("message: field required")
        self.range = range
        self.message = message if isinstance(message, str) else str(message)
        self.severity = severity
        self.code = code
        self.code_description = code_description
        self.source = source
        self.tags = tags
        self.related_information = related_information
        self.data = data

    def __repr__(self):
        return "Diagnostic(range=%r, message=%r, severity=%r)" % (
            self.range,
            self.message,
            self.severity,
        )


class _StubDocument(object):
    """Placeholder for pygls.workspace.Document (annotation target only)."""

    def __init__(self, uri="", source="", version=0):
        self.uri = uri
        self.path = uri
        self.source = source
        self.version = version

    @property
    def lines(self):
        return self.source.splitlines(True)


# Present the stub types under pygls' own names, so that a repr or an exception
# text that happens to reach a report reads the same in both modes.
for _stub_cls, _real_name in (
    (_StubPosition, "Position"),
    (_StubRange, "Range"),
    (_StubDiagnostic, "Diagnostic"),
    (_StubDiagnosticSeverity, "DiagnosticSeverity"),
    (_StubDocument, "Document"),
):
    _stub_cls.__name__ = _real_name
    _stub_cls.__qualname__ = _real_name
del _stub_cls, _real_name


def _install_pygls_stub():
    """Register the minimal pygls surface in sys.modules. Returns nothing."""
    pygls_mod = _pytypes.ModuleType("pygls")
    pygls_mod.__path__ = []
    pygls_mod.__version__ = "0.11.3-stub"

    lsp_mod = _pytypes.ModuleType("pygls.lsp")
    lsp_mod.__path__ = []

    types_mod = _pytypes.ModuleType("pygls.lsp.types")
    types_mod.__path__ = []

    basic_mod = _pytypes.ModuleType("pygls.lsp.types.basic_structures")
    workspace_mod = _pytypes.ModuleType("pygls.workspace")

    for module in (types_mod, basic_mod):
        module.Position = _StubPosition
        module.Range = _StubRange
        module.Diagnostic = _StubDiagnostic
        module.DiagnosticSeverity = _StubDiagnosticSeverity
        module.ValidationError = _StubValidationError

    types_mod.basic_structures = basic_mod

    workspace_mod.Document = _StubDocument

    def _position_from_utf16(lines, position):
        return position

    workspace_mod.position_from_utf16 = _position_from_utf16

    lsp_mod.types = types_mod
    pygls_mod.lsp = lsp_mod
    pygls_mod.workspace = workspace_mod

    sys.modules["pygls"] = pygls_mod
    sys.modules["pygls.lsp"] = lsp_mod
    sys.modules["pygls.lsp.types"] = types_mod
    sys.modules["pygls.lsp.types.basic_structures"] = basic_mod
    sys.modules["pygls.workspace"] = workspace_mod


def ensure_pygls():
    """Make `import pygls...` work. Returns (mode_label, using_stub)."""
    try:
        import pygls  # noqa: F401
        from pygls.lsp import types as _t  # noqa: F401
        from pygls.lsp.types.basic_structures import (  # noqa: F401
            Diagnostic,
            DiagnosticSeverity,
            Position,
            Range,
        )
        from pygls.workspace import Document  # noqa: F401
    except Exception:
        _install_pygls_stub()
        return (
            "STUB (findings verified equivalent to real pygls on the "
            "reference corpus)",
            True,
        )

    version = getattr(sys.modules["pygls"], "__version__", None)
    if not version:
        # pygls 0.11.3 exposes no __version__, and importlib.metadata only
        # exists from 3.8 - which is exactly the interpreter where real pygls
        # still installs. So try both.
        try:
            import importlib.metadata as _md

            version = _md.version("pygls")
        except Exception:
            try:
                import pkg_resources

                version = pkg_resources.get_distribution("pygls").version
            except Exception:
                version = "unknown version"
    return ("real %s" % version, False)


# =============================================================================
# END pygls compatibility shim
# =============================================================================


class CorpusDocument(object):
    """The document object the validators expect, backed by a corpus file.

    ``BlueprintSpec2Validator`` and its ``ValidationHandler`` base only ever
    touch ``.lines`` and ``.source``; ``.path``/``.uri`` are there because other
    validators in the same package read them and it costs nothing to be safe.
    A purpose-built class is used instead of a mock so that an unexpected
    attribute access surfaces as a real failure rather than a silent stub value.
    """

    __slots__ = ("path", "uri", "source", "lines", "version", "language_id")

    def __init__(self, path, text):
        self.path = path
        self.uri = "file:///" + path.replace("\\", "/").lstrip("/")
        self.source = text
        self.lines = text.splitlines(True)
        self.version = 0
        self.language_id = "yaml"


# -----------------------------------------------------------------------------
# Findings
# -----------------------------------------------------------------------------

LAYER_SCHEMA = "SCHEMA"
LAYER_YAML = "YAML"
LAYER_PARSER = "PARSER"
LAYER_TREE = "TREE"
LAYER_VALIDATOR = "VALIDATOR"

LAYER_ORDER = [LAYER_YAML, LAYER_PARSER, LAYER_SCHEMA, LAYER_TREE, LAYER_VALIDATOR]

LAYER_TITLES = {
    LAYER_YAML: "YAML load failures (the extension reports these before parsing)",
    LAYER_PARSER: "Parser failures (whole-file: no other diagnostic is produced)",
    LAYER_SCHEMA: "Layer 1 - JSON schema (blueprint-spec2-schema.json)",
    LAYER_TREE: "Layer 2a - language server tree errors",
    LAYER_VALIDATOR: "Layer 2b - language server semantic diagnostics",
}

VERDICT_NEW = "NEW"
VERDICT_BLUEPRINT_DEFECT = "KNOWN-BLUEPRINT-DEFECT"
VERDICT_TOOL_LIMITATION = "KNOWN-TOOL-LIMITATION"

KIND_TO_VERDICT = {
    "blueprint-defect": VERDICT_BLUEPRINT_DEFECT,
    "tool-limitation": VERDICT_TOOL_LIMITATION,
}


class Finding(object):
    __slots__ = (
        "layer",
        "severity",
        "line",
        "col",
        "line_is_approximate",
        "message",
        "template",
        "section",
        "prop",
        "json_path",
        "signature",
        "verdict",
        "note",
    )

    def __init__(
        self,
        layer,
        severity,
        message,
        line=None,
        col=None,
        line_is_approximate=False,
        section=None,
        prop=None,
        json_path=None,
    ):
        self.layer = layer
        self.severity = severity
        self.message = message
        self.line = line
        self.col = col
        self.line_is_approximate = line_is_approximate
        self.section = section
        self.prop = prop
        self.json_path = json_path
        self.template = normalize_message(message)
        self.signature = build_signature(layer, section, prop, self.template, message)
        self.verdict = VERDICT_NEW
        self.note = ""

    def sort_key(self):
        return (
            LAYER_ORDER.index(self.layer) if self.layer in LAYER_ORDER else 99,
            self.line if self.line is not None else -1,
            self.col if self.col is not None else -1,
            self.json_path or "",
            self.signature,
            self.message,
        )


class Crash(object):
    __slots__ = ("phase", "exc_type", "exc_message", "frames")

    def __init__(self, phase, exc_type, exc_message, frames):
        self.phase = phase
        self.exc_type = exc_type
        self.exc_message = exc_message
        self.frames = frames


class FileResult(object):
    __slots__ = (
        "path",
        "rel",
        "fid",
        "findings",
        "crashes",
        "line_count",
        "ls_skip_reason",
    )

    def __init__(self, path, rel, fid):
        self.path = path
        self.rel = rel
        self.fid = fid
        self.findings = []
        self.crashes = []
        self.line_count = 0
        self.ls_skip_reason = None

    @property
    def is_clean(self):
        return not self.findings and not self.crashes


# -----------------------------------------------------------------------------
# Message normalization and clustering
# -----------------------------------------------------------------------------

_EXPRESSION_RE = re.compile(r"\{\{[^{}]*\}\}")
_QUOTED_SINGLE_RE = re.compile(r"'[^']*'")
_QUOTED_DOUBLE_RE = re.compile(r'"[^"]*"')
_REPEATED_X_RE = re.compile(r"(?:'X',\s*)+'X'")
_BRACED_RE = re.compile(r"\{[^{}]*\}")
_BRACKETED_RE = re.compile(r"\[[^\[\]]*\]")
_DIGITS_RE = re.compile(r"\d+")
_WHITESPACE_RE = re.compile(r"\s+")


# A couple of language-server messages interpolate blueprint content without
# quoting it, so the generic quote-collapse cannot reach it and the "template"
# would carry a fragment of the customer's file into every report - including the
# safe one - and never cluster. These are rewritten wholesale first.
_MESSAGE_SPECIALIZATIONS = [
    (re.compile(r"^Unknown command .*$", re.DOTALL), "Unknown command X"),
    # note the unbalanced quote: that is the server's own message, verbatim.
    (re.compile(r"^Wrong script property '.*$", re.DOTALL), "Wrong script property 'X."),
]


def normalize_message(message):
    """Collapse a concrete message into a cluster template.

    Quoted strings become 'X', Liquid expressions {{X}}, brace/bracket literals
    {X}/[X] and digit runs N, so that 'Input 'Foo' is not defined' and
    'Input 'Bar' is not defined' end up in the same cluster.
    """
    text = message if message is not None else ""
    if not isinstance(text, str):
        text = str(text)
    for pattern, replacement in _MESSAGE_SPECIALIZATIONS:
        if pattern.match(text):
            return replacement
    text = _EXPRESSION_RE.sub("{{X}}", text)
    text = _QUOTED_SINGLE_RE.sub("'X'", text)
    text = _QUOTED_DOUBLE_RE.sub('"X"', text)
    text = _REPEATED_X_RE.sub("'X'", text)
    text = _BRACED_RE.sub("{X}", text)
    text = _BRACKETED_RE.sub("[X]", text)
    text = _DIGITS_RE.sub("N", text)
    # jsonschema says "was unexpected" for one property and "were unexpected"
    # for several; after the quote collapse the distinction is pure noise.
    text = text.replace("were unexpected", "was unexpected")
    return _WHITESPACE_RE.sub(" ", text).strip()


# Language-server messages whose quoted token is a *key or keyword* rather than
# blueprint data. The generic template collapses it to 'X', which would lump
# thirteen different unknown keys into one untriageable cluster - so the token is
# lifted back out and becomes the cluster identity instead.
_LS_IDENTITY_PATTERNS = [
    (re.compile(r"^Parent node does not have child with name '(.+)'$"), "unknown key"),
    (re.compile(r"^Wrong property '(.+?)'\. Must be"), "wrong property"),
    (re.compile(r"^Wrong activity '(.+?)'\. Must be"), "wrong activity"),
    (re.compile(r"^Prefix '(.+?)' is not allowed$"), "unknown prefix"),
    (re.compile(r"^The value '(.+?)' is not a reserved variable$"), "unknown variable"),
    (re.compile(r"^Wrong type of the script '(.+?)'$"), "wrong script type"),
]

_BRACKET_TOKEN_RE = re.compile(r"\[[^\[\]]*\]")


def _normalize_identity_token(token):
    """Keep the structure of a key/expression token, drop the data inside it.

    ``outputs["endpoint"]`` becomes ``outputs[X]`` so that the spec-1 style
    ``outputs[...]`` prefix clusters as one finding no matter which output the
    blueprint names.
    """
    text = _BRACKET_TOKEN_RE.sub("[X]", token)
    text = _DIGITS_RE.sub("N", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def ls_identity(message):
    """(label, token) when a language-server message identifies a key, else None."""
    if not message:
        return None
    text = message.strip()
    for pattern, label in _LS_IDENTITY_PATTERNS:
        match = pattern.match(text)
        if match:
            return label, _normalize_identity_token(match.group(1))
    return None


def build_signature(layer, section, prop, template, message=None):
    """The clustering identity of a finding.

    A bare message template is too coarse for the schema layer: every
    ``additionalProperties`` violation in a blueprint shares one template, and so
    does every ``enum`` violation, which would make triage impossible. Schema
    findings therefore carry their normalized section, and an unexpected-property
    finding is identified by the property itself - which is exactly the unit the
    known-findings catalog is written in. Language-server findings that name a
    key get that key in their signature for the same reason.
    """
    if prop is not None:
        return "unexpected property: %s.%s" % (section or "<root>", prop)
    if layer == LAYER_SCHEMA:
        return "%s :: %s" % (section or "<root>", template)
    identity = ls_identity(message)
    if identity is not None:
        return "%s: '%s'" % (identity[0], identity[1])
    return template


class Cluster(object):
    __slots__ = (
        "layer",
        "signature",
        "template",
        "verdict",
        "note",
        "count",
        "examples",
        # One anonymous file id per finding in this cluster, kept regardless of
        # --anonymize-paths: safe-summary.txt is always id-based, because a file
        # basename alone can identify a customer.
        "example_ids",
    )

    def __init__(self, layer, signature, template, verdict, note):
        self.layer = layer
        self.signature = signature
        self.template = template
        self.verdict = verdict
        self.note = note
        self.count = 0
        self.examples = []
        self.example_ids = []

    def sort_key(self):
        return (
            LAYER_ORDER.index(self.layer) if self.layer in LAYER_ORDER else 99,
            -self.count,
            self.signature,
        )


def build_clusters(results, anonymize, safe):
    """Group findings by (layer, signature, verdict). Deterministic order.

    The verdict is part of the key so that a signature which the catalog matches
    for some findings and not others splits into a KNOWN row and a NEW row
    instead of hiding the new one.
    """
    clusters = {}
    for result in results:
        for finding in sorted(result.findings, key=Finding.sort_key):
            key = (finding.layer, finding.signature, finding.verdict, finding.note)
            cluster = clusters.get(key)
            if cluster is None:
                cluster = Cluster(
                    finding.layer,
                    finding.signature,
                    finding.template,
                    finding.verdict,
                    finding.note,
                )
                clusters[key] = cluster
            cluster.count += 1
            cluster.examples.append(example_location(result, finding, anonymize, safe))
            cluster.example_ids.append(result.fid)
    ordered = sorted(clusters.values(), key=Cluster.sort_key)
    for cluster in ordered:
        cluster.examples.sort()
        cluster.example_ids.sort()
    return ordered


def example_location(result, finding, anonymize, safe):
    name = result.fid if anonymize else result.rel
    if finding.line is not None:
        return "%s:%d:%d" % (name, finding.line + 1, (finding.col or 0) + 1)
    if finding.json_path and not safe:
        return "%s %s" % (name, finding.json_path)
    # A literal JSON path spells out author-chosen key names, so at the safe
    # level the normalized section is the most that may be shown.
    if finding.section and safe:
        return "%s $.%s" % (name, finding.section)
    return name


def aggregate_unexpected_properties(results):
    """Counts of unexpected properties by (section, property).

    Returns a sorted list of (section, property, count, verdict, note).
    """
    counter = {}
    for result in results:
        for finding in result.findings:
            if finding.prop is None:
                continue
            key = (finding.section or "<root>", finding.prop)
            entry = counter.get(key)
            if entry is None:
                entry = [0, finding.verdict, finding.note]
                counter[key] = entry
            entry[0] += 1
    rows = []
    for (section, prop), (count, verdict, note) in counter.items():
        rows.append((section, prop, count, verdict, note))
    rows.sort(key=lambda row: (-row[2], row[0], row[1]))
    return rows


# -----------------------------------------------------------------------------
# Triage
# -----------------------------------------------------------------------------


class TriageCatalog(object):
    def __init__(self, entries, source):
        self.entries = entries
        self.source = source

    def classify(self, finding):
        """Returns (verdict, note). First matching entry wins (file order)."""
        subject = "\n".join(
            [
                "signature: " + finding.signature,
                "template: " + finding.template,
                "message: " + (finding.message or ""),
                "path: " + (finding.json_path or ""),
                "section: " + (finding.section or ""),
                "layer: " + finding.layer,
            ]
        )
        for pattern, compiled, verdict, note in self.entries:
            if pattern and pattern in subject:
                return verdict, note
            if compiled is not None and compiled.search(subject):
                return verdict, note
        return VERDICT_NEW, ""


EMPTY_CATALOG = TriageCatalog([], "disabled (--no-triage)")


def load_triage(path):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("triage catalog must be a JSON object")
    version = data.get("version")
    if version != 1:
        raise ValueError("unsupported triage catalog version: %r" % (version,))
    entries = []
    for index, raw in enumerate(data.get("clusters") or []):
        if not isinstance(raw, dict):
            raise ValueError("clusters[%d] is not an object" % index)
        match = raw.get("match")
        if not match:
            raise ValueError("clusters[%d] has no 'match'" % index)
        kind = raw.get("kind")
        if kind not in KIND_TO_VERDICT:
            raise ValueError(
                "clusters[%d] has unknown kind %r (expected one of %s)"
                % (index, kind, ", ".join(sorted(KIND_TO_VERDICT)))
            )
        compiled = _compile_optional_regex(match)
        entries.append((match, compiled, KIND_TO_VERDICT[kind], raw.get("note") or ""))
    return TriageCatalog(entries, path)


# Metacharacters that indicate a 'match' was *meant* as a regex. Deliberately
# excludes '.', '[', ']', '{' and '}': catalog entries are normally literal
# signatures such as "unexpected property: inputs.<key>.style" or templates such
# as "'X' is not one of [X]", where those characters are meant literally. If such
# a pattern were also tried as a regex, its '.' wildcards could match a
# *different* cluster and label a genuinely new finding as KNOWN - silently
# hiding the tool bug this script exists to find. Substring matching already
# covers the literal case, so the regex attempt is reserved for patterns that
# clearly ask for it.
_REGEX_INTENT_RE = re.compile(r"[\\^$*+?()|]")


def _compile_optional_regex(pattern):
    """Compile `pattern` only if it looks like a deliberate regex, else None."""
    if not _REGEX_INTENT_RE.search(pattern):
        return None
    try:
        return re.compile(pattern)
    except re.error:
        return None


# -----------------------------------------------------------------------------
# Corpus walk
# -----------------------------------------------------------------------------

YAML_SUFFIXES = (".yaml", ".yml")
SPEC2_RE = re.compile(r"^spec_version:\s*['\"]?2\b", re.MULTILINE)


def iter_yaml_files(root):
    """Yield every *.yaml/*.yml under root, in deterministic order."""
    collected = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            if name.lower().endswith(YAML_SUFFIXES):
                collected.append(os.path.join(dirpath, name))
    collected.sort(key=lambda p: relpath(p, root))
    return collected


def relpath(path, root):
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        rel = path
    return rel.replace("\\", "/")


def read_text(path):
    """Read a corpus file read-only, tolerating BOM, CRLF and bad bytes.

    ``surrogateescape`` keeps undecodable bytes round-trippable instead of
    raising, so a file with a stray byte still gets validated. Line endings are
    left exactly as they are: the language server reports positions against the
    text the editor holds, and rewriting them would shift columns.
    """
    with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as handle:
        text = handle.read()
    if text.startswith("\ufeff"):
        text = text[1:]
    return text


def is_spec2(text):
    return bool(SPEC2_RE.search(text))


# -----------------------------------------------------------------------------
# Layer 1: JSON schema
# -----------------------------------------------------------------------------

# Leaf errors that actually tell the author something, ranked. A oneOf branch
# failing on `type` is usually just "this is not the null variant" or "this is
# not the short-syntax variant" and says nothing useful.
_LEAF_PRIORITY = {
    "additionalProperties": 4,
    "required": 4,
    "enum": 4,
    "const": 4,
    "propertyNames": 3,
    "pattern": 3,
    "minimum": 3,
    "maximum": 3,
    "minItems": 3,
    "maxItems": 3,
    "minLength": 3,
    "maxLength": 3,
    "uniqueItems": 3,
    "contains": 3,
    "type": 1,
}
_DEFAULT_LEAF_PRIORITY = 2


def _is_null_branch_noise(error):
    """True for `type: null` mismatches produced by oneOf-with-null wrappers."""
    if error.validator != "type":
        return False
    expected = error.validator_value
    if isinstance(expected, str):
        return expected == "null"
    if isinstance(expected, (list, tuple)):
        return set(expected) == {"null"}
    return False


def _leaf_priority(leaf):
    return _LEAF_PRIORITY.get(leaf.validator, _DEFAULT_LEAF_PRIORITY)


def _dedupe_leaves(leaves):
    unique = []
    seen = set()
    for leaf in leaves:
        key = (tuple(leaf.absolute_path), leaf.validator, leaf.message)
        if key in seen:
            continue
        seen.add(key)
        unique.append(leaf)
    return unique


def _best_leaves(error):
    """Drill into a combinator error and keep only the informative leaves.

    A ``oneOf``/``anyOf`` error's context holds the failures of *every* branch,
    and the branches are alternatives for the same instance - so exactly one
    branch is worth reporting, and its errors are then all real. Picking leaves
    globally instead of picking a branch first is wrong: it silently drops the
    unexpected key in ``spec`` because a deeper unexpected key in
    ``spec.activities`` outranked it, even though both are genuine.

    So: group the context by branch, resolve each branch recursively, score each
    branch by (most informative validator, deepest path), and return every leaf
    of the winning branch. ``type: null`` failures - the "this is not the null
    variant" half of an optional-section wrapper - are dropped as noise.
    """
    if not error.context:
        return [error]

    branches = {}
    branch_order = []
    for sub_error in error.context:
        schema_path = list(sub_error.schema_path)
        index = schema_path[0] if schema_path else 0
        if index not in branches:
            branches[index] = []
            branch_order.append(index)
        branches[index].append(sub_error)

    scored = []
    for index in branch_order:
        leaves = []
        for sub_error in branches[index]:
            leaves.extend(_best_leaves(sub_error))
        leaves = [leaf for leaf in leaves if not _is_null_branch_noise(leaf)]
        if not leaves:
            continue
        score = (
            max(_leaf_priority(leaf) for leaf in leaves),
            max(len(list(leaf.absolute_path)) for leaf in leaves),
        )
        scored.append((score, index, _dedupe_leaves(leaves)))

    if not scored:
        # Every branch was pure noise - report the combinator error itself rather
        # than silently dropping a real problem.
        return [error]

    # max() on the score, with the branch index breaking ties so the choice is
    # stable across runs and jsonschema versions.
    best = max(scored, key=lambda item: (item[0], -_as_sort_int(item[1])))
    return best[2]


def _as_sort_int(value):
    return value if isinstance(value, int) else 0


# Schema keywords that consume one instance path element, and how to render it.
_SCHEMA_STEP_NAMED = "properties"
_SCHEMA_STEP_PATTERN = "patternProperties"
_SCHEMA_STEP_ADDITIONAL = "additionalProperties"
_SCHEMA_STEP_ITEMS = "items"
_SCHEMA_STEP_CONTAINS = "contains"


def normalize_json_path(instance_path, schema_path):
    """Turn an instance path into a reusable *section* identifier.

    Path elements the schema names explicitly stay literal; elements that come
    from ``patternProperties``/``additionalProperties`` are author-chosen keys and
    become ``<key>``; array indices become ``[]``. So
    ``inputs -> db_password -> style`` reads as ``inputs.<key>.style`` and
    clusters across every blueprint in the corpus.

    The two paths are walked in parallel because that is how jsonschema builds
    them: a ``properties`` step appends the property name to *both*, a
    ``patternProperties`` step appends the pattern to the schema path only, and
    combinators (``oneOf``, ``$ref``, ...) touch the schema path alone.
    """
    instance = list(instance_path)
    schema = list(schema_path)
    parts = []
    i = 0
    j = 0
    while j < len(schema) and i < len(instance):
        step = schema[j]
        if step == _SCHEMA_STEP_NAMED:
            parts.append(str(instance[i]))
            i += 1
            j += 2
        elif step == _SCHEMA_STEP_PATTERN:
            parts.append("<key>")
            i += 1
            j += 2
        elif step == _SCHEMA_STEP_ADDITIONAL:
            parts.append("<key>")
            i += 1
            j += 1
        elif step == _SCHEMA_STEP_ITEMS:
            parts.append("[]")
            i += 1
            # `items` as a list (tuple validation) puts the index next.
            j += 2 if (j + 1 < len(schema) and isinstance(schema[j + 1], int)) else 1
        elif step == _SCHEMA_STEP_CONTAINS:
            parts.append("[]")
            i += 1
            j += 1
        else:
            j += 1
    # Whatever the walk could not account for is appended as-is; this keeps the
    # section usable even if a future jsonschema changes how a path is built.
    while i < len(instance):
        element = instance[i]
        parts.append("[]" if isinstance(element, int) else str(element))
        i += 1
    return ".".join(parts).replace(".[]", "[]")


_PLAIN_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def literal_json_path(instance_path):
    out = "$"
    for element in instance_path:
        if isinstance(element, int):
            out += "[%d]" % element
        elif _PLAIN_KEY_RE.match(str(element)):
            out += "." + str(element)
        else:
            out += "[%s]" % json.dumps(str(element))
    return out


_UNEXPECTED_PROPS_RE = re.compile(r"'([^']*)'")


def unexpected_properties(error):
    """The property names an `additionalProperties` error is complaining about."""
    instance = error.instance
    schema = error.schema if isinstance(error.schema, dict) else {}
    if isinstance(instance, dict):
        allowed = set(schema.get("properties") or {})
        patterns = []
        for pattern in schema.get("patternProperties") or {}:
            try:
                patterns.append(re.compile(pattern))
            except re.error:
                pass
        extras = []
        for key in instance:
            name = str(key)
            if name in allowed:
                continue
            if any(compiled.search(name) for compiled in patterns):
                continue
            extras.append(name)
        if extras:
            return sorted(extras)
    # Fall back to the message, whose wording jsonschema has kept stable:
    # "Additional properties are not allowed ('a', 'b' were unexpected)".
    head = error.message.split("(", 1)[-1]
    return sorted(set(_UNEXPECTED_PROPS_RE.findall(head)))


_MAX_SCANNED_LINES = 4096


def guess_property_line(lines, prop):
    """Best-effort line for an unexpected property: first `^\\s*prop\\s*:`.

    Only used to help the human find the spot; flagged as approximate in the
    reports because a property name can legitimately appear more than once.
    """
    if not prop or len(prop) > 200:
        return None
    try:
        pattern = re.compile(r"^\s*(?:-\s*)?%s\s*:" % re.escape(prop))
    except re.error:
        return None
    for index, line in enumerate(lines[:_MAX_SCANNED_LINES]):
        if pattern.match(line):
            return index
    return None


def schema_findings(instance, validator, lines):
    """Layer 1: every informative schema violation, as Finding objects."""
    findings = []
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda err: (list(map(str, err.absolute_path)), err.validator or "", err.message),
    )
    seen = set()
    for error in errors:
        for leaf in _best_leaves(error):
            section = normalize_json_path(leaf.absolute_path, leaf.absolute_schema_path)
            path = literal_json_path(leaf.absolute_path)
            if leaf.validator == "additionalProperties":
                props = unexpected_properties(leaf)
                if not props:
                    props = [None]
                for prop in props:
                    key = (path, leaf.message, prop)
                    if key in seen:
                        continue
                    seen.add(key)
                    line = guess_property_line(lines, prop) if prop else None
                    findings.append(
                        Finding(
                            LAYER_SCHEMA,
                            "ERROR",
                            leaf.message,
                            line=line,
                            col=None,
                            line_is_approximate=line is not None,
                            section=section,
                            prop=prop,
                            json_path=path,
                        )
                    )
            else:
                key = (path, leaf.message, None)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    Finding(
                        LAYER_SCHEMA,
                        "ERROR",
                        leaf.message,
                        section=section,
                        json_path=path,
                    )
                )
    return findings


# -----------------------------------------------------------------------------
# Layer 2: language server
# -----------------------------------------------------------------------------


class LanguageServerLayer(object):
    """Holds the lazily imported server pieces and runs them over a document."""

    def __init__(self, repo_root):
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from server.ats.parser import Parser, ParserError, replace_unprintable_characters
        from server.ats.trees.blueprint_v2 import BlueprintV2Tree
        from server.validation.bp_v2_validator import BlueprintSpec2Validator

        self.Parser = Parser
        self.ParserError = ParserError
        self.replace_unprintable_characters = replace_unprintable_characters
        self.BlueprintSpec2Validator = BlueprintSpec2Validator
        self.BlueprintV2Tree = BlueprintV2Tree

    # -- the extension's own pre-parse gate ---------------------------------
    def load_yaml(self, text):
        """Mirror the extension's `_validate_yaml`: load, report, and stop.

        The real server never reaches the parser when the YAML itself does not
        load, so neither do we - otherwise every malformed file would be counted
        as a tool crash it never actually causes in production.
        """
        return yaml.load(
            self.replace_unprintable_characters(text), Loader=yaml.FullLoader
        )

    def run(self, path, text):
        """Returns (findings, crashes, skip_reason).

        skip_reason is None when the spec2 semantic validator ran, otherwise a
        short tag naming why it did not.
        """
        findings = []
        crashes = []

        document = CorpusDocument(path, text)

        try:
            tree = self.Parser(text).parse()
        except self.ParserError as exc:
            findings.append(
                Finding(
                    LAYER_PARSER,
                    "ERROR",
                    exc.message if exc.message is not None else str(exc),
                    line=_pos(exc.start_pos, 0),
                    col=_pos(exc.start_pos, 1),
                )
            )
            return findings, crashes, "parser-error"
        except ValueError as exc:
            # server.py turns a ValueError from the parser into a diagnostic too.
            findings.append(Finding(LAYER_PARSER, "ERROR", str(exc), line=0, col=0))
            return findings, crashes, "parser-error"
        except Exception as exc:
            crashes.append(_make_crash("parse", exc))
            return findings, crashes, "parse-crash"

        if not isinstance(tree, self.BlueprintV2Tree):
            # --include-non-spec2 can hand us a spec-1 tree. The real server
            # routes that to a different validator (ValidatorFactory), so running
            # the spec2 one here would only manufacture a crash that never
            # happens in production. Tree errors below are still real.
            for error in getattr(tree, "errors", None) or []:
                findings.append(
                    Finding(
                        LAYER_TREE,
                        "ERROR",
                        getattr(error, "message", str(error)),
                        line=_pos(getattr(error, "start_pos", None), 0),
                        col=_pos(getattr(error, "start_pos", None), 1),
                    )
                )
            return findings, crashes, "non-spec2-tree"

        try:
            diagnostics = self.BlueprintSpec2Validator(tree, document).validate()
        except Exception as exc:
            # This is the worst class of failure: server.py swallows it, so the
            # file silently loses *all* diagnostics, tree errors included.
            crashes.append(_make_crash("validate", exc))
            diagnostics = []

        for diagnostic in diagnostics or []:
            findings.append(
                Finding(
                    LAYER_VALIDATOR,
                    _severity_name(getattr(diagnostic, "severity", None)),
                    getattr(diagnostic, "message", ""),
                    line=_range_value(diagnostic, "line"),
                    col=_range_value(diagnostic, "character"),
                )
            )

        for error in getattr(tree, "errors", None) or []:
            findings.append(
                Finding(
                    LAYER_TREE,
                    "ERROR",
                    getattr(error, "message", str(error)),
                    line=_pos(getattr(error, "start_pos", None), 0),
                    col=_pos(getattr(error, "start_pos", None), 1),
                )
            )

        return findings, crashes, None


def _pos(position, index):
    if isinstance(position, (tuple, list)) and len(position) > index:
        value = position[index]
        if isinstance(value, int):
            return value
    return None


def _range_value(diagnostic, attribute):
    rng = getattr(diagnostic, "range", None)
    start = getattr(rng, "start", None)
    value = getattr(start, attribute, None)
    return value if isinstance(value, int) else None


def _severity_name(severity):
    if severity is None:
        # LSP treats an absent severity as an error, and so does the client.
        return "ERROR"
    name = getattr(severity, "name", None)
    if name:
        return str(name).upper()
    return str(severity).upper()


_TOOL_FRAME_RE = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')


def _make_crash(phase, exc):
    text = traceback.format_exc()
    frames = []
    for match in _TOOL_FRAME_RE.finditer(text):
        frames.append(
            "%s:%s in %s" % (os.path.basename(match.group(1)), match.group(2), match.group(3))
        )
    return Crash(phase, type(exc).__name__, str(exc), frames[-6:])


# -----------------------------------------------------------------------------
# Driver
# -----------------------------------------------------------------------------


class Run(object):
    """Everything the renderers need to know about one execution."""

    def __init__(self, args, repo_root, schema_path, pygls_mode, catalog):
        self.args = args
        self.repo_root = repo_root
        self.schema_path = schema_path
        self.pygls_mode = pygls_mode
        self.catalog = catalog
        self.started_at = datetime.datetime.now()
        self.corpus_dir = os.path.abspath(args.corpus_dir)
        self.schema_sha256 = ""
        self.repo_sha = ""
        self.results = []
        self.skipped_non_spec2 = 0
        self.unreadable = []
        self.total_yaml_files = 0
        self.clusters = []
        self.property_rows = []

    # -- derived counts -----------------------------------------------------
    @property
    def anonymize(self):
        return bool(self.args.anonymize_paths)

    @property
    def clean_results(self):
        return [r for r in self.results if r.is_clean]

    @property
    def dirty_results(self):
        return [r for r in self.results if not r.is_clean]

    @property
    def crash_results(self):
        return [r for r in self.results if r.crashes]

    @property
    def finding_count(self):
        return sum(len(r.findings) for r in self.results)

    @property
    def crash_count(self):
        return sum(len(r.crashes) for r in self.results)

    @property
    def new_clusters(self):
        return [c for c in self.clusters if c.verdict == VERDICT_NEW]

    def display_name(self, result):
        return result.fid if self.anonymize else result.rel


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_short_sha(repo_root):
    try:
        output = subprocess.check_output(
            ["git", "-C", repo_root, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception:
        return ""
    return output.decode("ascii", "replace").strip()


def run_corpus(run):
    schema = load_json(run.schema_path)
    jsonschema.Draft6Validator.check_schema(schema)
    validator = jsonschema.Draft6Validator(schema)

    ls_layer = LanguageServerLayer(run.repo_root)

    paths = iter_yaml_files(run.corpus_dir)
    run.total_yaml_files = len(paths)

    selected = []
    for path in paths:
        try:
            text = read_text(path)
        except (OSError, IOError) as exc:
            run.unreadable.append((relpath(path, run.corpus_dir), str(exc)))
            continue
        if not run.args.include_non_spec2 and not is_spec2(text):
            run.skipped_non_spec2 += 1
            continue
        selected.append((path, text))

    for index, (path, text) in enumerate(selected):
        rel = relpath(path, run.corpus_dir)
        result = FileResult(path, rel, "bp_%04d" % (index + 1))
        result.line_count = text.count("\n") + 1
        lines = text.splitlines(True)

        # The extension's YAML gate runs before anything else; if it fails, that
        # single diagnostic is all the author ever sees.
        instance = None
        yaml_failed = False
        try:
            instance = ls_layer.load_yaml(text)
        except yaml.MarkedYAMLError as exc:
            yaml_failed = True
            mark = getattr(exc, "problem_mark", None)
            result.findings.append(
                Finding(
                    LAYER_YAML,
                    "ERROR",
                    getattr(exc, "problem", None) or str(exc),
                    line=max((mark.line - 1) if mark else 0, 0),
                    col=max((mark.column - 1) if mark else 0, 0),
                )
            )
        except Exception as exc:
            yaml_failed = True
            result.crashes.append(_make_crash("yaml", exc))

        if not yaml_failed:
            try:
                result.findings.extend(schema_findings(instance, validator, lines))
            except Exception as exc:
                result.crashes.append(_make_crash("schema", exc))

            findings, crashes, skip_reason = ls_layer.run(path, text)
            result.findings.extend(findings)
            result.crashes.extend(crashes)
            result.ls_skip_reason = skip_reason

        for finding in result.findings:
            finding.verdict, finding.note = run.catalog.classify(finding)

        run.results.append(result)

    run.clusters = build_clusters(
        run.results, run.anonymize, run.args.level == "safe"
    )
    run.property_rows = aggregate_unexpected_properties(run.results)


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


# -----------------------------------------------------------------------------
# Rendering
# -----------------------------------------------------------------------------

RULE = "=" * 78
THIN = "-" * 78

FULL_BANNER = (
    "LEVEL: FULL - MAY CONTAIN CUSTOMER BLUEPRINT CONTENT - TREAT AS CONFIDENTIAL"
)
SAFE_BANNER = "LEVEL: SAFE - no blueprint content: message templates and counts only"
SAFE_SHARE_BANNER = (
    "SAFE TO SHARE: contains no blueprint content, only message templates and counts."
)


def level_banner(level):
    return FULL_BANNER if level == "full" else SAFE_BANNER


def report_header(run, title):
    lines = [RULE, "Torque blueprint corpus validation - %s" % title, level_banner(run.args.level), RULE]
    return lines


def header_block(run):
    lines = []
    lines.append("timestamp        : %s" % run.started_at.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("corpus dir       : %s" % run.corpus_dir)
    lines.append("repo root        : %s" % run.repo_root)
    lines.append("repo HEAD        : %s" % (run.repo_sha or "(not a git checkout)"))
    lines.append("schema file      : %s" % relpath(run.schema_path, run.repo_root))
    lines.append("schema sha256    : %s" % run.schema_sha256)
    lines.append("pygls            : %s" % run.pygls_mode)
    lines.append("level            : %s" % run.args.level)
    lines.append("paths            : %s" % ("anonymized ids" if run.anonymize else "relative to corpus dir"))
    lines.append("triage catalog   : %s" % run.catalog.source)
    lines.append("file selection   : %s" % (
        "all *.yaml/*.yml" if run.args.include_non_spec2 else "spec_version 2 only"
    ))
    return lines


def counts_block(run):
    known = sum(c.count for c in run.clusters if c.verdict != VERDICT_NEW)
    new = sum(c.count for c in run.clusters if c.verdict == VERDICT_NEW)
    lines = []
    lines.append("yaml files found        : %d" % run.total_yaml_files)
    lines.append("validated (spec2)       : %d" % len(run.results))
    lines.append("skipped (not spec2)     : %d" % run.skipped_non_spec2)
    lines.append("unreadable              : %d" % len(run.unreadable))
    lines.append("fully clean             : %d" % len(run.clean_results))
    lines.append("with findings           : %d" % len([r for r in run.results if r.findings]))
    lines.append("files with crashes      : %d" % len(run.crash_results))
    lines.append("findings total          : %d" % run.finding_count)
    lines.append("  of which KNOWN        : %d" % known)
    lines.append("  of which NEW          : %d" % new)
    lines.append("crashes total           : %d" % run.crash_count)
    lines.append("clusters total          : %d" % len(run.clusters))
    lines.append("  NEW clusters          : %d" % len(run.new_clusters))
    not_spec2_tree = len(
        [r for r in run.results if r.ls_skip_reason == "non-spec2-tree"]
    )
    if not_spec2_tree:
        lines.append(
            "semantic layer skipped  : %d (did not parse into a spec2 tree; the real"
            % not_spec2_tree
        )
        lines.append(
            "                          server routes those to another validator, so"
        )
        lines.append(
            "                          running the spec2 one would invent a crash)"
        )
    return lines


def crash_section(run, safe):
    lines = []
    if not run.crash_results:
        return lines
    lines.append("")
    lines.append(RULE)
    lines.append("!! CRASHES - %d in %d file(s)" % (run.crash_count, len(run.crash_results)))
    lines.append("!! These are tool bugs. In the running language server the exception is")
    lines.append("!! swallowed, so the file silently loses ALL of its diagnostics.")
    lines.append(RULE)
    for result in run.crash_results:
        lines.append("")
        lines.append("%s" % run.display_name(result))
        for crash in result.crashes:
            lines.append("  phase     : %s" % crash.phase)
            lines.append("  exception : %s" % crash.exc_type)
            if not safe:
                lines.append("  message   : %s" % crash.exc_message)
            for frame in crash.frames:
                lines.append("    at %s" % frame)
    return lines


def cluster_tables(run, max_examples, safe):
    lines = []
    for layer in LAYER_ORDER:
        layer_clusters = [c for c in run.clusters if c.layer == layer]
        if not layer_clusters:
            continue
        lines.append("")
        lines.append(RULE)
        lines.append("%s" % LAYER_TITLES[layer])
        lines.append("%d cluster(s), %d finding(s)" % (
            len(layer_clusters), sum(c.count for c in layer_clusters)))
        lines.append(RULE)
        for cluster in layer_clusters:
            lines.append("")
            lines.append("[%5d]  %s" % (cluster.count, cluster.signature))
            if cluster.signature != cluster.template:
                lines.append("         template: %s" % cluster.template)
            lines.append("         verdict : %s" % cluster.verdict)
            if cluster.note:
                lines.append("         note    : %s" % cluster.note)
            shown = cluster.examples[:max_examples]
            lines.append("         examples: %s" % (", ".join(shown) if shown else "-"))
            if len(cluster.examples) > len(shown):
                lines.append("                   (+%d more)" % (len(cluster.examples) - len(shown)))
    return lines


def property_table(run):
    lines = []
    if not run.property_rows:
        return lines
    lines.append("")
    lines.append(RULE)
    lines.append("UNEXPECTED PROPERTIES by (section, property)")
    lines.append("The schema rejects these keys. Each one is either a blueprint defect")
    lines.append("(Torque ignores the key) or a gap in the schema. Most actionable table.")
    lines.append(RULE)
    section_width = max([len(row[0]) for row in run.property_rows] + [len("section")])
    prop_width = max([len(row[1]) for row in run.property_rows] + [len("property")])
    row_format = "%7s  %-" + str(section_width) + "s  %-" + str(prop_width) + "s  %s"
    lines.append(row_format % ("count", "section", "property", "verdict"))
    lines.append(THIN)
    for section, prop, count, verdict, note in run.property_rows:
        lines.append(row_format % (count, section, prop, verdict))
        if note:
            lines.append("%7s  %s" % ("", "^ " + note))
    lines.append("")
    lines.append("(the language server reports its own unknown keys separately - see the")
    lines.append(" \"unknown key: 'X'\" clusters in the tree-errors table above)")
    return lines


def triage_section(run):
    lines = []
    lines.append("")
    lines.append(RULE)
    lines.append("TRIAGE")
    lines.append(RULE)

    new = run.new_clusters
    lines.append("")
    if new:
        lines.append("*" * 78)
        lines.append("*** %d NEW CLUSTER(S) - NOT IN THE KNOWN-FINDINGS CATALOG" % len(new))
        lines.append("*** These are the candidate TOOL BUGS. Start here.")
        lines.append("*" * 78)
        for cluster in new:
            lines.append("")
            lines.append("  NEW  [%d]  %s  (%s)" % (cluster.count, cluster.signature, cluster.layer))
            if cluster.signature != cluster.template:
                lines.append("            template: %s" % cluster.template)
    else:
        lines.append("  No NEW clusters: every finding matched the known-findings catalog.")

    for verdict in (VERDICT_BLUEPRINT_DEFECT, VERDICT_TOOL_LIMITATION):
        known = [c for c in run.clusters if c.verdict == verdict]
        if not known:
            continue
        lines.append("")
        lines.append(THIN)
        lines.append("%s - %d cluster(s), %d finding(s)" % (
            verdict, len(known), sum(c.count for c in known)))
        lines.append(THIN)
        for cluster in known:
            lines.append("  [%5d]  %s" % (cluster.count, cluster.signature))
            if cluster.note:
                lines.append("           %s" % cluster.note)
    return lines


def next_steps(run, include_paths=True):
    lines = ["", RULE, "WHAT TO DO NEXT", RULE]
    steps = []
    if run.crash_results:
        steps.append([
            "CRASHES first. Each one is a tool bug that makes the language server",
            "publish nothing at all for that file. Reproduce with the file named",
            "above, fix, then add a regression test under tests/.",
        ])
    if run.new_clusters:
        steps.append([
            "NEW clusters -> INVESTIGATE THE TOOL. Decide for each one whether the",
            "blueprint is really wrong (then add it to known_findings.json as",
            "blueprint-defect) or the schema/validator is wrong (then fix the tool",
            "and add a test). Check the key against the Torque server source before",
            "concluding either way.",
        ])
    if any(c.verdict == VERDICT_BLUEPRINT_DEFECT for c in run.clusters):
        steps.append([
            "KNOWN-BLUEPRINT-DEFECT clusters -> REPORT TO THE BLUEPRINT OWNERS.",
            "These keys are silently dropped by Torque, so the blueprint does not do",
            "what its author thinks it does. Nothing to fix in the extension.",
        ])
    if any(c.verdict == VERDICT_TOOL_LIMITATION for c in run.clusters):
        steps.append([
            "KNOWN-TOOL-LIMITATION clusters -> false positives we already know about.",
            "Worth fixing eventually; not a surprise.",
        ])
    if not steps:
        lines.append("Nothing to do: the corpus produced no findings at all.")
    for index, step in enumerate(steps):
        lines.append("%d. %s" % (index + 1, step[0]))
        for continuation in step[1:]:
            lines.append("   %s" % continuation)
    if not run.crash_results and not run.new_clusters and steps:
        lines.append("")
        lines.append("Nothing new. The corpus produced only findings already in the catalog.")
    lines.append("")
    if include_paths:
        lines.append("Reports written to: %s" % os.path.abspath(run.args.report_dir))
    else:
        # safe-summary.txt may be pasted anywhere, so it does not carry the
        # report directory either - that path is the human's own business.
        lines.append("Report files (in the report directory):")
    lines.append("  summary.txt      - full run summary (%s)" % run.args.level.upper())
    lines.append("  findings.txt     - per-file detail (%s)" % run.args.level.upper())
    lines.append("  findings.json    - machine readable (%s)" % run.args.level.upper())
    lines.append("  safe-summary.txt - SAFE to paste into a chat with an AI")
    lines.append("  path-map.txt     - CONFIDENTIAL id -> path mapping, do NOT share")
    return lines


def render_summary(run):
    safe = run.args.level == "safe"
    lines = report_header(run, "SUMMARY")
    lines.extend(header_block(run))
    lines.append("")
    lines.append(THIN)
    lines.append("COUNTS")
    lines.append(THIN)
    lines.extend(counts_block(run))
    if run.unreadable:
        lines.append("")
        lines.append("UNREADABLE FILES")
        for rel, error in run.unreadable:
            lines.append("  %s: %s" % (rel if not run.anonymize else "(path hidden)", error))
    lines.extend(crash_section(run, safe))
    lines.extend(cluster_tables(run, run.args.max_examples, safe))
    lines.extend(property_table(run))
    lines.extend(triage_section(run))
    lines.extend(next_steps(run))
    lines.append("")
    return "\n".join(lines) + "\n"


def render_findings_txt(run):
    safe = run.args.level == "safe"
    lines = report_header(run, "FINDINGS (per file)")
    lines.append("format: LAYER SEVERITY line:col message")
    if safe:
        lines.append("safe level: normalized templates only, no source and no raw messages.")
    else:
        lines.append("'~' before a line number means the location is approximate.")
    lines.append("")

    dirty = run.dirty_results
    if not dirty:
        lines.append("No findings.")
    for result in dirty:
        lines.append(RULE)
        lines.append(run.display_name(result))
        lines.append(RULE)
        for crash in result.crashes:
            lines.append("  CRASH    %s in %s" % (crash.exc_type, crash.phase))
            if not safe:
                lines.append("           %s" % crash.exc_message)
            for frame in crash.frames:
                lines.append("           at %s" % frame)
        source_lines = None
        if not safe:
            try:
                source_lines = read_text(result.path).splitlines()
            except (OSError, IOError):
                source_lines = None
        for finding in sorted(result.findings, key=Finding.sort_key):
            location = format_location(finding)
            text = finding.template if safe else finding.message
            lines.append("  %-9s %-11s %-10s %s" % (
                finding.layer, finding.severity, location, one_line(text)))
            if finding.prop is not None:
                # A single additionalProperties error can name several keys; the
                # finding is per key, so say which one this row is about.
                lines.append("            offending property: %s" % finding.prop)
            if not safe:
                if finding.json_path:
                    lines.append("            %s" % finding.json_path)
                lines.extend(source_excerpt(source_lines, finding.line))
            if finding.verdict != VERDICT_NEW:
                lines.append("            [%s] %s" % (finding.verdict, finding.note))
            else:
                lines.append("            [NEW]")
        lines.append("")
    return "\n".join(lines) + "\n"


def format_location(finding):
    if finding.line is None:
        return "-:-"
    prefix = "~" if finding.line_is_approximate else ""
    col = "-" if finding.col is None else str(finding.col + 1)
    return "%s%d:%s" % (prefix, finding.line + 1, col)


def one_line(text):
    return _WHITESPACE_RE.sub(" ", text if text is not None else "").strip()


def source_excerpt(source_lines, line):
    """The offending source line plus one line of context above it."""
    if source_lines is None or line is None or line < 0 or line >= len(source_lines):
        return []
    out = []
    if line > 0:
        out.append("              | %s" % source_lines[line - 1].rstrip())
    out.append("            > | %s" % source_lines[line].rstrip())
    return out


def render_findings_json(run):
    safe = run.args.level == "safe"
    payload = {
        "level": run.args.level,
        "confidentiality": "SAFE" if safe else "FULL - may contain customer content",
        "generated_at": run.started_at.isoformat(),
        "corpus_dir": None if (safe and run.anonymize) else run.corpus_dir,
        "repo_root": run.repo_root,
        "repo_head": run.repo_sha,
        "schema_file": relpath(run.schema_path, run.repo_root),
        "schema_sha256": run.schema_sha256,
        "pygls": run.pygls_mode,
        "paths": "anonymized" if run.anonymize else "relative",
        "triage_catalog": run.catalog.source,
        "counts": {
            "yaml_files_found": run.total_yaml_files,
            "validated": len(run.results),
            "skipped_not_spec2": run.skipped_non_spec2,
            "unreadable": len(run.unreadable),
            "clean": len(run.clean_results),
            "with_findings": len([r for r in run.results if r.findings]),
            "files_with_crashes": len(run.crash_results),
            "findings": run.finding_count,
            "crashes": run.crash_count,
            "clusters": len(run.clusters),
            "new_clusters": len(run.new_clusters),
        },
        "clusters": [
            {
                "layer": cluster.layer,
                "signature": cluster.signature,
                "template": cluster.template,
                "verdict": cluster.verdict,
                "note": cluster.note,
                "count": cluster.count,
                "examples": cluster.examples[: run.args.max_examples],
            }
            for cluster in run.clusters
        ],
        "unexpected_properties": [
            {
                "section": section,
                "property": prop,
                "count": count,
                "verdict": verdict,
                "note": note,
            }
            for section, prop, count, verdict, note in run.property_rows
        ],
        "files": [],
    }

    for result in run.results:
        entry = {
            "id": result.fid,
            "clean": result.is_clean,
            "lines": result.line_count,
            "crashes": [
                {
                    "phase": crash.phase,
                    "exception": crash.exc_type,
                    "frames": crash.frames,
                }
                for crash in result.crashes
            ],
            "findings": [],
        }
        if not run.anonymize:
            entry["path"] = result.rel
        for crash, raw in zip(entry["crashes"], result.crashes):
            if not safe:
                crash["message"] = raw.exc_message
        for finding in sorted(result.findings, key=Finding.sort_key):
            item = {
                "layer": finding.layer,
                "severity": finding.severity,
                "template": finding.template,
                "signature": finding.signature,
                "verdict": finding.verdict,
                "note": finding.note,
                "line": finding.line,
                "column": finding.col,
                "line_is_approximate": finding.line_is_approximate,
                "section": finding.section,
                "unexpected_property": finding.prop,
            }
            if not safe:
                item["message"] = finding.message
                item["json_path"] = finding.json_path
            entry["findings"].append(item)
        payload["files"].append(entry)

    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def render_safe_summary(run):
    """Always written. Must never contain blueprint content."""
    lines = [RULE, "Torque blueprint corpus validation - SAFE SUMMARY", SAFE_SHARE_BANNER, RULE]
    lines.append("")
    lines.append("What is in here : normalized message templates; schema sections; the")
    lines.append("                  *names* of rejected properties (schema keys such as")
    lines.append("                  'display-name' or 'optional', never values); counts;")
    lines.append("                  and anonymous file ids (bp_0001, ...).")
    lines.append("What is not     : no blueprint values, no source lines, no raw messages,")
    lines.append("                  no file names, no paths, no directory structure.")
    lines.append("Resolving ids   : path-map.txt, next to this file, maps each id back to")
    lines.append("                  its path. That mapping is CONFIDENTIAL - keep it local.")
    lines.append("")
    lines.append("timestamp      : %s" % run.started_at.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("repo HEAD      : %s" % (run.repo_sha or "(not a git checkout)"))
    lines.append("schema sha256  : %s" % run.schema_sha256)
    lines.append("pygls          : %s" % run.pygls_mode)
    lines.append("run level      : %s" % run.args.level)
    lines.append("triage catalog : %s" % (
        os.path.basename(run.catalog.source) if run.catalog.entries else run.catalog.source))
    lines.append("")
    lines.append(THIN)
    lines.append("COUNTS")
    lines.append(THIN)
    lines.extend(counts_block(run))

    if run.crash_results:
        lines.append("")
        lines.append(RULE)
        lines.append("!! CRASHES - %d in %d file(s)" % (run.crash_count, len(run.crash_results)))
        lines.append("!! In the running language server these are swallowed and the file loses")
        lines.append("!! ALL diagnostics. Highest priority.")
        lines.append(RULE)
        counter = {}
        for result in run.crash_results:
            for crash in result.crashes:
                key = (crash.phase, crash.exc_type, " <- ".join(crash.frames))
                counter[key] = counter.get(key, 0) + 1
        for (phase, exc_type, frames), count in sorted(
            counter.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append("")
            lines.append("[%5d]  %s during %s" % (count, exc_type, phase))
            if frames:
                lines.append("         frames: %s" % frames)

    for layer in LAYER_ORDER:
        layer_clusters = [c for c in run.clusters if c.layer == layer]
        if not layer_clusters:
            continue
        lines.append("")
        lines.append(RULE)
        lines.append("%s" % LAYER_TITLES[layer])
        lines.append(RULE)
        for cluster in layer_clusters:
            lines.append("")
            lines.append("[%5d]  %s" % (cluster.count, cluster.signature))
            if cluster.signature != cluster.template:
                lines.append("         template: %s" % cluster.template)
            lines.append("         verdict : %s" % cluster.verdict)
            if cluster.note:
                lines.append("         note    : %s" % cluster.note)
            lines.append("         files   : %s" % safe_file_summary(run, cluster))

    lines.extend(property_table(run))
    lines.extend(triage_section(run))
    lines.extend(next_steps(run, include_paths=False))
    lines.append("")
    return "\n".join(lines) + "\n"


def safe_file_summary(run, cluster):
    """Anonymous file ids with counts - never a path, never a basename.

    Always id-based, whatever --anonymize-paths says: a basename such as
    'acme-prod-deploy.yaml' can identify a customer on its own, and a file whose
    purpose is to be pasted into a chat has to be safe unconditionally rather
    than safe-if-the-right-flag-was-passed. path-map.txt resolves the ids.
    """
    counter = {}
    for fid in cluster.example_ids:
        counter[fid] = counter.get(fid, 0) + 1
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    shown = ordered[: run.args.max_examples]
    text = ", ".join("%s x%d" % (name, count) for name, count in shown)
    if len(ordered) > len(shown):
        text += ", (+%d more file(s))" % (len(ordered) - len(shown))
    return text or "-"


def render_path_map(run):
    lines = [
        RULE,
        "CONFIDENTIAL - blueprint id to path mapping",
        "Do NOT share this file. It is the key that de-anonymizes every report,",
        "safe-summary.txt included. Use it locally to resolve an id such as",
        "bp_0007 back to the blueprint it came from.",
        RULE,
        "corpus dir: %s" % run.corpus_dir,
        "",
    ]
    for result in run.results:
        lines.append("%s  %s" % (result.fid, result.rel))
    lines.append("")
    return "\n".join(lines) + "\n"


def write_report(path, text):
    """Write a report. `backslashreplace` keeps surrogates from bad corpus bytes
    from blowing up the encoder."""
    with open(path, "w", encoding="utf-8", errors="backslashreplace", newline="\n") as handle:
        handle.write(text)


# -----------------------------------------------------------------------------
# Console output
# -----------------------------------------------------------------------------


def console(run, text=""):
    if run.args.quiet:
        return
    emit(text)


def emit(text=""):
    stream = sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        stream.write(text + "\n")
    except UnicodeEncodeError:
        stream.write(text.encode(encoding, "backslashreplace").decode(encoding, "replace") + "\n")


def print_console_report(run):
    safe = run.args.level == "safe"
    show = run.args.show

    console(run, "")
    console(run, RULE)
    console(run, "Torque blueprint corpus validation")
    console(run, level_banner(run.args.level))
    console(run, RULE)
    for line in counts_block(run):
        console(run, line)

    if run.crash_results:
        console(run, "")
        console(run, "!! %d CRASH(ES) in %d file(s) - see summary.txt" % (
            run.crash_count, len(run.crash_results)))
        for result in run.crash_results:
            for crash in result.crashes:
                console(run, "   %s: %s during %s" % (
                    run.display_name(result), crash.exc_type, crash.phase))

    if show in ("clean", "all"):
        console(run, "")
        console(run, "CLEAN FILES (%d) - no schema and no language-server findings" % len(
            run.clean_results))
        for result in run.clean_results:
            console(run, "   %s" % run.display_name(result))

    if show in ("findings", "all"):
        console(run, "")
        console(run, "FILES WITH FINDINGS (%d)" % len(run.dirty_results))
        for result in run.dirty_results:
            new_count = len([f for f in result.findings if f.verdict == VERDICT_NEW])
            console(run, "   %-52s %3d finding(s), %d NEW%s" % (
                run.display_name(result),
                len(result.findings),
                new_count,
                ", CRASH" if result.crashes else "",
            ))
            if show == "all":
                for finding in sorted(result.findings, key=Finding.sort_key):
                    if safe:
                        # Never the raw message at the safe level - the template
                        # and the rejected key name are all that may be printed.
                        detail = finding.template
                        if finding.prop is not None:
                            detail += "   -> %s" % finding.prop
                    else:
                        detail = one_line(finding.message)
                        if finding.prop is not None:
                            detail += "   -> %s" % finding.prop
                    console(run, "        %-9s %-9s %s" % (
                        finding.layer, format_location(finding), detail))

    if run.new_clusters:
        console(run, "")
        console(run, "*** %d NEW CLUSTER(S) - candidate tool bugs" % len(run.new_clusters))
        for cluster in run.new_clusters:
            console(run, "    [%d] %-9s %s" % (cluster.count, cluster.layer, cluster.signature))
    else:
        console(run, "")
        console(run, "No NEW clusters - everything matched the known-findings catalog.")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

EPILOG = """\
typical workflow
----------------
  1. sanitize the customer repo (never validate the original):
       python sanitize_blueprints.py --in C:\\corpora\\acme-raw --out C:\\corpora\\acme

  2. validate the sanitized corpus:
       python validate_blueprints.py --in C:\\corpora\\acme

  3. read the report yourself:
       notepad blueprint-validation-report\\summary.txt
     start at the CRASHES section, then the NEW clusters, then the
     "UNEXPECTED PROPERTIES" table.

  4. if you want help interpreting it, paste ONLY this file to an AI:
       blueprint-validation-report\\safe-summary.txt

  extra safety when the corpus is sensitive - hides file names too:
       python validate_blueprints.py --in C:\\corpora\\acme --level safe --anonymize-paths

exit codes
----------
  0 no findings (or only KNOWN ones, with the default --fail-on new)
  1 findings, per --fail-on
  2 crashes in the language server
  3 setup error (missing repo, schema or dependency)
  4 unexpected error
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="validate_blueprints.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Run the Torque VS Code extension's two blueprint validation layers "
            "(JSON schema + Python language server) over a corpus of spec_version 2 "
            "blueprints, and write reports for a human to read. Read-only, offline."
        ),
        epilog=EPILOG,
    )
    parser.add_argument(
        "--in",
        dest="corpus_dir",
        required=True,
        metavar="CORPUS_DIR",
        help="directory to walk for blueprint YAML (never modified)",
    )
    parser.add_argument(
        "--repo-root",
        default=DEFAULT_REPO_ROOT,
        metavar="PATH",
        help="root of the torque-vs-code-extensions checkout "
        "(default: the script's own ../..)",
    )
    parser.add_argument(
        "--report-dir",
        default=os.path.join(".", "blueprint-validation-report"),
        metavar="PATH",
        help="where to write the reports (default: ./blueprint-validation-report)",
    )
    parser.add_argument(
        "--level",
        choices=("full", "safe"),
        default="full",
        help="full: reports may quote blueprint content (confidential). "
        "safe: templates and counts only. Default: full",
    )
    parser.add_argument(
        "--anonymize-paths",
        action="store_true",
        help="also replace corpus paths with stable bp_0001 ids in summary.txt, "
        "findings.txt and findings.json (safe-summary.txt always uses ids "
        "regardless); the mapping goes only into path-map.txt",
    )
    parser.add_argument(
        "--triage",
        default=DEFAULT_TRIAGE_PATH,
        metavar="PATH",
        help="known-findings catalog (default: the shipped known_findings.json)",
    )
    parser.add_argument(
        "--no-triage",
        action="store_true",
        help="do not classify findings; everything is reported as NEW",
    )
    parser.add_argument(
        "--include-non-spec2",
        action="store_true",
        help="validate every *.yaml/*.yml, not just spec_version 2 files. Note "
        "that a file which does not parse into a spec2 tree gets the schema and "
        "parser layers only - the spec2 semantic validator is skipped, because "
        "the real server routes such files to a different validator",
    )
    parser.add_argument(
        "--show",
        choices=("clean", "findings", "all"),
        default="findings",
        help="console listing: clean files, files with findings, or both plus "
        "per-finding detail. Default: findings",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "findings", "new", "crashes"),
        default="new",
        help="what makes the exit code non-zero. Default: new",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=5,
        metavar="N",
        help="example locations per cluster in the summary (default: 5)",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress console output")
    return parser


class SetupError(Exception):
    """A problem with the environment, not with the corpus - exit code 3."""


def fail_setup(message):
    sys.stderr.write("setup error: %s\n" % message)
    return EXIT_SETUP


def resolve_setup(args):
    """Validate the environment. Returns (repo_root, schema_path) or raises SetupError."""
    if yaml is None:
        raise SetupError(
            "pyyaml is not installed (%s). Install it with: pip install pyyaml" % _YAML_ERROR
        )
    if jsonschema is None:
        raise SetupError(
            "jsonschema is not installed (%s). Install it with: pip install jsonschema"
            % _JSONSCHEMA_ERROR
        )

    corpus_dir = os.path.abspath(args.corpus_dir)
    if not os.path.isdir(corpus_dir):
        raise SetupError("corpus directory does not exist: %s" % corpus_dir)

    repo_root = os.path.abspath(args.repo_root)
    schema_path = os.path.join(repo_root, SCHEMA_RELPATH)
    server_dir = os.path.join(repo_root, "server")
    missing = []
    if not os.path.isfile(schema_path):
        missing.append(schema_path)
    if not os.path.isdir(server_dir):
        missing.append(server_dir)
    if missing:
        raise SetupError(
            "%s does not look like a torque-vs-code-extensions checkout - missing:\n  %s\n"
            "Pass --repo-root pointing at the extension repository."
            % (repo_root, "\n  ".join(missing))
        )

    if args.max_examples < 1:
        raise SetupError("--max-examples must be at least 1")

    return repo_root, schema_path


def compute_exit_code(run):
    fail_on = run.args.fail_on
    if fail_on == "none":
        return EXIT_OK
    if run.crash_count:
        return EXIT_CRASHES
    if fail_on == "crashes":
        return EXIT_OK
    if fail_on == "findings" and run.finding_count:
        return EXIT_FINDINGS
    if fail_on == "new" and run.new_clusters:
        return EXIT_FINDINGS
    return EXIT_OK


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        repo_root, schema_path = resolve_setup(args)
    except SetupError as exc:
        return fail_setup(str(exc))

    pygls_mode, using_stub = ensure_pygls()
    if using_stub and not args.quiet:
        emit(
            "note: pygls is not importable on this interpreter; using the built-in "
            "minimal stub (findings are equivalent)."
        )

    if args.no_triage:
        catalog = EMPTY_CATALOG
    else:
        try:
            catalog = load_triage(args.triage)
        except (OSError, IOError) as exc:
            return fail_setup("cannot read triage catalog %s: %s" % (args.triage, exc))
        except (ValueError, json.JSONDecodeError) as exc:
            return fail_setup("invalid triage catalog %s: %s" % (args.triage, exc))

    run = Run(args, repo_root, schema_path, pygls_mode, catalog)

    try:
        run.schema_sha256 = file_sha256(schema_path)
        run.repo_sha = git_short_sha(repo_root)
    except (OSError, IOError) as exc:
        return fail_setup("cannot read schema file %s: %s" % (schema_path, exc))

    try:
        run_corpus(run)
    except ImportError as exc:
        return fail_setup(
            "cannot import the language server from %s: %s\n"
            "Check --repo-root, and that server/ is intact." % (repo_root, exc)
        )
    except jsonschema.exceptions.SchemaError as exc:
        return fail_setup("%s is not a valid draft-06 schema: %s" % (schema_path, exc))
    except json.JSONDecodeError as exc:
        return fail_setup("%s is not valid JSON: %s" % (schema_path, exc))

    report_dir = os.path.abspath(args.report_dir)
    try:
        if not os.path.isdir(report_dir):
            os.makedirs(report_dir)
        write_report(os.path.join(report_dir, "summary.txt"), render_summary(run))
        write_report(os.path.join(report_dir, "findings.txt"), render_findings_txt(run))
        write_report(os.path.join(report_dir, "findings.json"), render_findings_json(run))
        write_report(os.path.join(report_dir, "safe-summary.txt"), render_safe_summary(run))
        # Always written: safe-summary.txt always refers to files by anonymous id,
        # so the human always needs the mapping to resolve them locally.
        write_report(os.path.join(report_dir, "path-map.txt"), render_path_map(run))
    except (OSError, IOError) as exc:
        return fail_setup("cannot write reports to %s: %s" % (report_dir, exc))

    print_console_report(run)
    console(run, "")
    console(run, "reports written to %s" % report_dir)

    return compute_exit_code(run)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        sys.exit(EXIT_UNEXPECTED)
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        sys.stderr.write("\nunexpected error - this is a bug in validate_blueprints.py\n")
        sys.exit(EXIT_UNEXPECTED)
