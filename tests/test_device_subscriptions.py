from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import traceback
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
import yaml

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "rose_device_subscriptions.py"
spec = importlib.util.spec_from_file_location("rose_device_subscriptions", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

LEGACY_UUID = "11111111-1111-4111-8111-111111111111"
MOBILE_UUID = "22222222-2222-4222-8222-222222222222"
COMPUTER_UUID = "33333333-3333-4333-8333-333333333333"
TV_UUID = "44444444-4444-4444-8444-444444444444"


def link(name: str, host: str = "node.example.com") -> str:
    return (
        f"vless://{LEGACY_UUID}@{host}:443?encryption=none&security=reality&"
        f"sni=www.example.com&fp=chrome&pbk=public-key&sid=abcd&flow=xtls-rprx-vision"
        f"&type=tcp#{name}"
    )


def decode_links(text: str) -> list[str]:
    return base64.b64decode(text.strip() + "===").decode().splitlines()


def clash_proxy(name: str) -> dict:
    return {
        "name": name,
        "type": "vless",
        "server": "node.example.com",
        "port": 443,
        "uuid": LEGACY_UUID,
        "network": "tcp",
        "tls": True,
        "servername": "www.example.com",
        "reality-opts": {"public-key": "public-key", "short-id": "abcd"},
        "client-fingerprint": "chrome",
    }


def test_mobile_base64_rewrites_identity_and_prefix_only() -> None:
    original = [link("BAND_REALITY_IPv4_443"), link("DMIT_REALITY_IPv4_443", "dmit.example.com")]

    encoded = module.build_mobile_subscription(original, MOBILE_UUID)
    rewritten = decode_links(encoded)

    assert len(rewritten) == 2
    for before, after in zip(original, rewritten):
        b, a = urlsplit(before), urlsplit(after)
        assert a.username == MOBILE_UUID
        assert a.hostname == b.hostname
        assert a.port == b.port
        assert parse_qs(a.query) == parse_qs(b.query)
        assert unquote(a.fragment).startswith("MOBILE_")
        assert LEGACY_UUID not in after


def test_mobile_generation_rejects_duplicate_names_and_malformed_base64(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="duplicate mobile node name"):
        module.build_mobile_subscription([link("DUPLICATE"), link("DUPLICATE", "other.example.com")], MOBILE_UUID)

    secret_token = "secret-bearer-token-123456"
    malformed = tmp_path / secret_token
    malformed.write_text("not valid base64 !!!")
    with pytest.raises(RuntimeError, match="invalid Base64 subscription") as exc:
        module.decode_subscription(malformed)
    rendered = "".join(traceback.format_exception(type(exc.value), exc.value, exc.value.__traceback__))
    assert secret_token not in rendered

    missing = tmp_path / "missing-secret-token-123456"
    with pytest.raises(RuntimeError, match="unable to read private subscription") as exc:
        module.decode_subscription(missing)
    rendered = "".join(traceback.format_exception(type(exc.value), exc.value, exc.value.__traceback__))
    assert missing.name not in rendered


def test_computer_profile_has_distinct_identity_and_valid_groups() -> None:
    names = [
        "DMIT_CF_WS_443",
        "BAND_CF_WS_443",
        "DMIT_REALITY_IPv4_443",
        "BAND_REALITY_IPv4_443",
        "BAND_REALITY_IPv6_443",
        "DMIT_TLS_IPv6_443",
        "DMIT_REALITY_IPv4_8443",
    ]
    proxies = [clash_proxy(name) for name in names]

    profile = module.build_computer_profile(proxies, COMPUTER_UUID)

    assert [p["name"] for p in profile["proxies"]] == [f"COMPUTER_{name}" for name in names]
    assert {p["uuid"] for p in profile["proxies"]} == {COMPUTER_UUID}
    groups = {group["name"]: group for group in profile["proxy-groups"]}
    assert groups["COMPUTER_DIRECT"]["proxies"] == [
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
        "COMPUTER_BAND_REALITY_IPv4_443",
    ]
    assert groups["COMPUTER_CDN"]["proxies"] == [
        "COMPUTER_BAND_CF_WS_443",
        "COMPUTER_DMIT_CF_WS_443",
    ]
    assert groups["COMPUTER_AI"]["proxies"] == [
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
        "COMPUTER_DMIT_CF_WS_443",
    ]
    assert not any("COMPUTER_BAND_" in member for member in groups["COMPUTER_AI"]["proxies"])
    assert groups["COMPUTER_SOCIAL"]["proxies"] == [
        "COMPUTER_BAND_REALITY_IPv4_443",
        "COMPUTER_BAND_CF_WS_443",
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_CF_WS_443",
    ]
    assert groups["COMPUTER_VIDEO"]["proxies"] == [
        "COMPUTER_BAND_CF_WS_443",
        "COMPUTER_DMIT_CF_WS_443",
        "COMPUTER_BAND_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
    ]
    assert groups["COMPUTER_DEFAULT"]["proxies"] == [
        "COMPUTER_BAND_REALITY_IPv4_443",
        "COMPUTER_BAND_CF_WS_443",
        "COMPUTER_DMIT_REALITY_IPv4_443",
        "COMPUTER_DMIT_REALITY_IPv4_8443",
        "COMPUTER_DMIT_CF_WS_443",
    ]
    health_groups = [group for group in profile["proxy-groups"] if group["type"] != "select"]
    health_group_names = {group["name"] for group in health_groups}
    for group in health_groups:
        assert group["url"] == "https://www.gstatic.com/generate_204"
        assert group["interval"] == 120
        assert group["lazy"] is False
        assert group["max-failed-times"] == 2
        assert not any("IPv6" in member for member in group["proxies"])
        assert not health_group_names.intersection(group["proxies"])
    for group_name in ("COMPUTER_SOCIAL", "COMPUTER_VIDEO", "COMPUTER_DEFAULT"):
        members = groups[group_name]["proxies"]
        assert any("COMPUTER_DMIT_" in member for member in members)
        assert any("COMPUTER_BAND_" in member for member in members)
    assert "DOMAIN-SUFFIX,openai.com,COMPUTER_AI" in profile["rules"]
    assert "DOMAIN-SUFFIX,plasma.to,COMPUTER_AI" in profile["rules"]
    assert "DOMAIN-SUFFIX,x.com,COMPUTER_SOCIAL" in profile["rules"]
    assert "DOMAIN-SUFFIX,youtube.com,COMPUTER_VIDEO" in profile["rules"]
    assert profile["rules"][-1] == "MATCH,PROXY"
    assert LEGACY_UUID not in yaml.safe_dump(profile)


def test_tv_profile_is_cdn_first_with_direct_fallback_and_tv_identity() -> None:
    names = [
        "DMIT_CF_WS_443",
        "BAND_CF_WS_443",
        "DMIT_REALITY_IPv4_443",
        "BAND_REALITY_IPv4_443",
        "BAND_REALITY_IPv6_443",
        "DMIT_TLS_IPv6_443",
        "DMIT_REALITY_IPv4_8443",
    ]

    profile = module.build_tv_profile([clash_proxy(name) for name in names], TV_UUID)

    assert {p["uuid"] for p in profile["proxies"]} == {TV_UUID}
    assert all(p["name"].startswith("TV_") for p in profile["proxies"])
    groups = {g["name"]: g for g in profile["proxy-groups"]}
    assert groups["TV_CDN"]["proxies"] == ["TV_DMIT_CF_WS_443", "TV_BAND_CF_WS_443"]
    assert groups["TV_DIRECT"]["proxies"] == [
        "TV_DMIT_REALITY_IPv4_443",
        "TV_BAND_REALITY_IPv4_443",
        "TV_BAND_REALITY_IPv6_443",
        "TV_DMIT_TLS_IPv6_443",
        "TV_DMIT_REALITY_IPv4_8443",
    ]
    assert groups["TV_POLICY"]["proxies"] == ["TV_CDN", "TV_DIRECT"]


def test_env_requires_distinct_tokens_and_uuids(tmp_path: Path) -> None:
    env = tmp_path / "device.env"
    env.write_text(
        "\n".join(
            [
                "MASTER_TOKEN=master-token-123456",
                "MOBILE_TOKEN=mobile-token-123456",
                "COMPUTER_TOKEN=mobile-token-123456",
                "TV_TOKEN=tv-token-1234567890",
                f"MOBILE_UUID={MOBILE_UUID}",
                f"COMPUTER_UUID={COMPUTER_UUID}",
                f"TV_UUID={TV_UUID}",
            ]
        )
    )

    with pytest.raises(RuntimeError, match="tokens must be distinct"):
        module.load_device_env(env)


def test_env_rejects_duplicate_keys(tmp_path: Path) -> None:
    env = tmp_path / "duplicate.env"
    env.write_text("MASTER_TOKEN=master-token-123456\nMASTER_TOKEN=other-master-token-123456\n")
    with pytest.raises(RuntimeError, match="duplicate env key"):
        module._read_env(env)


@pytest.mark.parametrize("key", ["MASTER_TOKEN", "XHTTP_TOKEN", "BAND_XHTTP_TOKEN"])
def test_env_rejects_unsafe_master_path_tokens(tmp_path: Path, key: str) -> None:
    values = {
        "MASTER_TOKEN": "master-token-123456",
        "XHTTP_TOKEN": "xhttp-token-123456",
        "BAND_XHTTP_TOKEN": "band-xhttp-token-123456",
        "MOBILE_TOKEN": "mobile-token-123456",
        "COMPUTER_TOKEN": "computer-token-123456",
        "TV_TOKEN": "tv-token-1234567890",
        "MOBILE_UUID": MOBILE_UUID,
        "COMPUTER_UUID": COMPUTER_UUID,
        "TV_UUID": TV_UUID,
    }
    values[key] = "../../private"
    env = tmp_path / "device.env"
    env.write_text("\n".join(f"{name}={value}" for name, value in values.items()) + "\n")

    with pytest.raises(RuntimeError, match="URL-safe"):
        module.load_device_env(env)


def test_atomic_publish_writes_expected_paths_and_permissions(tmp_path: Path) -> None:
    outputs = {
        ("mobile", "default", "mobile-token-123456"): "mobile-body\n",
        ("computer", "clashMetaProfiles", "computer-token-123456"): "computer-body\n",
        ("tv", "clashMetaProfiles", "tv-token-1234567890"): "tv-body\n",
    }

    module.publish_outputs(tmp_path, outputs)

    for parts, body in outputs.items():
        path = tmp_path / "split" / parts[0] / parts[1] / parts[2]
        assert path.read_text() == body
        assert path.stat().st_mode & 0o777 == 0o644
    for directory in (
        tmp_path / "split",
        tmp_path / "split" / "mobile",
        tmp_path / "split" / "mobile" / "default",
        tmp_path / "split" / "computer",
        tmp_path / "split" / "computer" / "clashMetaProfiles",
        tmp_path / "split" / "tv",
        tmp_path / "split" / "tv" / "clashMetaProfiles",
    ):
        assert directory.stat().st_mode & 0o777 == 0o755

    with pytest.raises(RuntimeError, match="invalid publication path"):
        module.publish_outputs(tmp_path, {("mobile", "clashMetaProfiles", "mobile-token-123456"): "bad"})


def test_token_rotation_removes_only_previous_managed_publications(tmp_path: Path) -> None:
    first = {
        ("mobile", "default", "mobile-token-old-123456"): "old-mobile\n",
        ("computer", "clashMetaProfiles", "computer-token-old-123456"): "old-computer\n",
        ("tv", "clashMetaProfiles", "tv-token-old-123456"): "old-tv\n",
    }
    unrelated = tmp_path / "split" / "tv" / "clashMetaProfiles" / "legacy-unmanaged-token"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("legacy\n")
    module.publish_outputs(tmp_path, first)

    second = {
        ("mobile", "default", "mobile-token-new-123456"): "new-mobile\n",
        ("computer", "clashMetaProfiles", "computer-token-new-123456"): "new-computer\n",
        ("tv", "clashMetaProfiles", "tv-token-new-123456"): "new-tv\n",
    }
    module.publish_outputs(tmp_path, second)

    for device, format_name, token in first:
        assert not (tmp_path / "split" / device / format_name / token).exists()
    for device, format_name, token in second:
        assert (tmp_path / "split" / device / format_name / token).exists()
    assert unrelated.exists()
    manifest = tmp_path / ".device-publications.json"
    assert manifest.stat().st_mode & 0o777 == 0o600


def test_malformed_manifest_fails_before_any_publication_change(tmp_path: Path) -> None:
    existing = tmp_path / "split" / "mobile" / "default" / "existing-token-123456"
    existing.parent.mkdir(parents=True)
    existing.write_text("existing\n")
    (tmp_path / ".device-publications.json").write_text("not-json")
    new_path = tmp_path / "split" / "mobile" / "default" / "new-token-123456789"

    with pytest.raises(RuntimeError, match="invalid device publication manifest"):
        module.publish_outputs(tmp_path, {("mobile", "default", new_path.name): "new\n"})

    assert existing.read_text() == "existing\n"
    assert not new_path.exists()


def test_reconcile_env_requires_only_distinct_device_uuids(tmp_path: Path) -> None:
    env = tmp_path / "identities.env"
    env.write_text(
        f"LEGACY_UUID={LEGACY_UUID}\nMOBILE_UUID={MOBILE_UUID}\nCOMPUTER_UUID={COMPUTER_UUID}\nTV_UUID={TV_UUID}\n"
    )

    values = module.load_reconcile_env(env)

    assert values == {
        "LEGACY_UUID": LEGACY_UUID,
        "MOBILE_UUID": MOBILE_UUID,
        "COMPUTER_UUID": COMPUTER_UUID,
        "TV_UUID": TV_UUID,
    }


def test_reconcile_clients_is_append_only_and_idempotent() -> None:
    config = {
        "inbounds": [
            {
                "tag": "VLESS_REALITY",
                "protocol": "vless",
                "settings": {"clients": [{"id": LEGACY_UUID, "flow": "xtls-rprx-vision"}]},
            },
            {"tag": "SOCKS", "protocol": "socks", "settings": {}},
        ]
    }
    identities = {
        "device-mobile": MOBILE_UUID,
        "device-computer": COMPUTER_UUID,
        "device-tv": TV_UUID,
    }

    changed = module.reconcile_vless_clients(config, identities, LEGACY_UUID)
    second = module.reconcile_vless_clients(config, identities, LEGACY_UUID)

    clients = config["inbounds"][0]["settings"]["clients"]
    assert changed is True
    assert second is False
    assert clients[0] == {"id": LEGACY_UUID, "flow": "xtls-rprx-vision"}
    assert {(c.get("email"), c["id"]) for c in clients[1:]} == set(identities.items())
    assert all(c.get("flow") == "xtls-rprx-vision" for c in clients[1:])
    assert config["inbounds"][1]["settings"] == {}


def test_reconcile_fails_closed_without_vless_or_legacy_and_on_duplicates() -> None:
    identities = {"device-mobile": MOBILE_UUID, "device-computer": COMPUTER_UUID, "device-tv": TV_UUID}
    with pytest.raises(RuntimeError, match="no VLESS inbounds"):
        module.reconcile_vless_clients({"inbounds": []}, identities, LEGACY_UUID)

    missing_legacy = {
        "inbounds": [{"tag": "VLESS", "protocol": "vless", "settings": {"clients": [{"id": MOBILE_UUID}]}}]
    }
    with pytest.raises(RuntimeError, match="legacy client missing"):
        module.reconcile_vless_clients(missing_legacy, identities, LEGACY_UUID)

    duplicate_ids = {
        "inbounds": [{
            "tag": "VLESS",
            "protocol": "vless",
            "settings": {"clients": [{"id": LEGACY_UUID}, {"id": LEGACY_UUID}]},
        }]
    }
    with pytest.raises(RuntimeError, match="duplicate client id"):
        module.reconcile_vless_clients(duplicate_ids, identities, LEGACY_UUID)


def test_nginx_contract_exposes_only_explicit_device_formats() -> None:
    snippet = (Path(__file__).resolve().parents[1] / "nginx" / "rose-device-subscriptions.conf.inc").read_text()
    assert "/rose-mobile/default/" in snippet
    assert "/rose-computer/clashMetaProfiles/" in snippet
    assert "/rose-tv/clashMetaProfiles/" in snippet
    assert "[A-Za-z0-9_-]{16,128}" in snippet
    assert "rose-(mobile|computer|tv)/(.*)" not in snippet
    expected = {
        "Rose Mobile": "Um9zZSBNb2JpbGU=",
        "Rose Computer": "Um9zZSBDb21wdXRlcg==",
        "Rose TV": "Um9zZSBUVg==",
    }
    for title, encoded in expected.items():
        assert f'profile-title "base64:{encoded}"' in snippet
    for filename in ("rose-mobile.txt", "rose-computer.yaml", "rose-tv.yaml"):
        assert f"filename={filename}" in snippet
        assert f'filename=\\"{filename}\\"' not in snippet
        assert f'filename="{filename}"' not in snippet




def test_systemd_timer_contract_and_transactional_reconcile_script() -> None:
    root = Path(__file__).parents[1]
    dmit_timer = (root / "systemd" / "rose-device-clients-dmit.timer").read_text()
    band_timer = (root / "systemd" / "rose-device-clients-band.timer").read_text()
    assert "Unit=rose-device-clients-dmit.service" in dmit_timer
    assert "Unit=rose-device-clients-band.service" in band_timer

    script = root / "scripts" / "rose-reconcile-device-clients.sh"
    text = script.read_text()
    assert script.stat().st_mode & 0o111
    assert "CANDIDATE=" in text
    assert "BACKUP=" in text
    assert "flock -n 9" in text
    assert "/run/lock/rose-device-clients.lock" in text
    assert "RESTORE=" in text
    assert 'cp -p "$BACKUP" "$RESTORE"' in text
    assert 'mv "$RESTORE" "$CONFIG"' in text
    dmit_service = (root / "systemd" / "rose-device-clients-dmit.service").read_text()
    band_service = (root / "systemd" / "rose-device-clients-band.service").read_text()
    assert "/run/lock" in dmit_service
    assert "/run/lock" in band_service
    manager_lock = (root / "systemd" / "reality-camouflage-health.service.d" / "20-device-client-lock.conf").read_text()
    assert "ExecStart=" in manager_lock
    assert "/usr/bin/flock -n /run/lock/rose-device-clients.lock" in manager_lock
    assert "--force-id cloudflare" in manager_lock
    assert "LIVE_SHA=" in text
    assert "current_sha" in text
    assert text.index("xray run -test") < text.index('mv "$CANDIDATE" "$CONFIG"')
    assert 'if ! "$GENERATOR" reconcile --env "$ENV_FILE" --config "$CONFIG"' in text
    assert "rollback" in text
    assert (root / "scripts" / "rose_device_subscriptions.py").stat().st_mode & 0o111
