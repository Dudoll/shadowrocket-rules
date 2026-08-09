from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
GENERATOR = ROOT / "scripts" / "rose-generate-tailored-clash.updated"
CONVERTER = ROOT / "scripts" / "rose-convert-clash-rules.py"


def _load_converter():
    spec = importlib.util.spec_from_file_location("rose_rule_converter", CONVERTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clash_payload_is_converted_to_shadowrocket_lines(tmp_path: Path) -> None:
    converter = _load_converter()
    source = tmp_path / "reject.txt"
    source.write_text(
        "payload:\n"
        "  - '+.example.com'\n"
        "  - 'exact.example.net'\n"
        "  - '192.0.2.0/24'\n"
        "  - '2001:db8::/32'\n",
        encoding="utf-8",
    )
    rules = converter.convert(source)
    assert rules == [
        "DOMAIN-SUFFIX,example.com",
        "DOMAIN,exact.example.net",
        "IP-CIDR,192.0.2.0/24",
        "IP-CIDR6,2001:db8::/32",
    ]


def test_generator_keeps_clash_and_shadowrocket_urls_separate() -> None:
    text = GENERATOR.read_text(encoding="utf-8")
    provider = text[text.index("def rule_provider"):text.index("def base_config")]
    shadowrocket = text[text.index("def shadowrocket_config"):]
    assert '"url": f"https://cf.joelzt.org/clash-rules/{name}.txt"' in provider
    assert "https://cf.joelzt.org/shadowrocket-rules/" not in provider
    assert "https://cf.joelzt.org/shadowrocket-rules/" in shadowrocket
    assert "https://cf.joelzt.org/clash-rules/" not in shadowrocket
    personal = text[text.index("def personal_profile"):text.index("def tv_profile")]
    rules = personal[personal.index('d["rules"] = ['):personal.index("    return d", personal.index('d["rules"] = ['))]
    assert rules.index("RULE-SET,private,DIRECT") < rules.index("DOMAIN-SUFFIX,chatgpt.com")
    assert rules.index("RULE-SET,reject,REJECT") < rules.index("DOMAIN-SUFFIX,chatgpt.com")
    assert "DOMAIN-SUFFIX,whatsapp.com,𝕏低延迟" in rules
    assert "DOMAIN-SUFFIX,whatsapp.net,𝕏低延迟" in rules


def test_standard_shadowrocket_configs_have_current_rules() -> None:
    for path in sorted(ROOT.glob("shadowrocket-*.conf")):
        text = path.read_text(encoding="utf-8")
        assert "8443" not in text
        assert "TAILSCALE" not in text
        assert "clash-rules" not in text
        reject = "RULE-SET,https://cf.joelzt.org/shadowrocket-rules/reject.txt,REJECT"
        assert text.count(reject) == 1
        assert text.index(reject) < text.index("DOMAIN-SUFFIX,google.com")
        for domain in (
            "x.com",
            "twitter.com",
            "instagram.com",
            "cdninstagram.com",
            "threads.net",
            "facebook.com",
            "fbcdn.net",
            "whatsapp.com",
            "whatsapp.net",
        ):
            assert f"DOMAIN-SUFFIX,{domain},社交低延迟" in text
