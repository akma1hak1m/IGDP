from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.shortcuts import redirect
from django.urls import path
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
