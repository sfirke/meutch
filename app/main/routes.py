import random

from app.main.views import browse, giveaways, items, loans, messaging, profile, public  # noqa: F401
from app.utils.digest_tokens import verify_digest_manage_token
from app.utils.email import send_message_notification_email
from app.utils.storage import upload_item_images

giveaways.random = random
items.upload_item_images = lambda *args, **kwargs: upload_item_images(*args, **kwargs)
items.send_message_notification_email = lambda *args, **kwargs: send_message_notification_email(
    *args, **kwargs
)
giveaways.send_message_notification_email = lambda *args, **kwargs: send_message_notification_email(
    *args, **kwargs
)
loans.send_message_notification_email = lambda *args, **kwargs: send_message_notification_email(
    *args, **kwargs
)
messaging.send_message_notification_email = lambda *args, **kwargs: send_message_notification_email(
    *args, **kwargs
)
profile.verify_digest_manage_token = lambda *args, **kwargs: verify_digest_manage_token(
    *args, **kwargs
)
