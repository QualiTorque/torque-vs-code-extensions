#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Secret sanitizer for Torque blueprint YAML corpora.

PURPOSE
-------
Customer blueprint repositories routinely contain proprietary data: cloud
credentials, private keys, internal hostnames, customer e-mail addresses.  We
want such blueprints as a *validation corpus* for the Torque VS Code language
server, but the raw files must never be read by anything (or anyone) outside
the person who received them.

This script produces a sanitized copy of a blueprint tree: same directory
layout, same files, same bytes -- except that every substring that looks like a
secret is replaced by a stable, YAML-safe placeholder.

CONFIDENTIALITY MODEL
---------------------
* The operator (a human) runs this script.  It is deliberately dependency-free
  (Python 3.7+, standard library only) so it can be inspected in one sitting and
  executed on an air-gapped machine.
* THERE IS NO NETWORK CODE IN THIS FILE.  No sockets, no urllib, no subprocess.
* Original values are held in memory only.  They are never written to the
  reports.  The reports carry the first 8 hex digits of the sha256 of an
  original value, which is enough to correlate duplicate occurrences and
  nothing else.  A reversible mapping is written only if the operator explicitly
  passes --emit-mapping, and that file is then as sensitive as the input.

NEVER-OVERWRITE GUARANTEE
-------------------------
* Input files are opened read-only, in binary mode, and never written to.
* Every file under the input tree is hashed (sha256) before the run and again
  afterwards; the two manifests must match exactly, or the script aborts loudly
  with exit code 4.
* Unsafe invocations are refused up-front (exit code 3): output == input,
  output nested in input, input nested in output, report/mapping paths inside
  the input tree, or a non-empty output directory without --force.

WHY TEXT-BASED REDACTION (AND NOT load-yaml/dump-yaml)
------------------------------------------------------
The whole point of the corpus is to exercise a *parser and validator* against
real-world messiness: comments, flow style, tab/space mixtures, mojibake, CRLF,
duplicate keys, and files that do not even parse.  Round-tripping through a
YAML library would normalize all of that away -- and would simply fail on the
unparseable files, which are the most interesting ones.  So this tool rewrites
only the sensitive substrings and preserves every other byte, the line count,
and (where possible) the column layout.

WHAT IS REDACTED
----------------
Two mechanisms, both text-level:
  A. key-name based -- the whole value of a line whose key looks secret-ish
     (password, client_secret, api_key, "Administrator Password", ...), plus
     `default:` / `value:` sitting under such a key;
  B. value-pattern based -- substrings matching a detector (PEM blocks, JWTs,
     cloud keys, URL userinfo, inline `--password X` / `TOKEN=X`, base64 blobs,
     high-entropy hex, and the opt-in identity patterns).  Mechanism B also
     runs inside block scalars and shell command bodies.

PROTECTION RULES (structure the downstream validators must still see)
---------------------------------------------------------------------
1. A YAML key is never rewritten -- only values, or substrings inside values.
2. Pure-Liquid values ({{ ... }} / {% ... %}) are never redacted, and Liquid
   spans inside longer text are protected, so patterns run around them.
3. `pattern:` and `validation-description:` values are exempt from BOTH
   mechanisms: a pattern is a regex whose exact content decides an input's
   required-vs-optional semantics, and the description is the UI text quoting
   it.  Those lines come out byte-identical.
4. Content-addressed keys (commit, sha, sha1, sha256, digest, image, tag, ref,
   revision, version, chart-version, path, store, path-in-archive) -- and any
   `sha256:` / `sha512:` / `sha1:` / `md5:`-prefixed digest anywhere, including
   inside command bodies -- are exempt from the two entropy heuristics
   (base64-blob, high-entropy-hex) and ONLY those two.  Git SHAs and image
   digests are public content addresses; every other detector still applies, so
   a real token pasted into `path:` is still caught.
5. YAML aliases (*name) are left alone, and an anchor definition keeps its
   &name.
6. Comment lines are scanned by mechanism B (people paste live tokens into
   comments) but never by mechanism A -- a comment has no YAML key.
Placeholders are `REDACTED_<CATEGORY>_<n>`, stable per run: the same original
value always maps to the same placeholder, and re-running the tool over its own
output is a no-op.

