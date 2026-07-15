# Rose Dual-VPS Shadowrocket Config

This orphan branch is an independent Shadowrocket config subscription. It does not change the repository's `main` branch and contains no node or subscription credentials.

Config URL:

```text
https://raw.githubusercontent.com/Dudoll/shadowrocket-rules/rose-dual-vps/shadowrocket-rose.conf
```

Import the private `rose` node subscription first, then add the URL above as a configuration subscription in Shadowrocket.

Routing behavior:

- China whitelist and `GEOIP,CN`: direct.
- ChatGPT/OpenAI: Los Angeles DMIT TLS/Reality nodes only.
- Advertising and tracking domains: rejected by the remotely maintained `reject.txt` rule set.
- Other destinations: Tokyo and Los Angeles stable TLS/Reality nodes are tested every 1800 seconds.
- A 20 ms tolerance avoids switching nodes for insignificant latency changes.

The public config selects nodes only by these public names:

```text
VLESS_TCP_TLS_Vision_DMIT_443
VLESS_REALITY_Vision_DMIT_8443
VLESS_TCP_TLS_Vision_8443_band
VLESS_REALITY_Vision_443_band
```

The China whitelist is maintained by [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script).
