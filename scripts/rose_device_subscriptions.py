#!/usr/bin/env python3
"""Generate and reconcile private device-distinct proxy subscriptions.

Secrets are read from a root-only env file and are never logged.  The module is
also importable so transformations can be tested without live credentials.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

try:
    import yaml
except ModuleNotFoundError:  # Reconciliation on a minimal Xray host does not need PyYAML.
    yaml = None

DEFAULT_ENV = Path("/etc/rose-tailored-subscriptions.env")
DEFAULT_MASTER_ROOT = Path("/etc/v2ray-agent/subscribe")
DEFAULT_PUBLISH_ROOT = Path("/var/www/rose-rules")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
DEVICE_KEYS = {
    "mobile": ("MOBILE_TOKEN", "MOBILE_UUID"),
    "computer": ("COMPUTER_TOKEN", "COMPUTER_UUID"),
    "tv": ("TV_TOKEN", "TV_UUID"),
}
TV_REQUIRED = (
    "DMIT_CF_WS_443",
    "BAND_CF_WS_443",
    "DMIT_REALITY_IPv4_443",
    "BAND_REALITY_IPv4_443",
    "BAND_REALITY_IPv6_443",
    "DMIT_TLS_IPv6_443",
    "DMIT_REALITY_IPv4_8443",
)


def _valid_uuid(value: str) -> str:
    parsed = uuid.UUID(value)
    if str(parsed) != value.lower():
        raise RuntimeError("UUID must use canonical form")
    return str(parsed)


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RuntimeError("invalid env line")
        key, value = line.split("=", 1)
        key = key.strip()
        if key in values:
            raise RuntimeError(f"duplicate env key: {key}")
        values[key] = value.strip()
    return values


def load_device_env(path: Path = DEFAULT_ENV) -> dict[str, str]:
    values = _read_env(path)
    required = {"MASTER_TOKEN"}
    for token_key, uuid_key in DEVICE_KEYS.values():
        required.update((token_key, uuid_key))
    missing = sorted(required - values.keys())
    if missing:
        raise RuntimeError(f"missing env keys: {missing}")
    for key in ("MASTER_TOKEN", "XHTTP_TOKEN", "BAND_XHTTP_TOKEN"):
        if key in values and not TOKEN_RE.fullmatch(values[key]):
            raise RuntimeError(f"{key} must be 16-128 URL-safe characters")
    tokens = [values[token_key] for token_key, _ in DEVICE_KEYS.values()]
    identities = [values[uuid_key] for _, uuid_key in DEVICE_KEYS.values()]
    if any(not TOKEN_RE.fullmatch(token) for token in tokens):
        raise RuntimeError("device tokens must be 16-128 URL-safe characters")
    if len(set(tokens)) != len(tokens):
        raise RuntimeError("device tokens must be distinct")
    canonical = [_valid_uuid(value) for value in identities]
    if len(set(canonical)) != len(canonical):
        raise RuntimeError("device UUIDs must be distinct")
    return values


def load_reconcile_env(path: Path = DEFAULT_ENV) -> dict[str, str]:
    values = _read_env(path)
    keys = ("LEGACY_UUID", "MOBILE_UUID", "COMPUTER_UUID", "TV_UUID")
    missing = sorted(set(keys) - values.keys())
    if missing:
        raise RuntimeError(f"missing env keys: {missing}")
    identities = {key: _valid_uuid(values[key]) for key in keys}
    if len(set(identities.values())) != len(identities):
        raise RuntimeError("device UUIDs must be distinct")
    return identities


def decode_subscription(path: Path) -> list[str]:
    try:
        raw = "".join(path.read_text().split())
    except OSError:
        raise RuntimeError("unable to read private subscription") from None
    try:
        normalized = raw + "=" * (-len(raw) % 4)
        decoded = base64.b64decode(normalized, validate=True).decode()
    except Exception as exc:
        raise RuntimeError("invalid Base64 subscription") from exc
    links = [line.strip() for line in decoded.splitlines() if line.strip()]
    if not links:
        raise RuntimeError("subscription contains no links")
    return links


def node_name(link: str) -> str:
    value = urlsplit(link)
    if value.scheme != "vless" or not value.fragment:
        raise RuntimeError("only named VLESS links are supported")
    return unquote(value.fragment)


def rewrite_vless_link(link: str, device_uuid: str, prefix: str) -> str:
    device_uuid = _valid_uuid(device_uuid)
    parsed = urlsplit(link)
    if parsed.scheme != "vless" or not parsed.hostname or not parsed.port:
        raise RuntimeError("invalid VLESS link")
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    netloc = f"{device_uuid}@{hostname}:{parsed.port}"
    fragment = quote(f"{prefix}_{node_name(link)}", safe="")
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, fragment))


def build_mobile_subscription(links: list[str], device_uuid: str) -> str:
    seen: set[str] = set()
    rewritten: list[str] = []
    for link in links:
        name = node_name(link)
        if name in seen:
            raise RuntimeError(f"duplicate mobile node name: {name}")
        seen.add(name)
        rewritten.append(rewrite_vless_link(link, device_uuid, "MOBILE"))
    if not rewritten:
        raise RuntimeError("mobile subscription has no nodes")
    payload = "\n".join(rewritten) + "\n"
    return base64.b64encode(payload.encode()).decode() + "\n"


def _rewrite_proxy(proxy: dict, device_uuid: str, prefix: str) -> dict:
    if not proxy.get("name") or "uuid" not in proxy:
        raise RuntimeError("Clash proxy lacks name or uuid")
    rewritten = copy.deepcopy(proxy)
    rewritten["name"] = f"{prefix}_{proxy['name']}"
    rewritten["uuid"] = _valid_uuid(device_uuid)
    return rewritten


def _base_clash_profile(proxies: list[dict]) -> dict:
    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "warning",
        "ipv6": True,
        "proxies": proxies,
    }


def build_computer_profile(proxies: list[dict], device_uuid: str) -> dict:
    rewritten = [_rewrite_proxy(proxy, device_uuid, "COMPUTER") for proxy in proxies]
    names = [proxy["name"] for proxy in rewritten]
    if len(names) != len(set(names)) or not names:
        raise RuntimeError("computer proxy names must be unique and non-empty")
    required = {
        "COMPUTER_DMIT_CF_WS_443",
        "COMPUTER_BAND_CF_WS_443",
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_BAND_REALITY_IPv4_443",
        "COMPUTER_BAND_REALITY_IPv6_443",
        "COMPUTER_DMIT_TLS_IPv6_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
    }
    missing = sorted(required - set(names))
    if missing:
        raise RuntimeError(f"computer nodes missing from master: {missing}")
    direct = [
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
        "COMPUTER_BAND_REALITY_IPv4_443",
    ]
    cdn = ["COMPUTER_BAND_CF_WS_443", "COMPUTER_DMIT_CF_WS_443"]
    ai = [
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
        "COMPUTER_DMIT_CF_WS_443",
    ]
    social = [
        "COMPUTER_BAND_REALITY_IPv4_443",
        "COMPUTER_BAND_CF_WS_443",
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_CF_WS_443",
    ]
    video = [
        "COMPUTER_BAND_CF_WS_443",
        "COMPUTER_DMIT_CF_WS_443",
        "COMPUTER_BAND_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
    ]
    default = [
        "COMPUTER_BAND_REALITY_IPv4_443",
        "COMPUTER_BAND_CF_WS_443",
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
        "COMPUTER_DMIT_CF_WS_443",
    ]
    test_url = "https://www.gstatic.com/generate_204"

    def health_group(name: str, group_type: str, members: list[str], tolerance: int | None = None) -> dict:
        group = {
            "name": name,
            "type": group_type,
            "proxies": members,
            "url": test_url,
            "interval": 120,
            "lazy": False,
            "max-failed-times": 2,
        }
        if tolerance is not None:
            group["tolerance"] = tolerance
        return group

    profile = _base_clash_profile(rewritten)
    profile["proxy-groups"] = [
        health_group("COMPUTER_DIRECT", "url-test", direct, tolerance=50),
        health_group("COMPUTER_CDN", "url-test", cdn, tolerance=50),
        health_group("COMPUTER_AI", "fallback", ai),
        health_group("COMPUTER_SOCIAL", "fallback", social),
        health_group("COMPUTER_VIDEO", "fallback", video),
        health_group("COMPUTER_DEFAULT", "fallback", default),
        {"name": "PROXY", "type": "select", "proxies": ["COMPUTER_DEFAULT", "COMPUTER_AI", "COMPUTER_SOCIAL", "COMPUTER_VIDEO", "COMPUTER_DIRECT", "COMPUTER_CDN", *names, "DIRECT"]},
    ]
    ai_domains = ("chatgpt.com", "chat.com", "openai.com", "sora.com", "oaistatic.com", "oaiusercontent.com", "anthropic.com", "claude.ai", "perplexity.ai", "grok.com", "x.ai", "plasma.to")
    social_domains = ("x.com", "twitter.com", "t.co", "twimg.com", "instagram.com", "cdninstagram.com", "threads.net", "telegram.org", "telegram.me", "t.me", "telesco.pe")
    video_domains = ("youtube.com", "youtu.be", "googlevideo.com", "ytimg.com", "ggpht.com", "gvt1.com", "gvt2.com")
    profile["rules"] = [
        *(f"DOMAIN-SUFFIX,{domain},COMPUTER_AI" for domain in ai_domains),
        *(f"DOMAIN-SUFFIX,{domain},COMPUTER_SOCIAL" for domain in social_domains),
        *(f"DOMAIN-SUFFIX,{domain},COMPUTER_VIDEO" for domain in video_domains),
        "GEOIP,CN,DIRECT",
        "MATCH,PROXY",
    ]
    return profile


def build_tv_profile(proxies: list[dict], device_uuid: str) -> dict:
    by_name = {str(proxy.get("name")): proxy for proxy in proxies}
    missing = [name for name in TV_REQUIRED if name not in by_name]
    if missing:
        raise RuntimeError(f"TV nodes missing from master: {missing}")
    rewritten = [_rewrite_proxy(by_name[name], device_uuid, "TV") for name in TV_REQUIRED]
    cdn = ["TV_DMIT_CF_WS_443", "TV_BAND_CF_WS_443"]
    direct = [
        "TV_DMIT_REALITY_IPv4_443",
        "TV_BAND_REALITY_IPv4_443",
        "TV_BAND_REALITY_IPv6_443",
        "TV_DMIT_TLS_IPv6_443",
        "TV_DMIT_REALITY_IPv4_8443",
    ]
    profile = _base_clash_profile(rewritten)
    profile["allow-lan"] = True
    test_url = "https://www.gstatic.com/generate_204"
    profile["proxy-groups"] = [
        {"name": "TV_CDN", "type": "url-test", "proxies": cdn, "url": test_url, "interval": 300},
        {"name": "TV_DIRECT", "type": "url-test", "proxies": direct, "url": test_url, "interval": 300},
        {"name": "TV_POLICY", "type": "fallback", "proxies": ["TV_CDN", "TV_DIRECT"], "url": test_url, "interval": 180},
        {"name": "PROXY", "type": "select", "proxies": ["TV_POLICY", "TV_CDN", "TV_DIRECT", "DIRECT"]},
    ]
    profile["rules"] = [
        "DOMAIN-SUFFIX,youtube.com,TV_POLICY",
        "DOMAIN-SUFFIX,googlevideo.com,TV_POLICY",
        "DOMAIN-SUFFIX,netflix.com,TV_POLICY",
        "GEOIP,CN,DIRECT",
        "MATCH,PROXY",
    ]
    return profile


def atomic_write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o755)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def publish_outputs(root: Path, outputs: dict[tuple[str, str, str], str]) -> None:
    allowed = {
        ("mobile", "default"),
        ("computer", "clashMetaProfiles"),
        ("tv", "clashMetaProfiles"),
    }
    current: set[str] = set()
    for device, format_name, token in outputs:
        if (device, format_name) not in allowed or not TOKEN_RE.fullmatch(token):
            raise RuntimeError("invalid publication path")
        current.add(f"split/{device}/{format_name}/{token}")

    # Parse and validate all manifest state before making any public change.
    manifest = root / ".device-publications.json"
    previous: set[str] = set()
    if manifest.exists():
        try:
            loaded = json.loads(manifest.read_text())
        except (OSError, json.JSONDecodeError):
            raise RuntimeError("invalid device publication manifest") from None
        if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
            raise RuntimeError("invalid device publication manifest")
        previous = set(loaded)
    for relative in previous:
        parts = Path(relative).parts
        if len(parts) != 4 or parts[0] != "split" or (parts[1], parts[2]) not in allowed or not TOKEN_RE.fullmatch(parts[3]):
            raise RuntimeError("invalid managed publication path")

    for (device, format_name, token), body in outputs.items():
        relative = f"split/{device}/{format_name}/{token}"
        try:
            directory = root
            for part in Path(relative).parent.parts:
                directory = directory / part
                directory.mkdir(exist_ok=True)
                os.chmod(directory, 0o755)
            atomic_write(root / relative, body)
        except OSError:
            raise RuntimeError("unable to publish device subscription") from None
    for relative in previous - current:
        try:
            (root / relative).unlink(missing_ok=True)
        except OSError:
            raise RuntimeError("unable to revoke managed device subscription") from None
    atomic_write(manifest, json.dumps(sorted(current), indent=2) + "\n", mode=0o600)


def reconcile_vless_clients(config: dict, identities: dict[str, str], legacy_uuid: str) -> bool:
    canonical = {email: _valid_uuid(value) for email, value in identities.items()}
    legacy_uuid = _valid_uuid(legacy_uuid)
    if len(set(canonical.values())) != len(canonical):
        raise RuntimeError("device UUIDs must be distinct")
    changed = False
    inbounds = [inbound for inbound in config.get("inbounds", []) if inbound.get("protocol") == "vless"]
    if not inbounds:
        raise RuntimeError("no VLESS inbounds found")
    for inbound in inbounds:
        settings = inbound.setdefault("settings", {})
        clients = settings.get("clients")
        if not isinstance(clients, list) or not clients:
            raise RuntimeError(f"VLESS inbound has no base client: {inbound.get('tag')}")
        ids = [str(client.get("id") or "") for client in clients]
        emails = [str(client.get("email")) for client in clients if client.get("email")]
        if "" in ids:
            raise RuntimeError(f"client id missing on {inbound.get('tag')}")
        if len(ids) != len(set(ids)):
            raise RuntimeError(f"duplicate client id on {inbound.get('tag')}")
        if len(emails) != len(set(emails)):
            raise RuntimeError(f"duplicate client email on {inbound.get('tag')}")
        by_id = {str(client["id"]): client for client in clients}
        by_email = {str(client["email"]): client for client in clients if client.get("email")}
        if legacy_uuid not in by_id:
            raise RuntimeError(f"legacy client missing on {inbound.get('tag')}")
        template = by_id[legacy_uuid]
        for email, identity in canonical.items():
            existing_id = by_id.get(identity)
            existing_email = by_email.get(email)
            if existing_id and existing_id.get("email") != email:
                raise RuntimeError(f"device UUID collision on {inbound.get('tag')}")
            if existing_email and existing_email.get("id") != identity:
                raise RuntimeError(f"device email collision on {inbound.get('tag')}")
            if existing_id:
                continue
            device_client = {key: copy.deepcopy(value) for key, value in template.items() if key not in {"id", "email"}}
            device_client.update({"id": identity, "email": email})
            clients.append(device_client)
            by_id[identity] = device_client
            by_email[email] = device_client
            changed = True
    return changed


def generate_outputs(env: dict[str, str], master_root: Path) -> dict[tuple[str, str, str], str]:
    if yaml is None:
        raise RuntimeError("PyYAML is required for subscription generation")
    master_token = env["MASTER_TOKEN"]
    links = decode_subscription(master_root / "default" / master_token)
    for optional in ("XHTTP_TOKEN", "BAND_XHTTP_TOKEN"):
        token = env.get(optional)
        if token and (master_root / "default" / token).exists():
            links.extend(decode_subscription(master_root / "default" / token))
    try:
        clash_text = (master_root / "clashMeta" / master_token).read_text()
    except OSError:
        raise RuntimeError("unable to read private Clash subscription") from None
    try:
        clash = yaml.safe_load(clash_text)
    except yaml.YAMLError:
        raise RuntimeError("invalid private Clash subscription") from None
    proxies = clash.get("proxies") or []
    if not proxies:
        raise RuntimeError("master Clash provider has no proxies")
    return {
        ("mobile", "default", env["MOBILE_TOKEN"]): build_mobile_subscription(links, env["MOBILE_UUID"]),
        ("computer", "clashMetaProfiles", env["COMPUTER_TOKEN"]): yaml.safe_dump(
            build_computer_profile(proxies, env["COMPUTER_UUID"]), allow_unicode=True, sort_keys=False, width=1000
        ),
        ("tv", "clashMetaProfiles", env["TV_TOKEN"]): yaml.safe_dump(
            build_tv_profile(proxies, env["TV_UUID"]), allow_unicode=True, sort_keys=False, width=1000
        ),
    }


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _write_json(path: Path, data: dict) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", mode=0o600)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "reconcile"))
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--master-root", type=Path, default=DEFAULT_MASTER_ROOT)
    parser.add_argument("--publish-root", type=Path, default=DEFAULT_PUBLISH_ROOT)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.command == "generate":
        env = load_device_env(args.env)
        outputs = generate_outputs(env, args.master_root)
        publish_outputs(args.publish_root, outputs)
        print("generated device subscriptions: mobile, computer, tv")
        return 0
    if args.config is None:
        parser.error("reconcile requires --config")
    env = load_reconcile_env(args.env)
    config = _load_json(args.config)
    identities = {
        "device-mobile": env["MOBILE_UUID"],
        "device-computer": env["COMPUTER_UUID"],
        "device-tv": env["TV_UUID"],
    }
    changed = reconcile_vless_clients(config, identities, env["LEGACY_UUID"])
    if changed and args.apply:
        _write_json(args.config, config)
    print(f"device client reconciliation: {'changes-needed' if changed else 'unchanged'} mode={'apply' if args.apply else 'check'}")
    return 2 if changed and not args.apply else 0


if __name__ == "__main__":
    raise SystemExit(main())
