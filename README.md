# Rose Dual-VPS Shadowrocket Config

This orphan branch contains public Shadowrocket routing configs only. Node URLs, UUIDs, subscription tokens, and Reality keys remain in the private node subscription.

## Config URLs

### Universal app-routing config

```text
https://raw.githubusercontent.com/Dudoll/shadowrocket-rules/rose-dual-vps/shadowrocket-rose.conf
```

Default traffic uses `自动优先`.

### Band-default device config (recommended for iPhone)

```text
https://raw.githubusercontent.com/Dudoll/shadowrocket-rules/rose-dual-vps/shadowrocket-band.conf
```

Unmatched traffic defaults to `Band优先`.

### DMIT-default device config (recommended for iPad and Mac)

```text
https://raw.githubusercontent.com/Dudoll/shadowrocket-rules/rose-dual-vps/shadowrocket-dmit.conf
```

Unmatched traffic defaults to `DMIT优先`.

Import the private `rose` node subscription first, then add the appropriate URL above as a configuration subscription in Shadowrocket.

## Device-specific node subscriptions

```text
https://cf.joelzt.org/rose-band/<TOKEN>  # Band only
https://cf.joelzt.org/rose-dmit/<TOKEN>  # DMIT only
https://cf.joelzt.org/rose-all/<TOKEN>   # Both VPSes
```

The format-specific form is `/rose-{band|dmit|all}/{default|clashMeta|clashMetaProfiles|sing-box|sing-box_profiles}/<TOKEN>`.

## App routing

- ChatGPT, OpenAI, Claude, Anthropic, and Plasma → `DMIT优先`.
- Telegram, YouTube, and Google → `Band优先`.
- China whitelist, `GEOIP,CN`, Apple mainland services, LAN, and system traffic → direct.
- Advertising and tracking domains → rejected.
- Remaining blocked/non-China traffic → the device config's default `PROXY` policy.

## Published node names

### Band

```text
BAND_CF_WS_443
BAND_REALITY_IPv6_443
BAND_REALITY_IPv4_443
```

### DMIT

```text
DMIT_CF_WS_443
DMIT_TLS_IPv6_443
DMIT_REALITY_IPv4_8443
```

Each VPS group prefers Cloudflare WS, then its verified IPv6 direct path, then its verified IPv4 Reality path. DMIT Reality over IPv6 was tested and rejected; DMIT uses TLS Vision for the IPv6 fallback instead.

The Cloudflare WS endpoints hide the corresponding origin. Dedicated Reality/TLS direct hostnames are DNS-only by protocol necessity and reveal their VPS IPv4/IPv6 when queried. No literal origin IP is embedded in the subscription.

The China whitelist is maintained by [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules).
