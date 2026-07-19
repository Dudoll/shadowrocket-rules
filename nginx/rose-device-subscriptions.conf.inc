# Explicit device subscription routes. Include these inside each subscription server block.
# Unsupported formats remain 404 through the existing rose-* catch-all.
# Unquoted ASCII filenames avoid Clash Verge preserving escaped quote characters.
location ~ "^/rose-mobile/default/([A-Za-z0-9_-]{16,128})$" {
    alias /var/www/rose-rules/split/mobile/default/$1;
    add_header profile-title "base64:Um9zZSBNb2JpbGU=" always;
    add_header Content-Disposition "attachment; filename=rose-mobile.txt" always;
    add_header Cache-Control "no-store" always;
    add_header X-Rose-Subscription-Origin "vps-dmit" always;
}

location ~ "^/rose-computer/clashMetaProfiles/([A-Za-z0-9_-]{16,128})$" {
    alias /var/www/rose-rules/split/computer/clashMetaProfiles/$1;
    add_header profile-title "base64:Um9zZSBDb21wdXRlcg==" always;
    add_header Content-Disposition "attachment; filename=rose-computer.yaml" always;
    add_header Cache-Control "no-store" always;
    add_header X-Rose-Subscription-Origin "vps-dmit" always;
}

location ~ "^/rose-tv/clashMetaProfiles/([A-Za-z0-9_-]{16,128})$" {
    alias /var/www/rose-rules/split/tv/clashMetaProfiles/$1;
    add_header profile-title "base64:Um9zZSBUVg==" always;
    add_header Content-Disposition "attachment; filename=rose-tv.yaml" always;
    add_header Cache-Control "no-store" always;
    add_header X-Rose-Subscription-Origin "vps-dmit" always;
}