EXIT CODES
----------
0  success, no residual findings in the output
2  residual secrets found in the output tree (or --self-test failure)
3  safety refusal / bad usage
4  unexpected error (traceback printed) or input-tree mutation detected
"""

from __future__ import print_function

import argparse
import contextlib
import datetime
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import tempfile
import traceback
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple

TOOL_NAME = "sanitize_blueprints.py"
TOOL_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Category groups (what --categories accepts) and their defaults.
# ---------------------------------------------------------------------------

GROUP_SECRET = "secret"
GROUP_CERTIFICATE = "certificate"
GROUP_URL_CREDENTIALS = "url-credentials"
GROUP_EMAIL = "email"
GROUP_IP = "ip"
GROUP_HOSTNAME = "hostname"
GROUP_IDENTIFIER = "identifier"

ALL_GROUPS = (
    GROUP_SECRET,
    GROUP_CERTIFICATE,
    GROUP_URL_CREDENTIALS,
    GROUP_EMAIL,
    GROUP_IP,
    GROUP_HOSTNAME,
    GROUP_IDENTIFIER,
)

# Identity scrubbing is opt-in: the default run must distort the corpus as
# little as possible, because hostnames/IPs/e-mails change the *shape* of the
# scalars the validators are tested against far more than a secret does.
DEFAULT_GROUPS = (GROUP_SECRET, GROUP_CERTIFICATE, GROUP_URL_CREDENTIALS)

SKIP_DIR_NAMES = frozenset(
    [".git", "node_modules", "__pycache__", ".venv", ".tmp", ".mypy_cache", ".pytest_cache"]
)

DEFAULT_INCLUDE_EXT = (".yaml", ".yml")
DEFAULT_MAX_FILE_MB = 5
DEFAULT_BASE64_MIN = 40

# ---------------------------------------------------------------------------
# Mechanism A: secret-ish key names.
# ---------------------------------------------------------------------------

# Matched with word boundaries against a normalized key (lower-cased, with
# spaces/dashes folded to underscores), so "Administrator Password",
# "api-key" and "client_secret" all hit.
SECRET_KEY_TOKENS = frozenset(
    [
        "password",
        "passwd",
        "pwd",
        "passphrase",
        "secret",
        "client_secret",
        "secret_key",
        "token",
        "api_token",
        "auth_token",
        "access_token",
        "refresh_token",
        "bearer_token",
        "api_key",
        "apikey",
        "access_key",
        "private_key",
        "privatekey",
        "ssh_key",
        "ssh_private_key",
        "license_key",
        "account_key",
        "subscription_key",
        "encryption_key",
        "sas_token",
        "connection_string",
        "conn_string",
        "dsn",
        "credential",
        "credentials",
        "auth",
        "authorization",
        "pem",
        "pfx",
        "keystore",
        "truststore",
        "htpasswd",
        "webhook_url",
        "sas",
    ]
)

# A few tokens are also matched *glued* (substring, no separator required),
# because "mypassword" / "dbtoken" appear in the wild.  Kept deliberately
# small; the NEVER_REDACT_KEYS list below is consulted first, so structural
# names such as secret-name or credential_name are unaffected.
GLUED_KEY_TOKENS = frozenset(["password", "passwd", "passphrase", "secret", "apikey", "token"])

# NOTE ON THE BARE `key` TOKEN -- deliberately absent from SECRET_KEY_TOKENS.
# Torque blueprints use `- key: Provider` for label objects, plus `key-prefix`,
# `public_key`, `key_pair_name`, `key_name`, `secret-name`, `secret-namespace`
# as *structural* fields.  Redacting those would destroy exactly the structure
# the downstream validators must see, and none of them carry a secret value.
# `credential_name: my-aws-cred` is a reference *by name*; `password: hunter2`
# is a secret.  Only the latter is redacted.
NEVER_REDACT_KEYS = frozenset(
    [
        "key",
        "key-prefix",
        "keys",
        "public_key",
        "publickey",
        "key_pair_name",
        "keypair_name",
        "secret-name",
        "secret-namespace",
        "secretname",
        "secret-path",
        "key_name",
        "keyname",
        "ssh_key_name",
        "credential_name",
        "credentials_name",
        "agent_name",
        "target_name",
        "store",
        "path",
        "source",
        "kind",
        "type",
        "style",
        "pattern",
        "validation-description",
        "spec_version",
        "depends-on",
        "allowed-values",
        "allowed-formats",
        "allowed-credential-providers",
        "quantity",
        "mode",
        "scope",
        "name",
        "display-name",
        "description",
        "value",
        "region",
        "namespace",
        "version",
        "tf-version",
        "chart-version",
        "command",
        "commands",
        "arguments",
        "command-arguments",
        "image",
        "timeout",
        "cron",
        "event",
        "labels-selector",
        "label-selector",
        "parameter-name",
        "source-name",
    ]
)


def _normalize_key_variants(raw_key):
    # type: (str) -> Tuple[str, str]
    """Return (dashed, underscored) normalized forms of a key name.

    NEVER_REDACT_KEYS mixes dashed and underscored spellings, so both forms are
    produced and both are looked up.
    """
    k = raw_key.strip()
    if len(k) >= 2 and k[0] == k[-1] and k[0] in ("'", '"'):
        k = k[1:-1]
    k = k.strip().lower()
    k = re.sub(r"\s+", "_", k)
    underscored = k.replace("-", "_")
    dashed = k.replace("_", "-")
    return dashed, underscored


def key_in(raw_key, key_set):
    # type: (str, frozenset) -> bool
    """Membership test tolerant of dashed/underscored/spaced key spellings."""
    dashed, underscored = _normalize_key_variants(raw_key)
    return dashed in key_set or underscored in key_set


def key_is_never_redacted(raw_key):
    # type: (str) -> bool
    return key_in(raw_key, NEVER_REDACT_KEYS)


def key_is_secretish(raw_key):
    # type: (str) -> bool
    """True when mechanism A should redact the whole value of this key."""
    if key_is_never_redacted(raw_key):
        return False
    _dashed, underscored = _normalize_key_variants(raw_key)
    if not underscored:
        return False
    for token in SECRET_KEY_TOKENS:
        if re.search(r"(?:^|_)" + re.escape(token) + r"(?:_|$)", underscored):
            return True
    for token in GLUED_KEY_TOKENS:
        if token in underscored:
            return True
    return False


# ---------------------------------------------------------------------------
# Mechanism B: value patterns.
# ---------------------------------------------------------------------------


class Detector(object):
    """One value pattern.

    label        fine-grained category, used in reports and placeholder names
    group        coarse category gated by --categories
    regex        compiled pattern
    redact_group group index whose span is replaced (0 == the whole match)
    guard        optional callable(matched_text, context, start) -> True to skip
                 this match; `context` is the surrounding text and `start` the
                 match offset within it, so a guard can look at what precedes.
    """

    __slots__ = ("label", "group", "regex", "redact_group", "guard")

    def __init__(self, label, group, pattern, flags=0, redact_group=0, guard=None):
        self.label = label
        self.group = group
        self.regex = re.compile(pattern, flags)
        self.redact_group = redact_group
        self.guard = guard


LOOPBACK_ADDRESSES = frozenset(
    ["0.0.0.0", "127.0.0.1", "255.255.255.255", "::1", "0:0:0:0:0:0:0:1", "::"]
)

# TLD allow-list for the (opt-in) hostname detector.  A generic
# "label.label" rule would happily eat main.tf, values.yaml and app.py.
HOSTNAME_TLDS = (
    "com|net|org|io|co|us|eu|uk|de|fr|jp|in|cn|ru|il|ca|au|gov|edu|mil|info|biz|"
    "local|localdomain|internal|intranet|corp|lan|cloud|dev|app|ai|sh|xyz|tech|"
    "systems|services|azure|amazonaws|googleapis|windows"
)


def _guard_ip(text, context="", start=0):
    # type: (str, str, int) -> bool
    return text.strip() in LOOPBACK_ADDRESSES


def _guard_hostname(text, context="", start=0):
    # type: (str, str, int) -> bool
    return text.strip().lower() in ("localhost", "localhost.localdomain")


def _guard_content_address(text, context="", start=0):
    # type: (str, str, int) -> bool
    """Skip digest tokens introduced by `sha256:` and friends.

    Applies to the entropy heuristics only, and works anywhere -- including
    `docker pull repo/img@sha256:<64 hex>` inside a shell grain body, where
    there is no key name to exempt.
    """
    return bool(DIGEST_PREFIX_RE.search(context[:start]))


def build_detectors(active_groups, base64_min):
    # type: (Set[str], int) -> List[Detector]
    """Compile the ordered detector table for the active category groups.

    Order matters: the most specific patterns run first so that a JWT inside a
    URL userinfo is attributed to url-credentials, and so that the broad
    base64 / hex sweeps only see what is left over.
    """
    table = [
        # Inline (single-line) PEM blocks; the multi-line form is handled by a
        # dedicated pre-pass so that line counts survive.
        Detector(
            "pem-private-key",
            GROUP_SECRET,
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        ),
        Detector(
            "certificate",
            GROUP_CERTIFICATE,
            r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        ),
        Detector(
            "ssh-public-key",
            GROUP_SECRET,
            r"ssh-(?:rsa|ed25519|dss|ecdsa)\s+AAAA[0-9A-Za-z+/=]{20,}",
        ),
        # Keep the scheme and host so the URL shape survives; redact userinfo.
        Detector(
            "url-credentials",
            GROUP_URL_CREDENTIALS,
            r"(://)([^/\s:@\"']+:[^/\s@\"']+)(@)",
            redact_group=2,
        ),
        Detector("jwt", GROUP_SECRET, r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
        Detector(
            "aws-access-key-id",
            GROUP_SECRET,
            r"(?:A3T[A-Z0-9]|AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}",
        ),
        Detector("github-token", GROUP_SECRET, r"gh[pousr]_[A-Za-z0-9]{30,}"),
        Detector("slack-token", GROUP_SECRET, r"xox[baprs]-[A-Za-z0-9-]{10,}"),
        Detector("google-api-key", GROUP_SECRET, r"AIza[0-9A-Za-z_-]{35}"),
        Detector("bcrypt-hash", GROUP_SECRET, r"\$2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}"),
        Detector(
            "inline-authorization",
            GROUP_SECRET,
            r"(authorization\s*:\s*(?:bearer|basic)\s+)([A-Za-z0-9._~+/=-]{8,})",
            flags=re.IGNORECASE,
            redact_group=2,
        ),
        Detector(
            "inline-cli-secret",
            GROUP_SECRET,
            r"(--?(?:password|passwd|token|api-?key|secret)[= ]+)([\"']?)([^\s\"']{4,})",
            flags=re.IGNORECASE,
            redact_group=3,
        ),
        Detector(
            "inline-env-assignment",
            GROUP_SECRET,
            r"\b([A-Z0-9_]*(?:PASSWORD|PASSWD|TOKEN|SECRET|APIKEY|API_KEY|PRIVATE_KEY)[A-Z0-9_]*=)"
            r"([\"']?)([^\s\"']{4,})",
            flags=re.IGNORECASE,
            redact_group=3,
        ),
        # Catches things like kubeconfig_b64 payloads.
        Detector(
            "base64-blob",
            GROUP_SECRET,
            r"[A-Za-z0-9+/]{%d,}={0,2}" % (max(8, int(base64_min)),),
            guard=_guard_content_address,
        ),
        Detector(
            "high-entropy-hex",
            GROUP_SECRET,
            r"\b[0-9a-fA-F]{32,}\b",
            guard=_guard_content_address,
        ),
        # --- opt-in identity scrubbing -------------------------------------
        Detector("email", GROUP_EMAIL, r"[\w.+-]+@[\w-]+\.[\w.]+"),
        Detector(
            "ip",
            GROUP_IP,
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\b",
            guard=_guard_ip,
        ),
        # Requires >= 4 colon-separated groups (or a compressed "::") to avoid
        # eating clock/cron-ish values such as 12:34:56.
        Detector(
            "ip",
            GROUP_IP,
            r"(?:\b(?:[0-9A-Fa-f]{1,4}:){3,7}(?::|[0-9A-Fa-f]{1,4})\b)|(?:\b[0-9A-Fa-f]{1,4}::[0-9A-Fa-f:]{1,29}\b)",
            guard=_guard_ip,
        ),
        Detector(
            "hostname",
            GROUP_HOSTNAME,
            r"\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+(?:%s)\b" % HOSTNAME_TLDS,
            flags=re.IGNORECASE,
            guard=_guard_hostname,
        ),
        Detector(
            "identifier",
            GROUP_IDENTIFIER,
            r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
        ),
        Detector("identifier", GROUP_IDENTIFIER, r"\b[A-Z]{3}[0-9]{4}[A-Z0-9]{4}\b"),
    ]
    return [d for d in table if d.group in active_groups]


# ---------------------------------------------------------------------------
# Small text helpers.
# ---------------------------------------------------------------------------

_LIQUID_SPAN_RE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}")
_PURE_LIQUID_RE = re.compile(r"^(?:\{\{.*\}\}|\{%.*%\})$", re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"^REDACTED_[A-Z0-9]+(?:_[A-Z0-9]+)*_[0-9]+$")
_PLACEHOLDER_BODY_RE = re.compile(r"^(?:\s*REDACTED_[A-Z0-9_]+_[0-9]+\s*)+$")
_COMMENT_ONLY_RE = re.compile(r"^\s*#")
_BLOCK_SCALAR_RE = re.compile(r"^[|>](?:[0-9]*[+-]?|[+-]?[0-9]*)$")
_PEM_BEGIN_RE = re.compile(r"-----BEGIN ([A-Z0-9 ]*?)-----")
_PEM_END_RE = re.compile(r"-----END ([A-Z0-9 ]*?)-----")

# Keys that are structural on their own, but carry the actual material when
# they sit UNDER a secret-ish parent key -- the common Torque input shape:
#     inputs:
#       - Admin Password:
#           type: password
#           default: Tr0ub4dor&3     <-- this is a live secret
# Mechanism A alone cannot see this, because `default` is (rightly) a
# never-redact key name.  So a small parent-key context is tracked and only
# these child keys are promoted to secret when an ancestor key is secret-ish.
CONTEXT_SENSITIVE_CHILD_KEYS = frozenset(["default", "defaults", "value", "values"])

# CONTENT-ADDRESSED keys.  A git SHA, an OCI image digest, a chart version or a
# repo path is a *content address*: it identifies immutable content that is
# already public to anyone holding the repo, and it is never a credential.
# Redacting one destroys fidelity (the downstream validators check these fields)
# for zero security gain -- so the two entropy heuristics, and ONLY those two,
# are switched off for values under these keys.  Every other detector still
# runs here, so a real token pasted into `path:` is still caught.
CONTENT_ADDRESSED_KEYS = frozenset(
    [
        "commit",
        "sha",
        "sha1",
        "sha256",
        "digest",
        "image",
        "tag",
        "ref",
        "revision",
        "version",
        "chart-version",
        "path",
        "store",
        "path-in-archive",
    ]
)

# The entropy heuristics -- broad, shape-based, and the only detectors the
# content-addressed exemption disables.
ENTROPY_DETECTOR_LABELS = frozenset(["base64-blob", "high-entropy-hex"])

# Keys whose value is exempt from BOTH mechanisms, i.e. the line is left
# byte-identical.
#   pattern                : a regex whose exact content is load-bearing for
#                            Torque's required/optional semantics.  Substituting
#                            a placeholder inside it can silently flip an input
#                            from optional to required (or the reverse), which
#                            would make the whole corpus lie to the validator
#                            under test.
#   validation-description : user-facing UI text that accompanies a pattern;
#                            it routinely quotes the pattern's intent ("Empty or
#                            an IP in 10.0.0.0/24") and carries no secret.
NO_SCAN_VALUE_KEYS = frozenset(["pattern", "validation-description"])

# `sha256:<hex>` / `sha512:` / `sha1:` / `md5:` digest tokens are content
# addresses wherever they appear -- including inline in `docker pull ...@sha256:`
# lines inside shell grain bodies, where no key name is available to exempt.
DIGEST_PREFIX_RE = re.compile(r"(?:sha256|sha512|sha1|md5)\s*[:=]\s*$", re.IGNORECASE)

# A plausible YAML key: no quotes or brackets inside, not absurdly long.  This
# keeps mechanism A from mis-firing on shell lines such as
#   curl -H "Authorization: Bearer ..."
# where the text before the colon merely *looks* like a key.
_PLAUSIBLE_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-/ ]{1,64}$")

_KEY_VALUE_RE = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?P<dash>(?:-[ \t]+)*)"
    r"(?P<key>\"[^\"\n]*\"|'[^'\n]*'|[^\s#\-][^:\n]*?)"
    r"[ \t]*:(?P<sep>[ \t]+|$)"
    r"(?P<rest>.*)$"
)


def split_lines_keepends(text):
    # type: (str) -> List[Tuple[str, str]]
    """Split into [(content_without_eol, eol), ...] preserving each terminator.

    str.splitlines() also breaks on \\v, \\f, \\x1c and U+2028, which would
    silently rewrite exotic bytes; this only recognizes CR, LF and CRLF.
    """
    out = []  # type: List[Tuple[str, str]]
    pos = 0
    n = len(text)
    while pos < n:
        idx_n = text.find("\n", pos)
        idx_r = text.find("\r", pos)
        if idx_n < 0 and idx_r < 0:
            out.append((text[pos:], ""))
            return out
        if idx_r < 0 or (0 <= idx_n < idx_r):
            out.append((text[pos:idx_n], "\n"))
            pos = idx_n + 1
        else:
            if idx_n == idx_r + 1:
                out.append((text[pos:idx_r], "\r\n"))
                pos = idx_r + 2
            else:
                out.append((text[pos:idx_r], "\r"))
                pos = idx_r + 1
    return out


def join_lines(lines):
    # type: (Sequence[Tuple[str, str]]) -> str
    return "".join(content + eol for content, eol in lines)


def is_pure_liquid(value):
    # type: (str) -> bool
    """True for values that are nothing but a Liquid expression."""
    core = unquote_scalar(value).strip()
    return bool(core) and bool(_PURE_LIQUID_RE.match(core))


def unquote_scalar(value):
    # type: (str) -> str
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def quote_style(value):
    # type: (str) -> str
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[0]
    return ""


def split_value_and_trailing(rest):
    # type: (str) -> Tuple[str, str]
    """Split the text after 'key:' into (value, trailing).

    `trailing` holds any whitespace plus an end-of-line comment, so it can be
    re-attached verbatim and scanned separately (people paste tokens into
    comments).
    """
    if not rest:
        return "", ""
    if rest[0] == '"':
        i = 1
        while i < len(rest):
            c = rest[i]
            if c == "\\":
                i += 2
                continue
            if c == '"':
                i += 1
                break
            i += 1
        return rest[:i], rest[i:]
    if rest[0] == "'":
        i = 1
        while i < len(rest):
            if rest[i] == "'":
                if i + 1 < len(rest) and rest[i + 1] == "'":
                    i += 2
                    continue
                i += 1
                break
            i += 1
        return rest[:i], rest[i:]
    m = re.search(r"(?:(?<=[ \t])|^)#", rest)
    core = rest[: m.start()] if m else rest
    stripped = core.rstrip()
    return stripped, rest[len(stripped) :]


def sha256_hex(text):
    # type: (str) -> str
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()


def sha8(text):
    # type: (str) -> str
    return sha256_hex(text)[:8]


def shannon_entropy(text):
    # type: (str) -> float
    if not text:
        return 0.0
    counts = {}  # type: Dict[str, int]
    for ch in text:
        counts[ch] = counts.get(ch, 0) + 1
    total = float(len(text))
    acc = 0.0
    for c in counts.values():
        p = c / total
        acc -= p * math.log(p, 2)
    return acc


# ---------------------------------------------------------------------------
# Findings, warnings, placeholders.
# ---------------------------------------------------------------------------


class Finding(object):
    __slots__ = ("rel_path", "line", "col", "label", "group", "key", "length", "sha8", "mechanism")

    def __init__(self, rel_path, line, col, label, group, key, length, digest, mechanism):
        self.rel_path = rel_path
        self.line = line
        self.col = col
        self.label = label
        self.group = group
        self.key = key
        self.length = length
        self.sha8 = digest
        self.mechanism = mechanism

    def to_dict(self):
        # type: () -> Dict[str, object]
        return {
            "file": self.rel_path,
            "line": self.line,
            "col": self.col,
            "category": self.label,
            "group": self.group,
            "key": self.key,
            "length": self.length,
            "sha256_prefix": self.sha8,
            "mechanism": self.mechanism,
        }

    def format_line(self):
        # type: () -> str
        return "{0}:{1}  {2:<22} key={3:<28} len={4:<5} sha256={5}  [{6}]".format(
            self.line,
            self.col,
            self.label,
            self.key if self.key else "-",
            self.length,
            self.sha8,
            self.mechanism,
        )


class PlaceholderAllocator(object):
    """Stable per-run identity map: same original value -> same placeholder."""

    def __init__(self):
        # type: () -> None
        self._map = {}  # type: Dict[Tuple[str, str], str]
        self._counters = {}  # type: Dict[str, int]
        self.entries = []  # type: List[Tuple[str, str]]

    def get(self, label, original):
        # type: (str, str) -> str
        key = (label, original)
        existing = self._map.get(key)
        if existing is not None:
            return existing
        slug = re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_") or "VALUE"
        n = self._counters.get(slug, 0) + 1
        self._counters[slug] = n
        placeholder = "REDACTED_{0}_{1}".format(slug, n)
        self._map[key] = placeholder
        self.entries.append((placeholder, original))
        return placeholder

    def mapping(self):
        # type: () -> List[Tuple[str, str]]
        return list(self.entries)


class RunContext(object):
    """Everything the text pipeline needs, allocated once per pass."""

    def __init__(self, active_groups, base64_min):
        # type: (Set[str], int) -> None
        self.active_groups = set(active_groups)
        self.base64_min = base64_min
        self.detectors = build_detectors(self.active_groups, base64_min)
        self.allocator = PlaceholderAllocator()


# ---------------------------------------------------------------------------
# Segment machinery: protected spans never get rescanned.
# ---------------------------------------------------------------------------


class _Segment(object):
    __slots__ = ("text", "offset", "protected")

    def __init__(self, text, offset, protected):
        # type: (str, int, bool) -> None
        self.text = text
        self.offset = offset
        self.protected = protected


def _split_liquid(text, base_offset):
    # type: (str, int) -> List[_Segment]
    """Protect {{ ... }} / {% ... %} spans: they are structural references the
    downstream validators must still see, so patterns never run inside them."""
    segs = []  # type: List[_Segment]
    pos = 0
    for m in _LIQUID_SPAN_RE.finditer(text):
        if m.start() > pos:
            segs.append(_Segment(text[pos : m.start()], base_offset + pos, False))
        segs.append(_Segment(m.group(0), base_offset + m.start(), True))
        pos = m.end()
    if pos < len(text) or not segs:
        segs.append(_Segment(text[pos:], base_offset + pos, False))
    return segs


def redact_span_text(text, base_offset, ctx, rel_path, line_no, key, findings, skip_labels=frozenset()):
    # type: (str, int, RunContext, str, int, Optional[str], List[Finding], frozenset) -> str
    """Run every active detector over `text`, honoring Liquid protection.

    `base_offset` is the 0-based column of `text` within its line, so reported
    columns refer to the ORIGINAL line.  Leftover (unreplaced) segments keep
    their original text, so their offsets stay exact.

    `skip_labels` disables individual detectors for this span -- used by the
    content-addressed key exemption, which switches off the two entropy
    heuristics and nothing else.
    """
    if not text:
        return text
    segs = _split_liquid(text, base_offset)
    for det in ctx.detectors:
        if det.label in skip_labels:
            continue
        next_segs = []  # type: List[_Segment]
        for seg in segs:
            if seg.protected or not seg.text:
                next_segs.append(seg)
                continue
            next_segs.extend(_apply_detector(det, seg, ctx, rel_path, line_no, key, findings))
        segs = next_segs
    return "".join(s.text for s in segs)


def _apply_detector(det, seg, ctx, rel_path, line_no, key, findings):
    # type: (Detector, _Segment, RunContext, str, int, Optional[str], List[Finding]) -> List[_Segment]
    out = []  # type: List[_Segment]
    pos = 0
    for m in det.regex.finditer(seg.text):
        gi = det.redact_group
        try:
            start, end = m.span(gi)
        except IndexError:  # pragma: no cover - defensive
            continue
        if start < 0 or end <= start:
            continue
        if start < pos:
            continue
        original = seg.text[start:end]
        if det.guard is not None and det.guard(original, seg.text, start):
            continue
        if _PLACEHOLDER_RE.match(original.strip()):
            continue
        if "{{" in original or "{%" in original:
            continue
        placeholder = ctx.allocator.get(det.label, original)
        findings.append(
            Finding(
                rel_path,
                line_no,
                seg.offset + start + 1,
                det.label,
                det.group,
                key,
                len(original),
                sha8(original),
                "B",
            )
        )
        if start > pos:
            out.append(_Segment(seg.text[pos:start], seg.offset + pos, False))
        out.append(_Segment(placeholder, seg.offset + start, True))
        pos = end
    if pos < len(seg.text):
        out.append(_Segment(seg.text[pos:], seg.offset + pos, False))
    return out


# ---------------------------------------------------------------------------
# PEM pre-pass (multi-line blocks).
# ---------------------------------------------------------------------------


class _PemBody(object):
    __slots__ = ("label", "group", "placeholder", "is_first", "body_len", "digest")

    def __init__(self, label, group, placeholder, is_first, body_len, digest):
        self.label = label
        self.group = group
        self.placeholder = placeholder
        self.is_first = is_first
        self.body_len = body_len
        self.digest = digest


def _pem_label_for(marker):
    # type: (str) -> Optional[Tuple[str, str]]
    if "PRIVATE KEY" in marker:
        return "pem-private-key", GROUP_SECRET
    if "CERTIFICATE" in marker and "REQUEST" not in marker:
        return "certificate", GROUP_CERTIFICATE
    return None


def scan_pem_blocks(lines, ctx, warnings, rel_path):
    # type: (Sequence[Tuple[str, str]], RunContext, List[str], str) -> Dict[int, _PemBody]
    """Map line index -> _PemBody for the body lines of multi-line PEM blocks.

    Marker lines are intentionally left intact: keeping BEGIN/END preserves the
    structure of the scalar, and only the base64 body carries the material.
    Line count and indentation are preserved because each body line is
    replaced in place.
    """
    mapping = {}  # type: Dict[int, _PemBody]
    i = 0
    n = len(lines)
    while i < n:
        content = lines[i][0]
        mb = _PEM_BEGIN_RE.search(content)
        if not mb:
            i += 1
            continue
        marker = mb.group(1).strip()
        labeled = _pem_label_for(marker)
        # An inline BEGIN...END on one line is handled by the inline detectors.
        if _PEM_END_RE.search(content[mb.end() :]):
            i += 1
            continue
        end_idx = -1
        for j in range(i + 1, n):
            if _PEM_END_RE.search(lines[j][0]):
                end_idx = j
                break
        if end_idx < 0:
            warnings.append(
                "{0}: unterminated PEM block starting at line {1} "
                "(marker '{2}'); relying on base64/hex detectors".format(rel_path, i + 1, marker)
            )
            i += 1
            continue
        body_indices = list(range(i + 1, end_idx))
        body_text = "".join(lines[k][0].strip() for k in body_indices)
        if labeled is None or labeled[1] not in ctx.active_groups:
            i = end_idx + 1
            continue
        if not body_text or _PLACEHOLDER_BODY_RE.match("\n".join(lines[k][0] for k in body_indices)):
            # Already sanitized (idempotent re-run / residual scan).
            i = end_idx + 1
            continue
        label, group = labeled
        placeholder = ctx.allocator.get(label, body_text)
        digest = sha8(body_text)
        first = True
        for k in body_indices:
            mapping[k] = _PemBody(label, group, placeholder, first, len(body_text), digest)
            first = False
        i = end_idx + 1
    return mapping


# ---------------------------------------------------------------------------
# Core: process one file's text.
# ---------------------------------------------------------------------------


class _BlockState(object):
    __slots__ = ("parent_indent", "key", "secret", "is_pattern")

    def __init__(self, parent_indent, key, secret, is_pattern):
        self.parent_indent = parent_indent
        self.key = key
        self.secret = secret
        self.is_pattern = is_pattern


def _leading_ws_len(content):
    # type: (str) -> int
    i = 0
    while i < len(content) and content[i] in " \t":
        i += 1
    return i


def _looks_non_string(core):
    # type: (str) -> bool
    if not core:
        return False
    if core[0] in "[{&*!":
        return True
    if core.lower() in ("true", "false", "null", "~", "yes", "no", "on", "off"):
        return True
    return bool(re.match(r"^[-+]?[0-9][0-9_]*(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?$", core))


def process_text(text, rel_path, ctx):
    # type: (str, str, RunContext) -> Tuple[str, List[Finding], List[str]]
    """Redact `text`, returning (new_text, findings, warnings).

    Byte-preserving by construction: only the matched substrings are rewritten.
    """
    findings = []  # type: List[Finding]
    warnings = []  # type: List[str]
    lines = split_lines_keepends(text)
    pem_map = scan_pem_blocks(lines, ctx, warnings, rel_path)

    out_lines = []  # type: List[Tuple[str, str]]
    block = None  # type: Optional[_BlockState]
    pending_secret_scalar = None  # type: Optional[Tuple[int, str]]
    # (key_column, key_name, key_is_secretish) for the enclosing mappings.
    key_stack = []  # type: List[Tuple[int, str, bool]]

    for idx, (content, eol) in enumerate(lines):
        line_no = idx + 1

        # --- multi-line PEM body -------------------------------------------
        pem = pem_map.get(idx)
        if pem is not None:
            ws = _leading_ws_len(content)
            stripped = content[ws:].rstrip()
            trailing_ws = content[ws + len(stripped) :]
            if pem.is_first:
                findings.append(
                    Finding(
                        rel_path,
                        line_no,
                        ws + 1,
                        pem.label,
                        pem.group,
                        block.key if block else None,
                        pem.body_len,
                        pem.digest,
                        "B",
                    )
                )
            out_lines.append((content[:ws] + pem.placeholder + trailing_ws, eol))
            continue

        indent_len = _leading_ws_len(content)
        is_blank = not content.strip()

        # --- close an open block scalar ------------------------------------
        if block is not None and not is_blank and indent_len <= block.parent_indent:
            block = None
        if pending_secret_scalar is not None and not is_blank:
            if indent_len <= pending_secret_scalar[0]:
                pending_secret_scalar = None

        # --- inside a block scalar body ------------------------------------
        if block is not None and not is_blank and indent_len > block.parent_indent:
            # A `pattern:` body is a regex: redacting inside it would change
            # required/optional semantics for the validators under test.
            if block.is_pattern:
                out_lines.append((content, eol))
                continue
            if block.secret:
                stripped = content[indent_len:].rstrip()
                trailing_ws = content[indent_len + len(stripped) :]
                if stripped and not _PLACEHOLDER_RE.match(stripped):
                    placeholder = ctx.allocator.get("secret", stripped)
                    findings.append(
                        Finding(
                            rel_path,
                            line_no,
                            indent_len + 1,
                            "secret",
                            GROUP_SECRET,
                            block.key,
                            len(stripped),
                            sha8(stripped),
                            "A",
                        )
                    )
                    out_lines.append((content[:indent_len] + placeholder + trailing_ws, eol))
                    continue
                out_lines.append((content, eol))
                continue
            # Ordinary block body (shell script, helm values, ...): mechanism A
            # still applies line-wise (a `password: x` line inside a script
            # body is a real secret), but no NEW block state is opened -- the
            # body is opaque text, and tracking nested indicators inside it
            # would lose the outer block.
            new_content, extra_f, extra_w = _process_single_line(
                content, rel_path, line_no, ctx, allow_block_open=False
            )
            findings.extend(extra_f)
            warnings.extend(extra_w)
            out_lines.append((new_content, eol))
            continue

        if is_blank:
            out_lines.append((content, eol))
            continue

        # --- continuation of a secret key with an empty value --------------
        if pending_secret_scalar is not None and indent_len > pending_secret_scalar[0]:
            stripped = content[indent_len:].rstrip()
            looks_structural = bool(_KEY_VALUE_RE.match(content)) or stripped.startswith("-")
            if not looks_structural and stripped and not _PLACEHOLDER_RE.match(stripped):
                trailing_ws = content[indent_len + len(stripped) :]
                placeholder = ctx.allocator.get("secret", stripped)
                findings.append(
                    Finding(
                        rel_path,
                        line_no,
                        indent_len + 1,
                        "secret",
                        GROUP_SECRET,
                        pending_secret_scalar[1],
                        len(stripped),
                        sha8(stripped),
                        "A",
                    )
                )
                out_lines.append((content[:indent_len] + placeholder + trailing_ws, eol))
                continue
            pending_secret_scalar = None

        # --- normal line ---------------------------------------------------
        secret_ancestor = _update_key_stack(key_stack, content)
        new_content, extra_f, extra_w, new_block, new_pending = _process_single_line(
            content,
            rel_path,
            line_no,
            ctx,
            allow_block_open=True,
            want_state=True,
            secret_ancestor=secret_ancestor,
        )
        findings.extend(extra_f)
        warnings.extend(extra_w)
        if new_block is not None:
            block = new_block
        if new_pending is not None:
            pending_secret_scalar = new_pending
        out_lines.append((new_content, eol))

    return join_lines(out_lines), findings, warnings


def _update_key_stack(key_stack, content):
    # type: (List[Tuple[int, str, bool]], str) -> bool
    """Maintain the enclosing-key stack; return True if an ancestor is secretish.

    Indentation-based, which is all a text-level tool can do -- and enough for
    the mapping shapes that appear in blueprints.
    """
    m = _KEY_VALUE_RE.match(content)
    if not m:
        return any(entry[2] for entry in key_stack)
    key_col = len(m.group("indent")) + len(m.group("dash"))
    while key_stack and key_stack[-1][0] >= key_col:
        key_stack.pop()
    ancestor_secret = any(entry[2] for entry in key_stack)
    raw_key = m.group("key")
    this_secret = bool(_PLAUSIBLE_KEY_RE.match(unquote_scalar(raw_key))) and key_is_secretish(raw_key)
    key_stack.append((key_col, unquote_scalar(raw_key), this_secret))
    return ancestor_secret


def _process_single_line(
    content, rel_path, line_no, ctx, allow_block_open, want_state=False, secret_ancestor=False
):
    """Redact one line.

    Returns (new_content, findings, warnings) or, when want_state is True,
    (new_content, findings, warnings, block_state_or_None, pending_or_None).
    """
    findings = []  # type: List[Finding]
    warnings = []  # type: List[str]
    block = None  # type: Optional[_BlockState]
    pending = None  # type: Optional[Tuple[int, str]]

    def result(new_content):
        if want_state:
            return new_content, findings, warnings, block, pending
        return new_content, findings, warnings

    # Comment-only lines: mechanism A is meaningless here (there is no YAML
    # key), but pattern detection IS run, because people paste live tokens into
    # comments all the time.  This asymmetry is deliberate.
    if _COMMENT_ONLY_RE.match(content):
        new_content = redact_span_text(content, 0, ctx, rel_path, line_no, None, findings)
        return result(new_content)

    m = _KEY_VALUE_RE.match(content)
    if not m:
        # Sequence item, block body line, continuation, or unparseable junk.
        new_content = redact_span_text(content, 0, ctx, rel_path, line_no, None, findings)
        return result(new_content)

    raw_key = m.group("key")
    prefix = content[: m.start("rest")]
    rest = m.group("rest")
    value, trailing = split_value_and_trailing(rest)
    value_col = m.start("rest")
    _dashed, underscored = _normalize_key_variants(raw_key)
    plausible_key = bool(_PLAUSIBLE_KEY_RE.match(unquote_scalar(raw_key)))

    if not plausible_key:
        # The text before the colon only *looks* like a key -- typically a shell
        # line such as `curl -H "Authorization: Bearer ..."` inside a script
        # body.  Treat the whole line as free text so patterns that span the
        # pseudo-colon (inline-authorization) still fire.
        new_content = redact_span_text(content, 0, ctx, rel_path, line_no, None, findings)
        return result(new_content)

    is_block_indicator = bool(_BLOCK_SCALAR_RE.match(value.strip()))
    secretish = key_is_secretish(raw_key) or (
        secret_ancestor and underscored in CONTEXT_SENSITIVE_CHILD_KEYS
    )

    # `pattern:` and `validation-description:` values are exempt from BOTH
    # mechanisms, so the line survives byte-identical.  A `pattern` is a regex
    # whose exact content decides whether an input is required or optional in
    # Torque -- a placeholder spliced into it silently changes that semantics,
    # which would make the corpus lie to the validator under test.
    # `validation-description` is the user-facing UI text that goes with it and
    # commonly quotes the pattern ("Empty or an IP in 10.0.0.0/24"), so an
    # active `ip`/`hostname` category must not rewrite it either.  A
    # `pattern: |` block body is opaque for the same reason.
    if underscored in NO_SCAN_VALUE_KEYS or _dashed in NO_SCAN_VALUE_KEYS:
        if is_block_indicator and allow_block_open:
            block = _BlockState(
                parent_indent=len(m.group("indent")) + len(m.group("dash")),
                key=unquote_scalar(raw_key),
                secret=False,
                is_pattern=True,
            )
        return result(content)

    if is_block_indicator:
        if allow_block_open:
            block = _BlockState(
                parent_indent=len(m.group("indent")) + len(m.group("dash")),
                key=unquote_scalar(raw_key),
                secret=secretish,
                is_pattern=False,
            )
        # Nothing on this line itself is sensitive; still scan the comment.
        new_trailing = redact_span_text(
            trailing, value_col + len(value), ctx, rel_path, line_no, unquote_scalar(raw_key), findings
        )
        return result(prefix + value + new_trailing)

    core = unquote_scalar(value)
    key_display = unquote_scalar(raw_key)

    if secretish and not core.strip():
        # `password:` with the value on the following line(s).
        pending = (len(m.group("indent")) + len(m.group("dash")), key_display)

    do_mechanism_a = (
        secretish
        and bool(core.strip())
        and not is_pure_liquid(value)
        and not _PLACEHOLDER_RE.match(core.strip())
        and not core.strip().startswith("*")  # YAML alias: a reference, not a value
    )

    if do_mechanism_a:
        # A YAML anchor (&name) is structural -- other nodes alias it -- so the
        # anchor token is kept and only the value after it is redacted.
        anchor = ""
        anchor_match = re.match(r"^(&[^\s]+\s+)(.*)$", core)
        if anchor_match:
            anchor = anchor_match.group(1)
            core = anchor_match.group(2)
        if _looks_non_string(core.strip()):
            warnings.append(
                "{0}:{1}: non-string value redacted under key '{2}'".format(
                    rel_path, line_no, key_display
                )
            )
        placeholder = ctx.allocator.get("secret", core)
        q = quote_style(value)
        leading_ws = value[: len(value) - len(value.lstrip())]
        new_value = leading_ws + (q + anchor + placeholder + q if q else anchor + placeholder)
        findings.append(
            Finding(
                rel_path,
                line_no,
                value_col + 1,
                "secret",
                GROUP_SECRET,
                key_display,
                len(core),
                sha8(core),
                "A",
            )
        )
        new_trailing = redact_span_text(
            trailing, value_col + len(value), ctx, rel_path, line_no, key_display, findings
        )
        return result(prefix + new_value + new_trailing)

    # Mechanism B over the value and the trailing comment.  The key itself is
    # never passed in, so a key name can never be rewritten.  Under a
    # content-addressed key the two entropy heuristics stand down so git SHAs,
    # image digests and chart versions survive; every other detector still runs.
    skip_labels = ENTROPY_DETECTOR_LABELS if key_in(raw_key, CONTENT_ADDRESSED_KEYS) else frozenset()
    new_value = redact_span_text(
        value, value_col, ctx, rel_path, line_no, key_display, findings, skip_labels
    )
    new_trailing = redact_span_text(
        trailing, value_col + len(value), ctx, rel_path, line_no, key_display, findings
    )
    return result(prefix + new_value + new_trailing)


# ---------------------------------------------------------------------------
# Review candidates (near misses) for residual-scan.txt.
# ---------------------------------------------------------------------------


class ReviewCandidate(object):
    __slots__ = ("rel_path", "line", "col", "guess", "length")

    def __init__(self, rel_path, line, col, guess, length):
        self.rel_path = rel_path
        self.line = line
        self.col = col
        self.guess = guess
        self.length = length

    def to_dict(self):
        # type: () -> Dict[str, object]
        return {
            "file": self.rel_path,
            "line": self.line,
            "col": self.col,
            "guess": self.guess,
            "length": self.length,
        }


_REVIEW_MAX_PER_FILE = 200


def find_review_candidates(text, rel_path, active_groups, base64_min):
    # type: (str, str, Set[str], int) -> List[ReviewCandidate]
    """Locations deliberately NOT redacted that a human may want to eyeball.

    Reports location + length + a category guess only -- never any content.
    """
    out = []  # type: List[ReviewCandidate]
    inactive = set(ALL_GROUPS) - set(active_groups)
    inactive_detectors = build_detectors(inactive, base64_min) if inactive else []
    short_b64_re = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")

    for idx, (content, _eol) in enumerate(split_lines_keepends(text)):
        if len(out) >= _REVIEW_MAX_PER_FILE:
            break
        line_no = idx + 1
        m = _KEY_VALUE_RE.match(content)
        key_norm = ""
        value = ""
        value_col = 0
        if m:
            key_norm = _normalize_key_variants(m.group("key"))[1]
            value, _trailing = split_value_and_trailing(m.group("rest"))
            value_col = m.start("rest")
        if key_norm in NO_SCAN_VALUE_KEYS or key_norm.replace("_", "-") in NO_SCAN_VALUE_KEYS:
            continue

        # 0. values the content-addressed exemption deliberately let through.
        #    Surfaced so the human can confirm the exemption is not hiding a
        #    real secret behind a key like `path:` or `tag:`.
        if m is not None and key_in(m.group("key"), CONTENT_ADDRESSED_KEYS):
            core_ca = unquote_scalar(value)
            for det in build_detectors(set([GROUP_SECRET]), base64_min):
                if det.label not in ENTROPY_DETECTOR_LABELS:
                    continue
                for mm in det.regex.finditer(core_ca):
                    out.append(
                        ReviewCandidate(
                            rel_path,
                            line_no,
                            value_col + 1,
                            "content-addressed-exempt:" + key_norm,
                            len(mm.group(0)),
                        )
                    )

        # 1. base64-ish runs below the configured threshold.
        for mm in short_b64_re.finditer(content):
            token = mm.group(0)
            if len(token) >= base64_min:
                continue
            if _PLACEHOLDER_RE.match(token):
                continue
            if not (re.search(r"[a-z]", token) and re.search(r"[A-Z0-9]", token)):
                continue
            out.append(
                ReviewCandidate(rel_path, line_no, mm.start() + 1, "base64-below-threshold", len(token))
            )

        # 2. random-looking values sitting under a never-redact key.  Skipped
        #    for content-addressed keys, already covered by rule 0 above.
        core = unquote_scalar(value)
        if (
            m is not None
            and core
            and key_is_never_redacted(m.group("key"))
            and not key_in(m.group("key"), CONTENT_ADDRESSED_KEYS)
        ):
            if len(core) >= 16 and not is_pure_liquid(value) and not _PLACEHOLDER_RE.match(core):
                if shannon_entropy(core) >= 3.6:
                    out.append(
                        ReviewCandidate(
                            rel_path,
                            line_no,
                            value_col + 1,
                            "high-entropy-under-protected-key:" + key_norm,
                            len(core),
                        )
                    )

        # 3. unusually long unquoted scalars.
        if core and not quote_style(value) and len(core) > 120 and "{{" not in core:
            out.append(
                ReviewCandidate(rel_path, line_no, value_col + 1, "long-unquoted-scalar", len(core))
            )

        # 4. matches for categories that are switched off for this run.
        if inactive_detectors:
            scan_text = value if m else content
            scan_col = value_col if m else 0
            for det in inactive_detectors:
                for mm in det.regex.finditer(scan_text):
                    span = mm.span(det.redact_group)
                    if span[0] < 0 or span[1] <= span[0]:
                        continue
                    token = scan_text[span[0] : span[1]]
                    if det.guard is not None and det.guard(token, scan_text, span[0]):
                        continue
                    out.append(
                        ReviewCandidate(
                            rel_path,
                            line_no,
                            scan_col + span[0] + 1,
                            "inactive-category:" + det.label,
                            len(token),
                        )
                    )
    # Two detectors can flag the same span (a 64-hex token is both base64-ish
    # and hex); the human only needs the spot once.
    deduped = []  # type: List[ReviewCandidate]
    seen = set()  # type: Set[Tuple[int, int, str, int]]
    for cand in out:
        key = (cand.line, cand.col, cand.guess, cand.length)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cand)
    return deduped[:_REVIEW_MAX_PER_FILE]


# ---------------------------------------------------------------------------
# File system helpers.
# ---------------------------------------------------------------------------

UTF8_BOM = "\ufeff"


def norm_real(path):
    # type: (str) -> str
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def is_inside(child, parent):
    # type: (str, str) -> bool
    c = norm_real(child)
    p = norm_real(parent)
    if c == p:
        return True
    return c.startswith(p.rstrip(os.sep) + os.sep)


def iter_files(root, extra_skip_dirs=(), pruned=None):
    # type: (str, Sequence[str], Optional[List[str]]) -> Iterator[str]
    """Deterministic, sorted walk skipping noise directories.

    Pruned directory paths are appended to `pruned` so the report can say what
    was never even looked at.
    """
    skip_real = set(norm_real(p) for p in extra_skip_dirs)
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []  # type: List[str]
        for name in sorted(dirnames):
            full = os.path.join(dirpath, name)
            if name in SKIP_DIR_NAMES or norm_real(full) in skip_real:
                if pruned is not None:
                    pruned.append(rel_posix(full, root))
                continue
            keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


def iter_all_files(root):
    # type: (str) -> Iterator[str]
    """Every file under `root`, pruning nothing.

    Used for the before/after sha256 manifests: the never-modified guarantee
    must cover the whole input tree, including directories the sanitizer
    deliberately does not read (.git, node_modules, ...).
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


