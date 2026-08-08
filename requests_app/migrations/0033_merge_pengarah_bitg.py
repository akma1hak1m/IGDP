from django.db import migrations
from django.contrib.auth.models import Group


def merge_bitg_into_bahagian(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Group = apps.get_model("auth", "Group")
    UserProfile = apps.get_model("requests_app", "UserProfile")
    Bahagian = apps.get_model("requests_app", "Bahagian")

    pb_group, _ = Group.objects.get_or_create(name="Pengarah Bahagian")
    bitg_group = Group.objects.filter(name="Pengarah BITG").first()
    bitg_bahagian, _ = Bahagian.objects.get_or_create(nama="BITG")

    if bitg_group:
        for user in bitg_group.user_set.all():
            user.groups.add(pb_group)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if not profile.bahagian:
                profile.bahagian = bitg_bahagian
                profile.save()
            user.groups.remove(bitg_group)
        bitg_group.delete()


def unmerge_bitg_from_bahagian(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Pengarah BITG")


class Migration(migrations.Migration):

    dependencies = [
        ("requests_app", "0032_bahagian_pinjamanrequest_bahagian_and_more"),
    ]

    operations = [
        migrations.RunPython(merge_bitg_into_bahagian, unmerge_bitg_from_bahagian),
    ]
