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
