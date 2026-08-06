from django.db import migrations


def status_map(borang_type, old):
    common = {
        "Borang Telah Dihantar": "Borang Telah Dihantar",
        "Pengarah Bahagian Telah Sahkan": "Disokong Oleh Pengarah Bahagian",
        "Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik": "Mendapat Kelulusan Pengarah BITG",
        "Data Telah Di-email": "Serahan Data",
        "Selesai": "Selesai",
    }
    per_type = {
        "SERAHAN": {
            "Penugasan PIC": "Semakan Dan Penugasan Oleh Pengurus Pengkalan Data",
            "Pemohon Telah Mengesahkan Data": "Selesai",
        },
        "PINJAMAN": {
            "Penugasan PIC": "Penugasan PIC Oleh Pengarah BITG",
            "Pemohon Telah Mengesahkan Data": "Sahkan Penerimaan Data",
        },
    }
    mapped = common.get(old)
    if mapped is None:
        mapped = per_type.get(borang_type, {}).get(old)
    return mapped or "Borang Telah Dihantar"


def resolve_lookup(Negeri, Daerah, Mukim, dr):
    negeri = Negeri.objects.filter(nama__iexact=dr.negeri).first()
    daerah = None
    mukim = None
    if negeri and dr.daerah:
        daerah = Daerah.objects.filter(negeri=negeri, nama__iexact=dr.daerah).first()
    if daerah and dr.mukim:
        mukim = Mukim.objects.filter(daerah=daerah, nama__iexact=dr.mukim).first()
    return negeri, daerah, mukim


def copy_data(apps, schema_editor):
    DataRequest = apps.get_model("requests_app", "DataRequest")
    Serahan = apps.get_model("requests_app", "SerahanRequest")
    Pinjaman = apps.get_model("requests_app", "PinjamanRequest")
    Negeri = apps.get_model("requests_app", "Negeri")
    Daerah = apps.get_model("requests_app", "Daerah")
    Mukim = apps.get_model("requests_app", "Mukim")
    StatusLog = apps.get_model("requests_app", "StatusLog")
    ContentType = apps.get_model("contenttypes", "ContentType")

    serah_ct = ContentType.objects.get_for_model(Serahan)
    pinjam_ct = ContentType.objects.get_for_model(Pinjaman)

    for dr in DataRequest.objects.all().order_by("id"):
        negeri, daerah, mukim = resolve_lookup(Negeri, Daerah, Mukim, dr)
        status = status_map(dr.borang_type, dr.status)

        if dr.borang_type == "SERAHAN":
            obj = Serahan(
                pemohon=dr.pemohon,
                namapemohon=dr.namapemohon,
                email=dr.email,
                telefon=dr.telefon,
                komponen_data=dr.komponen_data,
                komponen_lain=dr.komponen_lain,
                negeri=negeri,
                daerah=daerah,
                mukim=mukim,
                indeks=dr.indeks,
                uploaded_file=dr.uploaded_file,
                status=status,
                created_at=dr.created_at,
                jenis_data=dr.jenis_data,
                jenis_lain=dr.jenis_lain,
                format_data=dr.format_data,
                format_lain=dr.format_lain,
                unjuranKoordinat_data=dr.unjuranKoordinat_data,
                unjuranKoordinat_lain=dr.unjuranKoordinat_lain,
                sumber_data=dr.sumber_data,
                sumber_lain=dr.sumber_lain,
                meta_data=dr.meta_data,
                namaagensi=dr.namaagensikerjasama,
                namaprojek=dr.namaprojek,
                tarikhprojek=dr.tarikhprojek,
                jenisdataformat=dr.jenisdataformat,
                klasifikasidata=dr.klasifikasidata,
            )
            obj.save()
            ct, oid = serah_ct, obj.id
        else:
            obj = Pinjaman(
                pemohon=dr.pemohon,
                namapemohon=dr.namapemohon,
                email=dr.email,
                telefon=dr.telefon,
                komponen_data=dr.komponen_data,
                komponen_lain=dr.komponen_lain,
                negeri=negeri,
                daerah=daerah,
                mukim=mukim,
                indeks=dr.indeks,
                uploaded_file=dr.uploaded_file,
                status=status,
                created_at=dr.created_at,
                tujuan=dr.tujuan,
                cacatan=dr.cacatan,
                Setuju=dr.Setuju,
                nama=dr.nama,
                Tarikh=dr.Tarikh,
            )
            obj.save()
            ct, oid = pinjam_ct, obj.id

        StatusLog.objects.create(
            borang_type=dr.borang_type,
            content_type=ct,
            object_id=oid,
            status=status,
            changed_by=dr.pemohon,
            changed_at=dr.created_at,
            iteration=0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("requests_app", "0026_alter_datarequest_meta_data_pinjamanrequest_and_more"),
    ]

    operations = [
        migrations.RunPython(copy_data, migrations.RunPython.noop),
    ]
