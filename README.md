# Rose Dual-VPS Shadowrocket Config

This orphan branch is an independent Shadowrocket config subscription. It does not change the repository's `main` branch and contains no node or subscription credentials.

Config URL:

```text
https://raw.githubusercontent.com/Dudoll/shadowrocket-rules/rose-dual-vps/shadowrocket-rose.conf
```

Import the private `rose` node subscription first, then add the URL above as a configuration subscription in Shadowrocket.

Routing behavior:

- China whitelist and `GEOIP,CN`: direct.
- ChatGPT/OpenAI and all other proxied traffic: the single Cloudflare-proxied WS TLS 443 node.
- Advertising and tracking domains: rejected by the remotely maintained `reject.txt` rule set.
- Direct VPS domains, IPv4/IPv6 literals, Reality, TLS Vision, and non-standard proxy ports are intentionally not published.

The public config selects only this privacy-preserving node name:

```text
VLESS_WS_TLS_CF_443
```

The China whitelist is maintained by [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script).
