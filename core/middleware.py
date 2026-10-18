from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from .models import profile_for


class UserTimezoneMiddleware(MiddlewareMixin):
    """Use the signed-in user's configured timezone while parsing forms/rendering pages."""
    def process_request(self, request):
        if request.user.is_authenticated:
            timezone.activate(profile_for(request.user).tz())

    def process_response(self, request, response):
        timezone.deactivate()
        return response
