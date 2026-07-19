# Explicit device subscription routes. Include these inside each subscription server block.
# Unsupported formats remain 404 through the existing rose-* catch-all.
location ~ "^/rose-mobile/default/([A-Za-z0-9_-]{16,128})$" {
    alias /var/www/rose-rules/split/mobile/default/$1;
}

location ~ "^/rose-computer/clashMetaProfiles/([A-Za-z0-9_-]{16,128})$" {
    alias /var/www/rose-rules/split/computer/clashMetaProfiles/$1;
}

location ~ "^/rose-tv/clashMetaProfiles/([A-Za-z0-9_-]{16,128})$" {
    alias /var/www/rose-rules/split/tv/clashMetaProfiles/$1;
}
