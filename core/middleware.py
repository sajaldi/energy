from django.contrib.auth.models import User
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect


class ImpersonateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        impersonate_as_id = request.session.get('impersonate_as_id')
        if impersonate_as_id and request.user.is_authenticated:
            # Intercept logout while impersonating: stop impersonation instead
            if request.path in ('/admin/logout/', '/logout/'):
                impersonator_id = request.session.get('impersonator_id')
                request.session.pop('impersonate_as_id', None)
                request.session.pop('impersonator_id', None)
                if impersonator_id:
                    try:
                        from django.contrib.auth import login as auth_login
                        superuser = User.objects.get(pk=impersonator_id, is_superuser=True)
                        auth_login(request, superuser, backend='django.contrib.auth.backends.ModelBackend')
                    except User.DoesNotExist:
                        pass
                request._impersonate_redirect = redirect('/admin/')
                return

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

    def process_response(self, request, response):
        # If we intercepted logout during impersonation, redirect back to admin
        if hasattr(request, '_impersonate_redirect'):
            return request._impersonate_redirect
        return response
