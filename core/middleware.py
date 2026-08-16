from django.contrib.auth.models import User
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect


class ImpersonateMiddleware(MiddlewareMixin):

    STOP_PATHS = ('/admin/logout/', '/logout/', '/core/impersonate/stop/', '/admin/login/')

    def _stop_impersonation(self, request):
        """Stop impersonation and re-login as superuser."""
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

    def process_request(self, request):
        impersonate_as_id = request.session.get('impersonate_as_id')
        if not impersonate_as_id:
            request.is_impersonating = False
            return

        if not request.user.is_authenticated:
            # Session has impersonate keys but user not authenticated — clean up
            request.session.pop('impersonate_as_id', None)
            request.session.pop('impersonator_id', None)
            request.is_impersonating = False
            return

        # If hitting stop/logout/login paths, stop impersonation and redirect to admin
        if request.path in self.STOP_PATHS:
            self._stop_impersonation(request)
            request._impersonate_redirect = redirect('/admin/')
            return

        # Impersonate the user
        try:
            impersonated_user = User.objects.get(pk=impersonate_as_id)
            request.user = impersonated_user
            request.impersonator_id = request.session.get('impersonator_id')
            request.is_impersonating = True
        except User.DoesNotExist:
            request.session.pop('impersonate_as_id', None)
            request.session.pop('impersonator_id', None)
            request.is_impersonating = False

    def process_response(self, request, response):
        if hasattr(request, '_impersonate_redirect'):
            return request._impersonate_redirect
        # If a view redirected to login while impersonating, intercept
        if (getattr(request, 'is_impersonating', False) and
                response.status_code == 302 and
                '/login/' in response.get('Location', '')):
            self._stop_impersonation(request)
            return redirect('/admin/')
        return response
