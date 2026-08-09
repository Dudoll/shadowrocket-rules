# Shadowrocket Rules

Public Shadowrocket routing config without proxy credentials.

Raw config URL:

```text
https://raw.githubusercontent.com/Dudoll/shadowrocket-rules/main/shadowrocket-public-rules.conf
```

Import the private node subscription first. The config expects the current
node names `BAND_CF_WS_443`, `BAND_REALITY_IPv6_443`, `BAND_REALITY_IPv4_443`,
`DMIT_CF_WS_443`, `DMIT_TLS_IPv6_443`, and `DMIT_REALITY_IPv4_443`.

Policy groups:

- `PROXY`: manual selection among current automatic, social, DMIT, and Band groups.
- `社交低延迟`: Reality direct url-test first, Cloudflare WS fallback second.
- `ChatGPT`: DMIT-only fallback group.
- Explicit ad and tracking rules are evaluated before broad service routing.

## Versioned rule snapshots

The repository also keeps the latest verified rule snapshot copied from the VPS publication tree:

- `clash-rules/`: original Clash/Mihomo YAML payloads.
- `shadowrocket-rules/`: generated Surge/Shadowrocket line-oriented rules.

The snapshot was compared byte-for-byte with both `vps-band` and `vps-dmit` before being staged. Do not edit the generated Shadowrocket files manually; refresh the Clash sources and run `rose-convert-clash-rules.py` from the `rose-dual-vps-publish` repository instead. The runtime clients continue to use the Cloudflare publication endpoints, while these files provide a reviewable Git history and rollback point.
