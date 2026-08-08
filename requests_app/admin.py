from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
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


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"


class UserAdminWithProfile(UserAdmin):
    inlines = [UserProfileInline]


admin.site.unregister(User)
admin.site.register(User, UserAdminWithProfile)

admin.site.register(DataRequest)

admin.site.register(SerahanRequest)
admin.site.register(PinjamanRequest)
admin.site.register(StatusLog)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bahagian", "phone")
    list_filter = ("bahagian",)
    search_fields = ("user__username", "user__email")


@admin.register(Bahagian)
class BahagianAdmin(admin.ModelAdmin):
    list_display = ("nama",)
    search_fields = ("nama",)


admin.site.register(Negeri)
admin.site.register(Daerah)
admin.site.register(Mukim)
