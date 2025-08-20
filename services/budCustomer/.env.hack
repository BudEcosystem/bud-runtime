# TODO:
# This is a hack to inject variables at runtime, since
# it's not properly implemented on application side
# used by the nix pacakge & container derivation, since it modifies the
# src at runtime nix pkg won't work, just the container that's using it

# API Configuration
NEXT_PUBLIC_BASE_URL=NEXT_PUBLIC_BASE_URL
NEXT_PUBLIC_API_BASE_URL=NEXT_PUBLIC_API_BASE_URL
NEXT_PUBLIC_TEMP_API_BASE_URL=NEXT_PUBLIC_TEMP_API_BASE_URL

# Playground Configuration
NEXT_PUBLIC_PLAYGROUND_URL=NEXT_PUBLIC_PLAYGROUND_URL
NEXT_PUBLIC_ASK_BUD_URL=NEXT_PUBLIC_ASK_BUD_URL
NEXT_PUBLIC_ASK_BUD_MODEL=NEXT_PUBLIC_ASK_BUD_MODEL

# Notification Configuration
NEXT_PUBLIC_NOVU_BASE_URL=NEXT_PUBLIC_NOVU_BASE_URL
NEXT_PUBLIC_NOVU_SOCKET_URL=NEXT_PUBLIC_NOVU_SOCKET_URL

# Gateway Configuration
NEXT_PUBLIC_COPY_CODE_API_BASE_URL=NEXT_PUBLIC_COPY_CODE_API_BASE_URL

# Asset Configuration
NEXT_PUBLIC_ASSET_BASE_URL=NEXT_PUBLIC_ASSET_BASE_URL

# Security Configuration (for production deployment)
NEXT_PUBLIC_PRIVATE_KEY=NEXT_PUBLIC_PRIVATE_KEY
NEXT_PUBLIC_PASSWORD=NEXT_PUBLIC_PASSWORD
