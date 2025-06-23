"""Middleware to mark notifications as seen when the user visits certain pages.
Add 'sparc.notification_middleware.NotificationSeenMiddleware' to MIDDLEWARE in settings.py
"""
from django.utils import timezone

URL_NAME_TO_SESSION_KEY = {
    "commission_history": "last_seen_commissions",
    "tranche_history": "last_seen_tranches",
    "approve": "last_seen_unapproved",
    "receivables": "last_seen_receivables",
}

class NotificationSeenMiddleware:
    """Update session timestamps after each request for specific pages so that
    notification badges reset once the user has visited the relevant page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Mark "seen" BEFORE the view so that context processors run after the timestamp is set
        resolver = getattr(request, "resolver_match", None)
        if request.user.is_authenticated and resolver is not None:
            url_name = resolver.url_name
            session_key = URL_NAME_TO_SESSION_KEY.get(url_name)
            if session_key:
                request.session[session_key] = timezone.now().isoformat()
        response = self.get_response(request)
        return response
