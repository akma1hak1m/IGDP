from django.db import migrations


def create_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Pengurus Pengkalan Data")


class Migration(migrations.Migration):

    dependencies = [
        ("requests_app", "0027_migrate_datarequest_to_split_models"),
    ]

    operations = [
        migrations.RunPython(create_group, migrations.RunPython.noop),
    ]