def rel_posix(path, root):
    # type: (str, str) -> str
    return os.path.relpath(path, root).replace(os.sep, "/")


def hash_file(path):
    # type: (str) -> str
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def manifest_of(root):
    # type: (str) -> Dict[str, Tuple[str, int]]
    """sha256 + size for every file under `root` (inputs are read-only)."""
    out = {}  # type: Dict[str, Tuple[str, int]]
    for path in iter_all_files(root):
        rel = rel_posix(path, root)
        try:
            out[rel] = (hash_file(path), os.path.getsize(path))
        except OSError as exc:
            out[rel] = ("<unreadable: {0}>".format(exc.errno), -1)
    return out


def read_text_file(path):
    # type: (str) -> Tuple[Optional[str], bool, Optional[str]]
    """Read as utf-8/surrogateescape.

    Returns (text, had_bom, error).  `text` is None when the file must be
    treated as binary/undecodable.  surrogateescape means real byte sequences
    round-trip exactly, so mojibake in the corpus is preserved.
    """
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff") or data[:4] in (
        b"\xff\xfe\x00\x00",
        b"\x00\x00\xfe\xff",
    ):
        return None, False, "UTF-16/UTF-32 encoded (not utf-8)"
    if b"\x00" in data[:4096]:
        return None, False, "binary content (NUL byte in first 4 KiB)"
    text = data.decode("utf-8", "surrogateescape")
    had_bom = text.startswith(UTF8_BOM)
    if had_bom:
        text = text[len(UTF8_BOM) :]
    return text, had_bom, None


