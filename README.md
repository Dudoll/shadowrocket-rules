# Rose Dual-VPS Shadowrocket Config

This orphan branch is an independent Shadowrocket config subscription. It does not change the repository's `main` branch and contains no node or subscription credentials.

Config URL:

```text
https://raw.githubusercontent.com/Dudoll/shadowrocket-rules/rose-dual-vps/shadowrocket-rose.conf
```

Import the private `rose` node subscription first, then add the URL above as a configuration subscription in Shadowrocket.

Routing behavior:

- China whitelist and `GEOIP,CN`: direct.
- ChatGPT/OpenAI and all other proxied traffic: Cloudflare WS TLS 443 first, with Band IPv6/IPv4 Reality 443 as ordered fallbacks.
- Advertising and tracking domains: rejected by the remotely maintained `reject.txt` rule set.
- TLS Vision, DMIT direct nodes, duplicate aliases, literal-IP nodes, and non-standard proxy ports are intentionally not published.

The public config selects only these three node names:

```text
VLESS_WS_TLS_CF_443
VLESS_REALITY_Vision_IPv6_443
VLESS_REALITY_Vision_443
```

The two Reality hostnames are DNS-only by protocol necessity and therefore reveal the Band origin IPv6/IPv4 when queried. Cloudflare WS remains the privacy-preserving default.

The China whitelist is maintained by [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script).
