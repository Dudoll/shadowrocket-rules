#!/usr/bin/env python3
"""Convert Loyalsoldier Clash payload lists into Surge/Shadowrocket rulesets.

The source files remain Clash YAML under clash-rules/.  The generated files
contain rule bodies only (no policy column); the caller's RULE-SET policy is
applied by Shadowrocket.
"""
from __future__ import annotations

import argparse
import ast
import ipaddress
import os
import re
import tempfile
from pathlib import Path

FILES = ("icloud", "private", "apple", "cncidr", "proxy", "direct", "reject")
ITEM_RE = re.compile(r"^\s*-\s*(?P<value>.+?)\s*(?:#.*)?$")
RULE_RE = re.compile(r"^(?:DOMAIN|DOMAIN-SUFFIX|DOMAIN-KEYWORD|IP-CIDR|IP-CIDR6|IP-ASN|GEOIP),")


def _value(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    if raw[:1] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            return None
        return parsed if isinstance(parsed, str) else None
    return raw


def _rule(value: str) -> str | None:
    value = value.strip()
    if not value or value.startswith("#"):
        return None
    if RULE_RE.match(value):
        return value.split(",", 2)[0] + "," + value.split(",", 2)[1]
    if value.startswith("+."):
        domain = value[2:].strip().rstrip(".")
        return f"DOMAIN-SUFFIX,{domain}" if domain else None
    if value.startswith("*."):
        domain = value[2:].strip().rstrip(".")
        return f"DOMAIN-SUFFIX,{domain}" if domain else None
    if value.startswith("||"):
        domain = value[2:].lstrip(".").rstrip("|").rstrip(".")
        return f"DOMAIN-SUFFIX,{domain}" if domain else None
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        network = None
    if network is not None:
        kind = "IP-CIDR6" if network.version == 6 else "IP-CIDR"
        return f"{kind},{network.with_prefixlen}"
    if any(ch.isspace() for ch in value) or "," in value:
        return None
    domain = value.rstrip(".")
    if not domain or domain.startswith("."):
        return None
    return f"DOMAIN,{domain}"


def convert(path: Path) -> list[str]:
    in_payload = False
    rules: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.strip() == "payload:":
            in_payload = True
            continue
        if not in_payload:
            continue
        match = ITEM_RE.match(raw)
        if not match:
            continue
        value = _value(match.group("value"))
        if value is None:
            continue
        rule = _rule(value)
        if rule and rule not in seen:
            seen.add(rule)
            rules.append(rule)
    if len(rules) < 1:
        raise ValueError(f"no rules parsed from {path}")
    return rules


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--destination-dir", type=Path, required=True)
    args = parser.parse_args()
    results: list[str] = []
    for name in FILES:
        source = args.source_dir / f"{name}.txt"
        destination = args.destination_dir / f"{name}.txt"
        rules = convert(source)
        atomic_write(destination, "\n".join(rules) + "\n")
        results.append(f"{name}={len(rules)}")
    print("shadowrocket rules generated: " + " ".join(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
