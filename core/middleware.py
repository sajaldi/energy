from django.contrib.auth.models import User
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect


class ImpersonateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        impersonate_as_id = request.session.get('impersonate_as_id')
        if impersonate_as_id and request.user.is_authenticated:
            # Don't impersonate on stop/logout routes — restore real user
            skip_paths = ('/admin/logout/', '/logout/', '/core/impersonate/stop/')
            if request.path in skip_paths:
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

            # If accessing admin login page while impersonating, stop impersonation
            if request.path == '/admin/login/':
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
        if hasattr(request, '_impersonate_redirect'):
            return request._impersonate_redirect
        # If response is a redirect to admin login while impersonating, stop and go back
        if (hasattr(request, 'is_impersonating') and request.is_impersonating and
            hasattr(response, 'status_code') and response.status_code == 302 and
            hasattr(response, 'url') and '/admin/login/' in response.get('Location', '')):
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
            return redirect('/admin/')
        return response