def write_text_file(path, text, had_bom):
    # type: (str, str, bool) -> None
    payload = ((UTF8_BOM + text) if had_bom else text).encode("utf-8", "surrogateescape")
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "wb") as fh:
        fh.write(payload)


def write_report_file(path, text):
    # type: (str, str) -> None
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    # backslashreplace: report text may carry surrogate-escaped bytes from
    # exotic file names or keys; the report must stay readable ASCII-safe text.
    with open(path, "w", encoding="utf-8", errors="backslashreplace", newline="\n") as fh:
        fh.write(text)


def dir_is_nonempty(path):
    # type: (str) -> bool
    if not os.path.isdir(path):
        return False
    return bool(os.listdir(path))


# ---------------------------------------------------------------------------
# Options.
# ---------------------------------------------------------------------------


class Options(object):
    def __init__(self):
        # type: () -> None
        self.in_dir = None  # type: Optional[str]
        self.out_dir = None  # type: Optional[str]
        self.scan_only = None  # type: Optional[str]
        self.report_dir = None  # type: Optional[str]
        self.groups = set(DEFAULT_GROUPS)  # type: Set[str]
        self.include_ext = list(DEFAULT_INCLUDE_EXT)  # type: List[str]
        self.base64_min = DEFAULT_BASE64_MIN
        self.max_file_mb = DEFAULT_MAX_FILE_MB
        self.force = False
        self.dry_run = False
        self.emit_mapping = None  # type: Optional[str]
        self.quiet = False


