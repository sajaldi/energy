from django.contrib.auth.models import User
from django.utils.deprecation import MiddlewareMixin


class ImpersonateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        impersonate_as_id = request.session.get('impersonate_as_id')
        if impersonate_as_id and request.user.is_authenticated:
            try:
                impersonated_user = User.objects.get(pk=impersonate_as_id)
                request.user = impersonated_user
                request.impersonator_id = request.session.get('impersonator_id')
                request.is_impersonating = True
            except User.DoesNotExist:
                request.session.pop('impersonate_as_id', None)
                request.session.pop('impersonator_id', None)
                request.is_impersonating = False
        else:
            request.is_impersonating = False
