# Backfill record_no globally across SerahanRequest + PinjamanRequest,
# ordered by (created_at, id) so oldest record gets 1. Uses UPDATE to
# avoid touching updated_at.

from django.db import migrations


def backfill_record_no(apps, schema_editor):
    SerahanRequest = apps.get_model("requests_app", "SerahanRequest")
    PinjamanRequest = apps.get_model("requests_app", "PinjamanRequest")

    tagged = [("S", pk, ca) for pk, ca in SerahanRequest.objects.all().values_list("pk", "created_at")]
    tagged += [("P", pk, ca) for pk, ca in PinjamanRequest.objects.all().values_list("pk", "created_at")]
    tagged.sort(key=lambda t: (t[2], t[1]))  # created_at, then pk

    for n, (model_tag, pk, _) in enumerate(tagged, start=1):
        if model_tag == "S":
            SerahanRequest.objects.filter(pk=pk).update(record_no=n)
        else:
            PinjamanRequest.objects.filter(pk=pk).update(record_no=n)


def unbackfill(apps, schema_editor):
    SerahanRequest = apps.get_model("requests_app", "SerahanRequest")
    PinjamanRequest = apps.get_model("requests_app", "PinjamanRequest")
    SerahanRequest.objects.update(record_no=None)
    PinjamanRequest.objects.update(record_no=None)


class Migration(migrations.Migration):

    dependencies = [
        ("requests_app", "0040_pinjamanrequest_record_no_serahanrequest_record_no"),
    ]

    operations = [
        migrations.RunPython(backfill_record_no, unbackfill),
    ]