class SafetyRefusal(Exception):
    """Raised for anything that would risk the input tree or the operator."""


def parse_categories(spec, current):
    # type: (str, Set[str]) -> Set[str]
    tokens = [t.strip() for t in spec.split(",") if t.strip()]
    if not tokens:
        return set(current)
    bare = [t for t in tokens if t[0] not in "+-"]
    result = set(current) if not bare else set()
    for token in tokens:
        op = "="
        name = token
        if token[0] in "+-":
            op = token[0]
            name = token[1:].strip()
        if name not in ALL_GROUPS:
            raise SafetyRefusal(
                "unknown category '{0}'; known categories: {1}".format(name, ", ".join(ALL_GROUPS))
            )
        if op == "-":
            result.discard(name)
        else:
            result.add(name)
    if not result:
        raise SafetyRefusal("--categories resolved to an empty set; nothing would be redacted")
    return result


def normalize_extensions(spec):
    # type: (str) -> List[str]
    out = []  # type: List[str]
    for token in spec.split(","):
        token = token.strip().lower()
        if not token:
            continue
        if not token.startswith("."):
            token = "." + token
        out.append(token)
    if not out:
        raise SafetyRefusal("--include-ext resolved to an empty list")
    return sorted(set(out))


def build_arg_parser():
    # type: () -> argparse.ArgumentParser
    epilog = """\
typical workflow
----------------
  1) look before you leap -- read-only detection report, writes nothing into
     the corpus (reports land in <CWD>\\_sanitization-report unless you say
     otherwise):
       python sanitize_blueprints.py --scan-only C:\\raw\\customer-repo ^
           --report-dir C:\\work\\scan-report

  2) trust the tool on THIS machine (temp dirs only, cleaned up afterwards):
       python sanitize_blueprints.py --self-test

  3) produce the sanitized copy (the input tree is opened read-only):
       python sanitize_blueprints.py --in C:\\raw\\customer-repo ^
           --out C:\\work\\corpus-sanitized

  4) read the reports, which for step 3 default to
     C:\\work\\corpus-sanitized\\_sanitization-report\\ :
     sanitization-report.txt and residual-scan.txt.  residual-scan.txt must
     show zero findings (exit code 2 if it does not).  Skim its REVIEW section
     by hand -- it lists the spots deliberately left alone, including values
     exempted as content addresses.

  5) only then let anything else read the sanitized tree.

exit codes
----------
  0  success, no residual findings      2  residual findings / self-test failed
  3  safety refusal or bad usage        4  unexpected error (traceback shown)

notes
-----
  * There is no network code in this script.  It never contacts anything.
  * Input files are opened read-only and verified by sha256 before and after.
  * Identity categories (email, ip, hostname, identifier) are OPT-IN:
       --categories +email,+ip
  * Structural values are protected on purpose: YAML keys, pure-Liquid values
    and Liquid spans, `pattern:` / `validation-description:` lines, and content
    addresses (commit / digest / image / tag / version / path / ... and any
    `sha256:`-prefixed digest).  Both report files spell this out under
    "KNOWN DELIBERATE NON-REDACTION".
  * --emit-mapping writes a REVERSIBLE mapping.  That file is exactly as
    sensitive as the original repository.  Do not share it.
"""
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Redact secrets from a tree of Torque blueprint YAML files, writing a "
            "sanitized copy to a separate directory.  Text-based: comments, flow "
            "style, indentation quirks, CRLF and mojibake are preserved, and files "
            "that are not valid YAML are handled too."
        ),
        epilog=epilog,
    )
    parser.add_argument("--in", dest="in_dir", metavar="SRC", help="input directory (read-only)")
    parser.add_argument(
        "--out", dest="out_dir", metavar="DST", help="output directory for the sanitized copy"
    )
    parser.add_argument(
        "--scan-only",
        dest="scan_only",
        metavar="DIR",
        help="detection-only report over DIR; writes nothing except the report",
    )
    parser.add_argument(
        "--self-test",
        dest="self_test",
        action="store_true",
        help="run the built-in planted-corpus test in a temp dir and exit",
    )
    parser.add_argument(
        "--report-dir",
        dest="report_dir",
        metavar="DIR",
        help=(
            "where to write the reports (default: <DST>\\_sanitization-report, "
            "or <CWD>\\_sanitization-report with --scan-only, which has no DST); "
            "must not be inside the input / scanned tree"
        ),
    )
    parser.add_argument(
        "--categories",
        dest="categories",
        metavar="LIST",
        help=(
            "comma-separated category list; bare names replace the defaults, "
            "'+name' adds, '-name' drops. known: " + ", ".join(ALL_GROUPS) + " (default: "
            + ",".join(DEFAULT_GROUPS)
            + ")"
        ),
    )
    parser.add_argument(
        "--include-ext",
        dest="include_ext",
        metavar="LIST",
        default=",".join(DEFAULT_INCLUDE_EXT),
        help="file extensions to process (default: %(default)s)",
    )
    parser.add_argument(
        "--base64-min",
        dest="base64_min",
        type=int,
        default=DEFAULT_BASE64_MIN,
        metavar="N",
        help="minimum length of a base64 run to redact (default: %(default)s)",
    )
    parser.add_argument(
        "--max-file-mb",
        dest="max_file_mb",
        type=float,
        default=DEFAULT_MAX_FILE_MB,
        metavar="N",
        help="skip files larger than N MiB, listing them in the report (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="allow writing into a non-empty output directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="analyze and report, but write no sanitized files",
    )
    parser.add_argument(
        "--emit-mapping",
        dest="emit_mapping",
        metavar="PATH",
        help="write placeholder -> ORIGINAL VALUE json (as sensitive as the input!)",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the final summary lines")
    return parser


def options_from_args(args):
    # type: (argparse.Namespace) -> Options
    opts = Options()
    opts.in_dir = args.in_dir
    opts.out_dir = args.out_dir
    opts.scan_only = args.scan_only
    opts.report_dir = args.report_dir
    if args.categories:
        opts.groups = parse_categories(args.categories, set(DEFAULT_GROUPS))
    opts.include_ext = normalize_extensions(args.include_ext)
    if args.base64_min < 8:
        raise SafetyRefusal("--base64-min must be >= 8")
    opts.base64_min = args.base64_min
    if args.max_file_mb <= 0:
        raise SafetyRefusal("--max-file-mb must be > 0")
    opts.max_file_mb = args.max_file_mb
    opts.force = bool(args.force)
    opts.dry_run = bool(args.dry_run)
    opts.emit_mapping = args.emit_mapping
    opts.quiet = bool(args.quiet)
    return opts


# ---------------------------------------------------------------------------
# Safety checks.
# ---------------------------------------------------------------------------


def check_sanitize_paths(opts):
    # type: (Options) -> None
    in_dir = opts.in_dir
    out_dir = opts.out_dir
    assert in_dir is not None and out_dir is not None
    if not os.path.isdir(in_dir):
        raise SafetyRefusal("--in is not an existing directory: {0}".format(in_dir))
    if norm_real(in_dir) == norm_real(out_dir):
        raise SafetyRefusal("--out must not be the same directory as --in")
    if is_inside(out_dir, in_dir):
        raise SafetyRefusal("--out must not be nested inside --in (would rewrite the input tree)")
    if is_inside(in_dir, out_dir):
        raise SafetyRefusal("--in must not be nested inside --out")
    if dir_is_nonempty(out_dir) and not opts.force:
        raise SafetyRefusal(
            "--out already exists and is not empty: {0}\n"
            "       refusing to mix sanitized output with existing content; "
            "pass --force if that is what you want".format(out_dir)
        )
    report_dir = opts.report_dir or os.path.join(out_dir, "_sanitization-report")
    if is_inside(report_dir, in_dir):
        raise SafetyRefusal("--report-dir must not be inside --in")
    opts.report_dir = report_dir
    if opts.emit_mapping and is_inside(opts.emit_mapping, in_dir):
        raise SafetyRefusal("--emit-mapping path must not be inside --in")


def check_scan_paths(opts):
    # type: (Options) -> None
    scan_dir = opts.scan_only
    assert scan_dir is not None
    if not os.path.isdir(scan_dir):
        raise SafetyRefusal("--scan-only is not an existing directory: {0}".format(scan_dir))
    report_dir = opts.report_dir or os.path.join(os.getcwd(), "_sanitization-report")
    if is_inside(report_dir, scan_dir):
        raise SafetyRefusal(
            "--report-dir must not be inside the scanned directory "
            "(scan-only never writes into the corpus)"
        )
    opts.report_dir = report_dir
    if opts.emit_mapping and is_inside(opts.emit_mapping, scan_dir):
        raise SafetyRefusal("--emit-mapping path must not be inside the scanned directory")


def assert_sources_unchanged(root, before, quiet):
    # type: (str, Dict[str, Tuple[str, int]], bool) -> None
    after = manifest_of(root)
    problems = []  # type: List[str]
    for rel in sorted(set(before) | set(after)):
        b = before.get(rel)
        a = after.get(rel)
        if b is None:
            problems.append("APPEARED: {0}".format(rel))
        elif a is None:
            problems.append("VANISHED: {0}".format(rel))
        elif a != b:
            problems.append("MODIFIED: {0}".format(rel))
    if problems:
        sys.stderr.write("\n" + "!" * 78 + "\n")
        sys.stderr.write("FATAL: the input tree changed during the run.  DO NOT TRUST THIS RUN.\n")
        for p in problems:
            sys.stderr.write("  " + p + "\n")
        sys.stderr.write("!" * 78 + "\n")
        raise RuntimeError("input tree mutated during run")
    if not quiet:
        print("  sha256 verify: {0} input files unchanged".format(len(before)))


# ---------------------------------------------------------------------------
# The passes.
# ---------------------------------------------------------------------------


class SkippedFile(object):
    __slots__ = ("rel_path", "reason")

    def __init__(self, rel_path, reason):
        self.rel_path = rel_path
        self.reason = reason

    def to_dict(self):
        # type: () -> Dict[str, object]
        return {"file": self.rel_path, "reason": self.reason}


class PassResult(object):
    def __init__(self):
        # type: () -> None
        self.findings = []  # type: List[Finding]
        self.warnings = []  # type: List[str]
        self.skipped = []  # type: List[SkippedFile]
        self.processed = []  # type: List[str]
        self.changed = []  # type: List[str]
        self.per_file = {}  # type: Dict[str, List[Finding]]
        self.pruned_dirs = []  # type: List[str]


def run_pass(src_root, dst_root, opts, ctx, exclude_dirs=()):
    # type: (str, Optional[str], Options, RunContext, Sequence[str]) -> PassResult
    """Walk src_root, redact, optionally write to dst_root.

    dst_root None (or opts.dry_run) means analyze-only.
    """
    res = PassResult()
    max_bytes = int(opts.max_file_mb * 1024 * 1024)
    write_output = dst_root is not None and not opts.dry_run

    for path in iter_files(src_root, exclude_dirs, res.pruned_dirs):
        rel = rel_posix(path, src_root)
        ext = os.path.splitext(path)[1].lower()
        if ext not in opts.include_ext:
            # NEVER copy unprocessed files: an output tree containing raw files
            # would look sanitized while it is not.
            res.skipped.append(SkippedFile(rel, "extension not included ({0})".format(ext or "<none>")))
            continue
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            res.skipped.append(SkippedFile(rel, "stat failed: {0}".format(exc)))
            continue
        if size > max_bytes:
            res.skipped.append(
                SkippedFile(rel, "too large ({0} bytes > {1} MiB limit)".format(size, opts.max_file_mb))
            )
            res.warnings.append("{0}: skipped, larger than --max-file-mb".format(rel))
            continue
        try:
            text, had_bom, err = read_text_file(path)
        except OSError as exc:
            res.skipped.append(SkippedFile(rel, "read failed: {0}".format(exc)))
            continue
        if text is None:
            res.skipped.append(SkippedFile(rel, "undecodable: {0}".format(err)))
            res.warnings.append("{0}: undecodable ({1}); NOT copied to the output".format(rel, err))
            continue

        new_text, findings, warnings = process_text(text, rel, ctx)
        res.processed.append(rel)
        res.findings.extend(findings)
        res.warnings.extend(warnings)
        if findings:
            res.per_file.setdefault(rel, []).extend(findings)
        if new_text != text:
            res.changed.append(rel)
        if len(split_lines_keepends(new_text)) != len(split_lines_keepends(text)):
            res.warnings.append("{0}: line count changed (unexpected shape change)".format(rel))

        if write_output:
            out_path = os.path.join(dst_root, *rel.split("/"))
            if opts.in_dir and is_inside(out_path, opts.in_dir):
                raise RuntimeError("refusing to write into the input tree: " + out_path)
            write_text_file(out_path, new_text, had_bom)
    return res


def residual_scan(out_root, opts, exclude_dirs):
    # type: (str, Options, Sequence[str]) -> Tuple[List[Finding], List[ReviewCandidate]]
    """Re-run the active detectors over the OUTPUT tree.

    Deliberate scoping note: only the ACTIVE categories are treated as
    residual *failures*.  Detectors for categories the operator switched off
    (the opt-in identity ones) would otherwise fail every default run; their
    matches are reported in the REVIEW section instead.
    """
    ctx = RunContext(opts.groups, opts.base64_min)
    findings = []  # type: List[Finding]
    review = []  # type: List[ReviewCandidate]
    for path in iter_files(out_root, exclude_dirs):
        ext = os.path.splitext(path)[1].lower()
        if ext not in opts.include_ext:
            continue
        rel = rel_posix(path, out_root)
        text, _had_bom, err = read_text_file(path)
        if text is None:
            findings.append(Finding(rel, 0, 0, "undecodable-output", GROUP_SECRET, None, 0, "-", "-"))
            continue
        _new_text, f, _w = process_text(text, rel, ctx)
        findings.extend(f)
        review.extend(find_review_candidates(text, rel, opts.groups, opts.base64_min))
    return findings, review


# ---------------------------------------------------------------------------
# Reports.
# ---------------------------------------------------------------------------


def _counts_by(findings, attr):
    # type: (Sequence[Finding], str) -> List[Tuple[str, int]]
    counts = {}  # type: Dict[str, int]
    for f in findings:
        k = getattr(f, attr)
        counts[k] = counts.get(k, 0) + 1
    return sorted(counts.items())


# Documented in the report so the reviewer is never surprised by a redaction
# that looks like a mistake but is a considered trade-off.
DELIBERATE_OVER_REDACTIONS = [
    "credential/credentials/auth keys: a value like `credentials: my-aws-cred` is a",
    "  reference BY NAME, not a secret, but the key token list requires redacting it.",
    "  The result is still a plain string, so blueprint structure survives; only the",
    "  name is lost.  `credential_name:` / `credentials_name:` are NOT redacted.",
    "ssh public keys: `ssh-rsa AAAA...` is redacted even though a public key is not",
    "  secret, because a public key identifies a customer machine and operator.",
    "unusually long or random-looking values under a secret-ish key are redacted even",
    "  when they are booleans, numbers or flow collections (each is listed in",
    "  WARNINGS above as 'non-string value redacted').",
]

DELIBERATE_UNDER_REDACTIONS = [
    "content addresses are kept: values under commit, sha, sha1, sha256, digest,",
    "  image, tag, ref, revision, version, chart-version, path, store and",
    "  path-in-archive are exempt from the base64/hex entropy heuristics, and so are",
    "  `sha256:`-prefixed digests anywhere (including shell command bodies).  Git",
    "  SHAs and image digests are public content addresses, and redacting them would",
    "  destroy fidelity for no security gain.  Every OTHER detector still runs on",
    "  those values, and each exempted spot is listed in residual-scan.txt REVIEW.",
    "`pattern:` and `validation-description:` lines are left byte-identical: a",
    "  pattern is a regex whose content decides required-vs-optional semantics in",
    "  Torque, and the description is the UI text that quotes it.",
    "pure Liquid values ({{ ... }} / {% ... %}) and Liquid spans inside longer text",
    "  are never rewritten -- they are structural references.",
    "YAML aliases (*name) are never redacted; an anchor definition keeps its &name.",
]


def render_text_report(opts, mode, src_root, dst_root, res, started_at, manifest_count):
    # type: (Options, str, str, Optional[str], PassResult, str, int) -> str
    lines = []  # type: List[str]
    add = lines.append
    bar = "=" * 78
    add(bar)
    add("Torque blueprint sanitization report")
    add(bar)
    add("tool                : {0} v{1}".format(TOOL_NAME, TOOL_VERSION))
    add("mode                : {0}".format(mode))
    add("started (local)     : {0}".format(started_at))
    add("input directory     : {0}".format(os.path.abspath(src_root)))
    add("output directory    : {0}".format(os.path.abspath(dst_root) if dst_root else "<none>"))
    add("report directory    : {0}".format(os.path.abspath(opts.report_dir or ".")))
    add("categories active   : {0}".format(",".join(sorted(opts.groups))))
    add("extensions          : {0}".format(",".join(opts.include_ext)))
    add("base64 min length   : {0}".format(opts.base64_min))
    add("max file size       : {0} MiB".format(opts.max_file_mb))
    add("dry run             : {0}".format("yes" if opts.dry_run else "no"))
    add("")
    add("NO NETWORK ACCESS   : this tool contains no networking code and made no")
    add("                      outbound connection of any kind.")
    add("SOURCES NEVER MODIFIED: every one of the {0} files under the input".format(manifest_count))
    add("                      directory was hashed (sha256) before and after the")
    add("                      run; the manifests matched exactly.")
    add("NO SECRET VALUES HERE : this report contains no original values, only the")
    add("                      first 8 hex digits of sha256(value) so duplicates can")
    add("                      be correlated.")
    add("")
    add("-" * 78)
    add("SUMMARY")
    add("-" * 78)
    add("files processed          : {0}".format(len(res.processed)))
    add("files modified           : {0}".format(len(res.changed)))
    add("files skipped            : {0}".format(len(res.skipped)))
    add("redactions total         : {0}".format(len(res.findings)))
    add("")
    add("  {0:<26} {1:>8}".format("category", "count"))
    add("  {0:<26} {1:>8}".format("-" * 26, "-" * 8))
    for label, count in _counts_by(res.findings, "label"):
        add("  {0:<26} {1:>8}".format(label, count))
    add("  {0:<26} {1:>8}".format("-" * 26, "-" * 8))
    add("  {0:<26} {1:>8}".format("TOTAL", len(res.findings)))
    add("")
    add("  by mechanism: " + ", ".join("{0}={1}".format(k, v) for k, v in _counts_by(res.findings, "mechanism")))
    add("")
    add("-" * 78)
    add("PER-FILE REDACTIONS")
    add("-" * 78)
    if not res.per_file:
        add("(none)")
    for rel in sorted(res.per_file):
        add("")
        add("### {0}".format(rel))
        for f in sorted(res.per_file[rel], key=lambda x: (x.line, x.col, x.label)):
            add("  " + f.format_line())
    add("")
    add("-" * 78)
    add("SKIPPED FILES (never copied into the output)")
    add("-" * 78)
    if not res.skipped:
        add("(none)")
    for s in sorted(res.skipped, key=lambda x: x.rel_path):
        add("  {0}  --  {1}".format(s.rel_path, s.reason))
    add("")
    add("-" * 78)
    add("PRUNED DIRECTORIES (not walked at all, nothing copied out of them)")
    add("-" * 78)
    if not res.pruned_dirs:
        add("(none)")
    for d in sorted(set(res.pruned_dirs)):
        add("  {0}/".format(d))
    add("")
    add("-" * 78)
    add("WARNINGS")
    add("-" * 78)
    if not res.warnings:
        add("(none)")
    for w in res.warnings:
        add("  " + w)
    add("")
    add("-" * 78)
    add("KNOWN DELIBERATE OVER-REDACTION (expected, not a bug)")
    add("-" * 78)
    for note in DELIBERATE_OVER_REDACTIONS:
        add("  " + note)
    add("")
    add("-" * 78)
    add("KNOWN DELIBERATE NON-REDACTION (expected, not a miss)")
    add("-" * 78)
    for note in DELIBERATE_UNDER_REDACTIONS:
        add("  " + note)
    add("")
    return "\n".join(lines) + "\n"


def render_json_report(opts, mode, src_root, dst_root, res, started_at, manifest_count, residual, review):
    # type: (Options, str, str, Optional[str], PassResult, str, int, List[Finding], List[ReviewCandidate]) -> str
    payload = {
        "tool": TOOL_NAME,
        "tool_version": TOOL_VERSION,
        "mode": mode,
        "started_local": started_at,
        "input_dir": os.path.abspath(src_root),
        "output_dir": os.path.abspath(dst_root) if dst_root else None,
        "report_dir": os.path.abspath(opts.report_dir or "."),
        "categories_active": sorted(opts.groups),
        "include_ext": opts.include_ext,
        "base64_min": opts.base64_min,
        "max_file_mb": opts.max_file_mb,
        "dry_run": opts.dry_run,
        "guarantees": {
            "no_network_access": True,
            "sources_verified_by_sha256": True,
            "input_files_hashed": manifest_count,
            "original_values_in_report": False,
        },
        "summary": {
            "files_processed": len(res.processed),
            "files_modified": len(res.changed),
            "files_skipped": len(res.skipped),
            "redactions_total": len(res.findings),
            "by_category": dict(_counts_by(res.findings, "label")),
            "by_group": dict(_counts_by(res.findings, "group")),
            "by_mechanism": dict(_counts_by(res.findings, "mechanism")),
        },
        "files_processed": sorted(res.processed),
        "files_modified": sorted(res.changed),
        "findings": [f.to_dict() for f in sorted(res.findings, key=lambda x: (x.rel_path, x.line, x.col, x.label))],
        "skipped": [s.to_dict() for s in sorted(res.skipped, key=lambda x: x.rel_path)],
        "pruned_dirs": sorted(set(res.pruned_dirs)),
        "warnings": list(res.warnings),
        "known_deliberate_over_redaction": list(DELIBERATE_OVER_REDACTIONS),
        "known_deliberate_non_redaction": list(DELIBERATE_UNDER_REDACTIONS),
        "residual_findings": [f.to_dict() for f in sorted(residual, key=lambda x: (x.rel_path, x.line, x.col, x.label))],
        "review_candidates": [r.to_dict() for r in sorted(review, key=lambda x: (x.rel_path, x.line, x.col, x.guess))],
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def render_residual_report(opts, out_root, residual, review, note):
    # type: (Options, Optional[str], List[Finding], List[ReviewCandidate], Optional[str]) -> str
    lines = []  # type: List[str]
    add = lines.append
    add("=" * 78)
    add("Residual scan of the SANITIZED output")
    add("=" * 78)
    add("output directory : {0}".format(os.path.abspath(out_root) if out_root else "<none>"))
    add("categories active: {0}".format(",".join(sorted(opts.groups))))
    add("")
    if note:
        add(note)
        add("")
    add("-" * 78)
    add("RESIDUAL FINDINGS  (must be empty; exit code 2 if not)")
    add("-" * 78)
    if not residual:
        add("(none -- clean)")
    else:
        for f in sorted(residual, key=lambda x: (x.rel_path, x.line, x.col)):
            add("  {0}  {1}".format(f.rel_path, f.format_line()))
    add("")
    add("-" * 78)
    add("REVIEW  (deliberately NOT redacted -- eyeball these spots by hand)")
    add("-" * 78)
    add("Location, length and a category guess only.  No content is shown.")
    add("Reasons a spot lands here:")
    add("  base64-below-threshold           : base64-ish run shorter than --base64-min")
    add("  high-entropy-under-protected-key : random-looking value under a never-redact key")
    add("  long-unquoted-scalar             : unusually long unquoted plain scalar")
    add("  inactive-category:<label>        : matched a category not enabled for this run")
    add("  content-addressed-exempt:<key>   : entropy heuristics stood down for a")
    add("                                     content-address key (commit/digest/image/...)")
    add("")
    if not review:
        add("(none)")
    else:
        for r in sorted(review, key=lambda x: (x.rel_path, x.line, x.col, x.guess)):
            add("  {0}:{1}:{2}  {3}  len={4}".format(r.rel_path, r.line, r.col, r.guess, r.length))
    add("")
    return "\n".join(lines) + "\n"


def write_mapping_file(path, allocator):
    # type: (str, PlaceholderAllocator) -> None
    payload = {
        "_WARNING": (
            "THIS FILE CONTAINS THE ORIGINAL SECRET VALUES. It is exactly as "
            "sensitive as the source repository. Store it like a password vault, "
            "never commit it, never share it, delete it when done."
        ),
        "tool_version": TOOL_VERSION,
        "mapping": dict(allocator.mapping()),
    }
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="\n") as fh:
        fh.write(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
        fh.write("\n")
    # Printed even under --quiet: this is a safety warning, not progress noise.
    banner = "!" * 78
    print("")
    print(banner)
    print("!! MAPPING FILE WRITTEN: {0}".format(os.path.abspath(path)))
    print("!! It holds {0} ORIGINAL SECRET VALUES IN CLEARTEXT.".format(len(allocator.mapping())))
    print("!! It is as sensitive as the customer repository itself.")
    print("!! Do not commit it, do not share it, delete it when you are done.")
    print(banner)
    print("")


# ---------------------------------------------------------------------------
# Commands.
# ---------------------------------------------------------------------------


def cmd_sanitize(opts):
    # type: (Options) -> int
    check_sanitize_paths(opts)
    in_dir = opts.in_dir
    out_dir = opts.out_dir
    assert in_dir is not None and out_dir is not None
    started_at = datetime.datetime.now().replace(microsecond=0).isoformat()
    quiet = opts.quiet

    if not quiet:
        print("{0} v{1}".format(TOOL_NAME, TOOL_VERSION))
        print("  input      : {0}".format(os.path.abspath(in_dir)))
        print("  output     : {0}".format(os.path.abspath(out_dir)))
        print("  categories : {0}".format(",".join(sorted(opts.groups))))
        print("  hashing input tree (sha256) ...")

    before = manifest_of(in_dir)

    if not opts.dry_run and not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    ctx = RunContext(opts.groups, opts.base64_min)
    report_dir = opts.report_dir
    assert report_dir is not None
    res = run_pass(in_dir, out_dir, opts, ctx)

    assert_sources_unchanged(in_dir, before, quiet)

    if opts.dry_run:
        residual = []  # type: List[Finding]
        review = []  # type: List[ReviewCandidate]
        note = "Dry run: no output tree was written, so no residual scan was possible."
    else:
        residual, review = residual_scan(out_dir, opts, [report_dir])
        note = None

    text_report = render_text_report(opts, "sanitize", in_dir, out_dir, res, started_at, len(before))
    json_report = render_json_report(
        opts, "sanitize", in_dir, out_dir, res, started_at, len(before), residual, review
    )
    residual_report = render_residual_report(opts, out_dir, residual, review, note)

    write_report_file(os.path.join(report_dir, "sanitization-report.txt"), text_report)
    write_report_file(os.path.join(report_dir, "sanitization-report.json"), json_report)
    write_report_file(os.path.join(report_dir, "residual-scan.txt"), residual_report)

    if opts.emit_mapping:
        write_mapping_file(opts.emit_mapping, ctx.allocator)

    print_console_summary(opts, res, residual, review, report_dir)
    return 2 if residual else 0


def cmd_scan_only(opts):
    # type: (Options) -> int
    check_scan_paths(opts)
    scan_dir = opts.scan_only
    assert scan_dir is not None
    started_at = datetime.datetime.now().replace(microsecond=0).isoformat()
    quiet = opts.quiet
    if not quiet:
        print("{0} v{1}  (scan-only: nothing is written into the corpus)".format(TOOL_NAME, TOOL_VERSION))
        print("  scanning   : {0}".format(os.path.abspath(scan_dir)))
        print("  categories : {0}".format(",".join(sorted(opts.groups))))
        print("  hashing tree (sha256) ...")

    before = manifest_of(scan_dir)
    ctx = RunContext(opts.groups, opts.base64_min)
    res = run_pass(scan_dir, None, opts, ctx)
    assert_sources_unchanged(scan_dir, before, quiet)

    report_dir = opts.report_dir
    assert report_dir is not None
    review = []  # type: List[ReviewCandidate]
    for rel in res.processed:
        path = os.path.join(scan_dir, *rel.split("/"))
        text, _bom, err = read_text_file(path)
        if text is not None:
            review.extend(find_review_candidates(text, rel, opts.groups, opts.base64_min))

    text_report = render_text_report(opts, "scan-only", scan_dir, None, res, started_at, len(before))
    json_report = render_json_report(
        opts, "scan-only", scan_dir, None, res, started_at, len(before), [], review
    )
    residual_report = render_residual_report(
        opts,
        None,
        [],
        review,
        "Scan-only mode: no output tree exists, so there is nothing to re-scan. "
        "The REVIEW section below refers to the SCANNED (still unsanitized) tree.",
    )
    write_report_file(os.path.join(report_dir, "sanitization-report.txt"), text_report)
    write_report_file(os.path.join(report_dir, "sanitization-report.json"), json_report)
    write_report_file(os.path.join(report_dir, "residual-scan.txt"), residual_report)

    print("")
    print("scan-only complete: {0} files scanned, {1} would-be redactions".format(len(res.processed), len(res.findings)))
    print("  report : {0}".format(os.path.join(os.path.abspath(report_dir), "sanitization-report.txt")))
    print("  json   : {0}".format(os.path.join(os.path.abspath(report_dir), "sanitization-report.json")))
    print("  review : {0}".format(os.path.join(os.path.abspath(report_dir), "residual-scan.txt")))
    return 0


def print_console_summary(opts, res, residual, review, report_dir):
    # type: (Options, PassResult, List[Finding], List[ReviewCandidate], str) -> None
    print("")
    print("-" * 60)
    if opts.dry_run:
        print("DRY RUN         : no sanitized files were written (reports only)")
    print("files processed : {0}".format(len(res.processed)))
    print("files modified  : {0}".format(len(res.changed)))
    print("files skipped   : {0}  (never copied to the output)".format(len(res.skipped)))
    print("redactions      : {0}".format(len(res.findings)))
    for label, count in _counts_by(res.findings, "label"):
        print("    {0:<26} {1}".format(label, count))
    print("warnings        : {0}".format(len(res.warnings)))
    print("review spots    : {0}  (see residual-scan.txt REVIEW section)".format(len(review)))
    if residual:
        print("")
        print("*** RESIDUAL FINDINGS IN OUTPUT: {0} -- DO NOT SHARE THE OUTPUT YET ***".format(len(residual)))
    else:
        print("residual scan   : clean")
    rd = os.path.abspath(report_dir)
    print("")
    print("reports:")
    print("  {0}".format(os.path.join(rd, "sanitization-report.txt")))
    print("  {0}".format(os.path.join(rd, "sanitization-report.json")))
    print("  {0}".format(os.path.join(rd, "residual-scan.txt")))
    print("-" * 60)


# ---------------------------------------------------------------------------
# Self-test.
# ---------------------------------------------------------------------------

# Planted secrets (must be absent from the output) and negatives (must survive
# byte-for-byte).  Kept as module-level literals so the operator can read what
# the test actually proves.
_ST_PEM_BODY_MARK = "MIIBOgIBAAJBAK7sanitizerSelfTestBodyLineOne1234567890abcdefGHIJK"
_ST_CERT_BODY_MARK = "MIIDdzCCAl+gAwIBAgIEAgAAuTANselfTestCertificateBody0987654321zyx"

# Content addresses: must survive byte-identical (precision, not recall).
_ST_GIT_SHA = "3f8a1c2d4e5f60718293a4b5c6d7e8f9a0b1c2d3"
_ST_IMAGE_DIGEST = "9f2c1a4b6d8e0f2a4c6e8b0d2f4a6c8e0b2d4f6a8c0e2b4d6f8a0c2e4b6d8f0a"
_ST_IMAGE_REF = "quay.io/acme/runner@sha256:" + _ST_IMAGE_DIGEST

_ST_SECRETS = [
    "hunter2SuperSecretValue",
    "Pa55w0rd-with-space-key",
    "clientSecretAbcdefghijklmnop123456",
    "AKIAIOSFODNN7EXAMPLE",
    "ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
    "xoxb-1234567890-abcdefghijKLMNOP",
    "AIzaSyD-1234567890abcdefghijklmnopqrstu",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk",
    "$2y$10$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0",
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDselfTestPublicKeyBlob123456",
    "d41d8cd98f00b204e9800998ecf8427e5f2b1c9a",
    "TG9uZ0Jhc2U2NEJsb2JGb3JLdWJlY29uZmlnVGVzdGluZ1B1cnBvc2VzT25seUFBQQ==",
    "supersecretuser:supersecretpass",
    "Sup3rS3cretEnvValue",
    "cliSecretValue12345",
    "BearerTokenInlineAuthValue123456",
    "contextSecretDefaultValue123",
    _ST_PEM_BODY_MARK,
    _ST_CERT_BODY_MARK,
]

_ST_IDENTITY = [
    "jane.doe+corp@customer-internal.example.com",
    "10.91.36.240",
    "bastion.customer-internal.corp",
    "00:1A:2B:3C:4D:5E",
    "FCH1234ABCD",
]

_ST_NEGATIVE_LINES = [
    "  - key: Provider",
    "  key-prefix: envs",
    "  credential_name: my-cred",
    "  secret-name: sec",
    "  secret-namespace: default",
    "  key_pair_name: my-keypair",
    "  public_key: my-public-key-name",
    "  admin_password_ref: '{{ .inputs[\"Admin Password\"] }}'",
    "  pattern: '[0-9a-f]{32}'",
    "  allowed-values: [alpha, beta, gamma]",
    "  tf-version: 1.5.7",
    "  local_bind: 127.0.0.1",
    "      type: password",
    "      sensitive: true",
    "      default: eu-west-1",
    "  commit: " + _ST_GIT_SHA,
    "  image: " + _ST_IMAGE_REF,
    "  chart-version: 1.2.3",
    "  path-in-archive: charts/app",
    "  validation-description: 'Empty or an IP in 10.0.0.0/24'",
    "        docker pull " + _ST_IMAGE_REF,
    "      ^[0-9a-f]{32}$",
    "        echo \"{{ .params.region }}\"",
]


def _self_test_corpus():
    # type: () -> Dict[str, str]
    """Return {relative_path: content} for the planted temp corpus."""
    bp = "\n".join(
        [
            "spec_version: 2",
            "description: planted corpus for sanitizer self-test",
            "inputs:",
            "  - admin_password: hunter2SuperSecretValue",
            "  - Admin Password:",
            "      type: password",
            "      sensitive: true",
            "      default: contextSecretDefaultValue123",
            "  - region:",
            "      type: string",
            "      default: eu-west-1",
            '  - "Administrator Password": "Pa55w0rd-with-space-key"',
            "  - client_secret: clientSecretAbcdefghijklmnop123456",
            "  - aws_access_key: AKIAIOSFODNN7EXAMPLE",
            "  - github_pat: ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
            "  - slack: xoxb-1234567890-abcdefghijKLMNOP",
            "  - gcp: AIzaSyD-1234567890abcdefghijklmnopqrstu",
            "  - jwt_input: eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            "  - hashed: $2y$10$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0",
            "  - authorized: ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDselfTestPublicKeyBlob123456",
            "  - hex_material: d41d8cd98f00b204e9800998ecf8427e5f2b1c9a",
            "  - kubeconfig_b64: TG9uZ0Jhc2U2NEJsb2JGb3JLdWJlY29uZmlnVGVzdGluZ1B1cnBvc2VzT25seUFBQQ==",
            "  - repo_url: https://supersecretuser:supersecretpass@git.customer-internal.corp/team/repo.git",
            "  # leftover token in a comment: ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
            "  - key: Provider",
            "  key-prefix: envs",
            "  credential_name: my-cred",
            "  secret-name: sec",
            "  secret-namespace: default",
            "  key_pair_name: my-keypair",
            "  public_key: my-public-key-name",
            "  admin_password_ref: '{{ .inputs[\"Admin Password\"] }}'",
            "  pattern: '[0-9a-f]{32}'",
            "  allowed-values: [alpha, beta, gamma]",
            "  tf-version: 1.5.7",
            "  local_bind: 127.0.0.1",
            # content addresses -- precision cases, must survive byte-identical
            "  commit: " + _ST_GIT_SHA,
            "  image: " + _ST_IMAGE_REF,
            "  chart-version: 1.2.3",
            "  path-in-archive: charts/app",
            "  validation-description: 'Empty or an IP in 10.0.0.0/24'",
            "  contact: jane.doe+corp@customer-internal.example.com",
            "  agent_host: 10.91.36.240",
            "  jump_host: bastion.customer-internal.corp",
            "  nic: 00:1A:2B:3C:4D:5E",
            "  serial: FCH1234ABCD",
            "  validation:",
            "    pattern: |",
            "      ^[0-9a-f]{32}$",
            "grains:",
            "  setup:",
            "    kind: shell",
            "    spec:",
            "      commands: |",
            '        curl -H "Authorization: Bearer BearerTokenInlineAuthValue123456" https://api.example.com/v1',
            "        export DB_PASSWORD=Sup3rS3cretEnvValue",
            "        helm upgrade app ./chart --password cliSecretValue12345",
            "        docker pull " + _ST_IMAGE_REF,
            '        echo "{{ .params.region }}"',
            "      private_key: |",
            "        -----BEGIN RSA PRIVATE KEY-----",
            "        " + _ST_PEM_BODY_MARK,
            "        AnotherBodyLineOfTheSelfTestPrivateKeyMaterial0123456789abcdefg",
            "        -----END RSA PRIVATE KEY-----",
            "      ca_cert: |",
            "        -----BEGIN CERTIFICATE-----",
            "        " + _ST_CERT_BODY_MARK,
            "        -----END CERTIFICATE-----",
            "",
        ]
    )
    crlf = "\r\n".join(
        [
            "# crlf file with a BOM",
            "inputs:",
            "  - password: hunter2SuperSecretValue",
            "  - key: Provider",
            "",
        ]
    )
    broken = "\n".join(
        [
            "this: is: not: valid: yaml",
            "  - stray",
            "\ttab_indented_password: hunter2SuperSecretValue",
            "unterminated: 'quote",
            "",
        ]
    )
    return {
        "blueprints/planted.yaml": bp,
        "blueprints/nested/crlf-bom.yaml": UTF8_BOM + crlf,
        "blueprints/nested/broken.yaml": broken,
        "notes/readme.md": "password: shouldNotBeTouchedBecauseExtensionIsExcluded\n",
    }


def _st_write_corpus(root, files):
    # type: (str, Dict[str, str]) -> None
    for rel in sorted(files):
        path = os.path.join(root, *rel.split("/"))
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "wb") as fh:
            fh.write(files[rel].encode("utf-8", "surrogateescape"))


def _st_read_all(root, exts=(".yaml", ".yml")):
    # type: (str, Sequence[str]) -> Dict[str, str]
    out = {}  # type: Dict[str, str]
    for path in iter_files(root):
        if os.path.splitext(path)[1].lower() not in exts:
            continue
        text, _bom, err = read_text_file(path)
        out[rel_posix(path, root)] = text if text is not None else "<undecodable>"
    return out


def _st_options(in_dir, out_dir, groups):
    # type: (str, str, Sequence[str]) -> Options
    opts = Options()
    opts.in_dir = in_dir
    opts.out_dir = out_dir
    opts.groups = set(groups)
    opts.report_dir = os.path.join(out_dir, "_sanitization-report")
    opts.quiet = True
    return opts


def _st_run(opts):
    # type: (Options) -> int
    """Run a sanitize pass with its console chatter swallowed."""
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        return cmd_sanitize(opts)


def cmd_self_test():
    # type: () -> int
    tmp_root = tempfile.mkdtemp(prefix="sanitize-selftest-")
    cases = []  # type: List[Tuple[str, bool, str]]

    def check(name, ok, detail=""):
        cases.append((name, bool(ok), detail))

    try:
        src = os.path.join(tmp_root, "src")
        out_default = os.path.join(tmp_root, "out-default")
        out_all = os.path.join(tmp_root, "out-all")
        out_repeat = os.path.join(tmp_root, "out-repeat")
        files = _self_test_corpus()
        _st_write_corpus(src, files)
        before = manifest_of(src)

        # ---- run A: default categories --------------------------------
        rc_a = _st_run(_st_options(src, out_default, DEFAULT_GROUPS))
        check("run(default categories) exits 0 (no residual findings)", rc_a == 0, "rc={0}".format(rc_a))
        out_a = _st_read_all(out_default)
        blob_a = "\n".join(out_a[k] for k in sorted(out_a))

        for secret in _ST_SECRETS:
            check("secret redacted: " + _st_short(secret), secret not in blob_a)

        # negatives must survive byte-for-byte
        planted_out = out_a.get("blueprints/planted.yaml", "")
        planted_lines = [c for c, _e in split_lines_keepends(planted_out)]
        for neg in _ST_NEGATIVE_LINES:
            check("negative preserved: " + _st_short(neg), neg in planted_lines)
        check(
            "liquid span preserved in command body",
            '{{ .params.region }}' in planted_out and '{{ .inputs["Admin Password"] }}' in planted_out,
        )
        check(
            "identity values kept when category is off",
            all(v in blob_a for v in _ST_IDENTITY),
        )
        check(
            "non-included extension not copied to output",
            not os.path.exists(os.path.join(out_default, "notes", "readme.md")),
        )
        crlf_out = out_a.get("blueprints/nested/crlf-bom.yaml", "")
        with open(os.path.join(out_default, "blueprints", "nested", "crlf-bom.yaml"), "rb") as fh:
            crlf_bytes = fh.read()
        check(
            "CRLF preserved (no bare LF introduced)",
            b"\r\n" in crlf_bytes and b"\n" not in crlf_bytes.replace(b"\r\n", b""),
        )
        check("BOM round-tripped", crlf_bytes.startswith(b"\xef\xbb\xbf"))
        check("CRLF file secret redacted", "hunter2SuperSecretValue" not in crlf_out)
        check("unparseable file still processed", "blueprints/nested/broken.yaml" in out_a)
        check(
            "unparseable file secret redacted",
            "hunter2SuperSecretValue" not in out_a.get("blueprints/nested/broken.yaml", "x"),
        )
        for rel in sorted(files):
            if rel.endswith((".yaml", ".yml")):
                src_lines = len(split_lines_keepends(files[rel].lstrip(UTF8_BOM)))
                out_lines = len(split_lines_keepends(out_a.get(rel, "")))
                check("line count preserved: " + rel, src_lines == out_lines, "{0} vs {1}".format(src_lines, out_lines))

        residual_txt = _st_report(out_default, "residual-scan.txt")
        check("residual scan clean", "(none -- clean)" in residual_txt)
        report_txt = _st_report(out_default, "sanitization-report.txt")
        check("report mentions the sha256 guarantee", "SOURCES NEVER MODIFIED" in report_txt)
        check(
            "report leaks no original value",
            not any(s in report_txt for s in _ST_SECRETS),
        )

        # ---- run B: every category ------------------------------------
        rc_b = _st_run(_st_options(src, out_all, ALL_GROUPS))
        check("run(all categories) exits 0", rc_b == 0, "rc={0}".format(rc_b))
        out_b = _st_read_all(out_all)
        blob_b = "\n".join(out_b[k] for k in sorted(out_b))
        for value in _ST_IDENTITY:
            check("identity redacted when opted in: " + _st_short(value), value not in blob_b)
        for secret in _ST_SECRETS:
            check("secret still redacted (all cats): " + _st_short(secret), secret not in blob_b)
        planted_b_text = out_b.get("blueprints/planted.yaml", "")
        planted_b = [c for c, _e in split_lines_keepends(planted_b_text)]
        check("pattern value untouched with ip category on", "  pattern: '[0-9a-f]{32}'" in planted_b)
        check("loopback address kept with ip category on", "  local_bind: 127.0.0.1" in planted_b)
        # precision fixes must hold with every category enabled too
        check("git SHA kept with all categories on", "  commit: " + _ST_GIT_SHA in planted_b)
        check(
            "validation-description kept verbatim with ip category on",
            "  validation-description: 'Empty or an IP in 10.0.0.0/24'" in planted_b,
        )
        check(
            "image digest kept with all categories on",
            planted_b_text.count("@sha256:" + _ST_IMAGE_DIGEST) == 2,
        )

        # ---- run C: determinism ---------------------------------------
        rc_c = _st_run(_st_options(src, out_repeat, DEFAULT_GROUPS))
        out_c = _st_read_all(out_repeat)
        check("repeat run exits 0", rc_c == 0, "rc={0}".format(rc_c))
        check("output is deterministic across runs", out_a == out_c)

        # ---- safety refusals ------------------------------------------
        check("refuses out == in", _st_refuses(_st_options(src, src, DEFAULT_GROUPS)))
        check(
            "refuses out inside in",
            _st_refuses(_st_options(src, os.path.join(src, "nested-out"), DEFAULT_GROUPS)),
        )
        check(
            "refuses in inside out",
            _st_refuses(_st_options(os.path.join(src, "blueprints"), src, DEFAULT_GROUPS)),
        )
        nonempty = _st_options(src, out_default, DEFAULT_GROUPS)
        check("refuses non-empty out without --force", _st_refuses(nonempty))

        # ---- sources unchanged ----------------------------------------
        after = manifest_of(src)
        check("input tree byte-identical after all runs", before == after)

    finally:
        report = _st_render(cases)
        print(report)
        shutil.rmtree(tmp_root, ignore_errors=True)

    failed = [c for c in cases if not c[1]]
    return 2 if failed else 0


def _st_short(text, width=46):
    # type: (str, int) -> str
    one = text.replace("\n", " ")
    return one if len(one) <= width else one[: width - 3] + "..."


def _st_report(out_dir, name):
    # type: (str, str) -> str
    path = os.path.join(out_dir, "_sanitization-report", name)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _st_refuses(opts):
    # type: (Options) -> bool
    try:
        check_sanitize_paths(opts)
    except SafetyRefusal:
        return True
    return False


def _st_render(cases):
    # type: (Sequence[Tuple[str, bool, str]]) -> str
    lines = []  # type: List[str]
    lines.append("")
    lines.append("=" * 78)
    lines.append("SELF-TEST RESULTS -- {0} v{1}".format(TOOL_NAME, TOOL_VERSION))
    lines.append("=" * 78)
    for name, ok, detail in cases:
        lines.append("  [{0}] {1}{2}".format("PASS" if ok else "FAIL", name, ("  <- " + detail) if detail and not ok else ""))
    passed = sum(1 for c in cases if c[1])
    lines.append("-" * 78)
    lines.append("  {0} passed, {1} failed, {2} total".format(passed, len(cases) - passed, len(cases)))
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------


def main(argv=None):
    # type: (Optional[Sequence[str]]) -> int
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            if args.in_dir or args.out_dir or args.scan_only:
                raise SafetyRefusal("--self-test cannot be combined with --in/--out/--scan-only")
            return cmd_self_test()
        opts = options_from_args(args)
        if opts.scan_only:
            if opts.in_dir or opts.out_dir:
                raise SafetyRefusal("--scan-only cannot be combined with --in/--out")
            return cmd_scan_only(opts)
        if not opts.in_dir or not opts.out_dir:
            parser.print_usage(sys.stderr)
            raise SafetyRefusal("both --in and --out are required (or use --scan-only / --self-test)")
        return cmd_sanitize(opts)
    except SafetyRefusal as exc:
        sys.stderr.write("\nREFUSED: {0}\n".format(exc))
        return 3
    except KeyboardInterrupt:
        sys.stderr.write("\ninterrupted\n")
        return 3
    except Exception:  # noqa: BLE001 - reported as exit code 4 with traceback
        sys.stderr.write("\nUNEXPECTED ERROR:\n")
        traceback.print_exc()
        return 4


if __name__ == "__main__":
    sys.exit(main())
