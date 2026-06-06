# Shadowrocket Rules

Public Shadowrocket routing config without proxy credentials.

Raw config URL:

```text
https://raw.githubusercontent.com/Dudoll/shadowrocket-rules/main/shadowrocket-public-rules.conf
```

Use this config after importing your private node subscription in Shadowrocket. The policy groups are:

- `PROXY`: manually selects `两小时优选`, `DIRECT`, or regional groups.
- `两小时优选`: `url-test` for Hong Kong, Japan, Taiwan, and United States nodes every 7200 seconds.
- `ChatGPT`: Japan-only `url-test` every 7200 seconds.

The node names in your private subscription should include `香港`, `日本`, `台湾`, or `美国` so the regex filters can pick them up.
