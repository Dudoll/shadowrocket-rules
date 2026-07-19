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

### Device-distinct primary links

Each device class uses a different private token, client identity, URL path, and node-name prefix. Tokens and UUIDs are generated on the server and never stored in Git.

```text
https://cf.joelzt.org/rose-mobile/default/<MOBILE_TOKEN>                  # Phone / tablet, Base64 VLESS
https://cf.joelzt.org/rose-computer/clashMetaProfiles/<COMPUTER_TOKEN>    # Computer, full Clash Meta profile
https://cf.joelzt.org/rose-tv/clashMetaProfiles/<TV_TOKEN>                # TV, self-contained CDN-first profile
```

Expected node prefixes are `MOBILE_`, `COMPUTER_`, and `TV_`. The legacy products below remain available during migration:

```text
https://cf.joelzt.org/rose-band/<TOKEN>  # Band only
https://cf.joelzt.org/rose-dmit/<TOKEN>  # DMIT only
https://cf.joelzt.org/rose-all/<TOKEN>   # Both VPSes
https://cf.joelzt.org/rose-tv/<TOKEN>    # Legacy TV root
```

The legacy format-specific form is `/rose-{band|dmit|all|tv}/{default|clashMeta|clashMetaProfiles|sing-box|sing-box_profiles}/<TOKEN>`. Device identities are appended to every VLESS inbound while the legacy identity is preserved for rollback.

### Durable installation contract

Install `scripts/rose_device_subscriptions.py` as `/usr/local/sbin/rose-generate-device-subscriptions` and `scripts/rose-reconcile-device-clients.sh` as `/usr/local/sbin/rose-reconcile-device-clients`, both mode `0755`. On DMIT install/enable `rose-device-clients-dmit.{service,timer}`; on Band install/enable `rose-device-clients-band.{service,timer}`. The root-only identity env is mode `0600` and contains `LEGACY_UUID`, `MOBILE_UUID`, `COMPUTER_UUID`, and `TV_UUID`; the legacy UUID is required in every VLESS inbound and is never removed by reconciliation.

Reconciliation is transactional: it mutates an isolated candidate, validates a complete temporary Xray confdir, then atomically installs and restarts. Restart or health-check failure restores the prior live config. The timers are host-specific and name their service explicitly.

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
DMIT_REALITY_IPv4_443
DMIT_REALITY_IPv4_8443
```

DMIT splits port 443 by address family: IPv4 serves Reality while the stable direct IPv6 address serves TLS Vision. Port 8443 remains as a Reality fallback. DMIT Reality over IPv6 was tested and rejected; DMIT uses TLS Vision for the IPv6 fallback instead.

The Cloudflare WS endpoints hide the corresponding origin. Dedicated Reality/TLS direct hostnames are DNS-only by protocol necessity and reveal their VPS IPv4/IPv6 when queried. No literal origin IP is embedded in the subscription.

The China whitelist is maintained by [Loyalsoldier/surge-rules](https://github.com/Loyalsoldier/surge-rules).
