from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.models import User
from django.contrib.auth.views import REDIRECT_FIELD_NAME
from django.http import HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from .admin_auth import (
    ADMIN_SESSION_PREFIX,
    get_admin_user,
    preserve_all_except,
    set_admin_auth,
)
from .models import (
    Bahagian,
    DataRequest,
    Negeri,
    Daerah,
    Mukim,
    SerahanRequest,
    PinjamanRequest,
    StatusLog,
    UserProfile,
)


class CustomAdminSite(admin.AdminSite):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_view(self.redirect_to_user_list), name='index'),
        ]
        return custom_urls + urls

    def redirect_to_user_list(self, request):
        return redirect('custom_admin:auth_user_changelist')

    def has_permission(self, request):
        """Admin access comes from the separate admin session only."""
        return get_admin_user(request) is not None

    @method_decorator(never_cache, name="__call__")
    @method_decorator(login_not_required, name="__call__")
    def login(self, request, extra_context=None):
        """Admin login that stores auth state under dedicated session keys.

        The default Django admin login calls auth.login(), which would share
        the normal-user session; this version authenticates via
        AdminAuthenticationForm (staff accounts only) and stores the result
        under the ``_admin_auth`` keys instead.
        """
        if request.method == "POST":
            form = AdminAuthenticationForm(request, data=request.POST)
            if form.is_valid():
                set_admin_auth(request, form.get_user())
                redirect_to = (
                    request.POST.get(REDIRECT_FIELD_NAME)
                    or request.GET.get(REDIRECT_FIELD_NAME)
                    or reverse("admin:index", current_app=self.name)
                )
                return HttpResponseRedirect(redirect_to)
        else:
            if self.has_permission(request):
                return HttpResponseRedirect(reverse("admin:index", current_app=self.name))
            form = AdminAuthenticationForm(request)

        context = {
            **self.each_context(request),
            "title": _("Log in"),
            "subtitle": None,
            "app_path": request.get_full_path(),
            "username": request.POST.get("username", request.user.get_username()),
            "form": form,
        }
        if REDIRECT_FIELD_NAME not in request.GET and REDIRECT_FIELD_NAME not in request.POST:
            context[REDIRECT_FIELD_NAME] = reverse("admin:index", current_app=self.name)
        context.update(extra_context or {})
        request.current_app = self.name
        return TemplateResponse(request, self.login_template or "admin/login.html", context)

    def logout(self, request, extra_context=None):
        """Log out of the admin only; keep the normal-user session intact."""
        if request.method == "POST":
            preserve_all_except(request, (ADMIN_SESSION_PREFIX,))
            return HttpResponseRedirect(reverse("admin:login", current_app=self.name))
        return HttpResponseNotAllowed(["POST"])


custom_admin_site = CustomAdminSite(name='custom_admin')


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"


class UserAdminWithProfile(UserAdmin):
    inlines = [UserProfileInline]


custom_admin_site.register(User, UserAdminWithProfile)

custom_admin_site.register(DataRequest)

custom_admin_site.register(SerahanRequest)
custom_admin_site.register(PinjamanRequest)
custom_admin_site.register(StatusLog)


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bahagian", "phone")
    list_filter = ("bahagian",)
    search_fields = ("user__username", "user__email")


class BahagianAdmin(admin.ModelAdmin):
    list_display = ("nama",)
    search_fields = ("nama",)


custom_admin_site.register(UserProfile, UserProfileAdmin)
custom_admin_site.register(Bahagian, BahagianAdmin)


custom_admin_site.register(Negeri)
custom_admin_site.register(Daerah)
custom_admin_site.register(Mukim)
