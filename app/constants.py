"""Application-wide constants."""

import uuid

# Reserved system user UUID — used as the sender for automated notifications
# (e.g. circle join-request decisions) so the acting admin remains anonymous.
SYSTEM_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
