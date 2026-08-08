from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class DataRequest(models.Model):

    BORANG_TYPE = [
        ('SERAHAN', 'Borang Serahan Data'),
        ('PINJAMAN', 'Borang Pinjaman Data'),
    ]

    STATUS_CHOICES = [
    ("Borang Telah Dihantar", "Borang Telah Dihantar"),
    ("Pengarah Bahagian Telah Sahkan", "Pengarah Bahagian Telah Sahkan"),
    ("Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik", "Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik"),
    ("Penugasan PIC", "Penugasan PIC"),
    ("Data Telah Di-email", "Data Telah Di-email"),
    ("Pemohon Telah Mengesahkan Data", "Pemohon Telah Mengesahkan Data"),
    ("Selesai", "Selesai"),
    ]

    borang_type = models.CharField(max_length=20, choices=BORANG_TYPE)

    pemohon = models.ForeignKey(User, on_delete=models.CASCADE)

    namapemohon = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    telefon = models.CharField(max_length=100, blank=True, null=True)

    komponen_data = models.TextField(blank=True, null=True)
    komponen_lain = models.CharField(max_length=200, blank=True, null=True)

    negeri = models.CharField(max_length=100)
    daerah = models.CharField(max_length=100, blank=True, null=True)
    mukim = models.CharField(max_length=100, blank=True, null=True)
    indeks = models.CharField(max_length=100, blank=True, null=True)

    jenis_data = models.CharField(max_length=255,blank=True, null=True)
    jenis_lain = models.CharField(max_length=200, blank=True, null=True)

    format_data = models.CharField(max_length=255,blank=True, null=True)
    format_lain = models.CharField(max_length=200, blank=True, null=True)

    unjuranKoordinat_data = models.CharField(max_length=255,blank=True, null=True)
    unjuranKoordinat_lain = models.CharField(max_length=200, blank=True, null=True)

    sumber_data = models.CharField(max_length=255,blank=True, null=True)
    sumber_lain = models.CharField(max_length=200, blank=True, null=True)

    meta_data = models.TextField(blank=True, null=True)


    nama_projek = models.TextField(max_length=100, blank=True, null=True)


    tujuan = models.TextField(max_length=200, blank=True, null=True)
    cacatan = models.TextField(max_length=200, blank=True, null=True)

    Setuju = models.BooleanField(default=False)
    nama = models.CharField(max_length=200, blank=True, null=True)
    Tarikh = models.CharField(max_length=50, blank=True, null=True)

    namaagensikerjasama = models.CharField(max_length=100, blank=True, null=True)
    namaprojek = models.CharField(max_length=100, blank=True, null=True)
    tarikhprojek = models.CharField(max_length=100, blank=True, null=True)

    namaagensiluar = models.CharField(max_length=100, blank=True, null=True)
    namaprojekluar = models.CharField(max_length=100, blank=True, null=True)
    tarikhprojekluar = models.CharField(max_length=100, blank=True, null=True)

    jenisdataformat = models.CharField(max_length=255,blank=True, null=True)
    
    klasifikasidata = models.CharField(max_length=255,blank=True, null=True)


    status = models.CharField(
        max_length=1000,
        choices=STATUS_CHOICES,
        default='Borang Telah Dihantar'
    )

    uploaded_file = models.FileField(
        upload_to="uploaded_data/",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

def __str__(self):
    return f"Request {self.id} - {self.borang_type}"


class LoginLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    login_time = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.login_time}"


class Bahagian(models.Model):
    nama = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nama

    class Meta:
        verbose_name_plural = "Bahagian"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(max_length=100, blank=True, null=True)
    bahagian = models.ForeignKey(
        Bahagian,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles",
    )

    def __str__(self):
        return f"{self.user.username} - {self.phone or ''}"


class Negeri(models.Model):
    nama = models.CharField(max_length=100)

    def __str__(self):
        return self.nama


class Daerah(models.Model):
    negeri = models.ForeignKey(Negeri, on_delete=models.CASCADE)
    nama = models.CharField(max_length=100)

    def __str__(self):
        return self.nama


class Mukim(models.Model):
    daerah = models.ForeignKey(Daerah, on_delete=models.CASCADE)
    nama = models.CharField(max_length=150)

    def __str__(self):
        return self.nama


class AbstractRequest(models.Model):
    """Shared base for SerahanRequest and PinjamanRequest."""

    pemohon = models.ForeignKey(User, on_delete=models.CASCADE)

    namapemohon = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    telefon = models.CharField(max_length=100, blank=True, null=True)

    komponen_data = models.TextField(blank=True, null=True)
    komponen_lain = models.CharField(max_length=200, blank=True, null=True)

    negeri = models.ForeignKey(Negeri, on_delete=models.PROTECT, null=True, blank=True)
    daerah = models.ForeignKey(Daerah, on_delete=models.PROTECT, null=True, blank=True)
    mukim = models.ForeignKey(Mukim, on_delete=models.PROTECT, null=True, blank=True)
    daerah_text = models.CharField(max_length=200, blank=True, null=True)
    mukim_text = models.CharField(max_length=200, blank=True, null=True)
    indeks = models.CharField(max_length=100, blank=True, null=True)

    uploaded_file = models.FileField(upload_to="uploaded_data/", null=True, blank=True)

    bahagian = models.ForeignKey(
        Bahagian,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_requests",
    )

    pic = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_pic",
    )

    status = models.CharField(max_length=200, default="Borang Telah Dihantar")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SerahanRequest(AbstractRequest):

    SERAHAN_STATUS = [
        ("Borang Telah Dihantar", "Borang Telah Dihantar"),
        ("Tidak Disokong Oleh Pengarah Bahagian", "Tidak Disokong Oleh Pengarah Bahagian"),
        ("Disokong Oleh Pengarah Bahagian", "Disokong Oleh Pengarah Bahagian"),
        ("Tidak Mendapat Kelulusan Pengarah BITG", "Tidak Mendapat Kelulusan Pengarah BITG"),
        ("Mendapat Kelulusan Pengarah BITG", "Mendapat Kelulusan Pengarah BITG"),
        ("Verifikasi Data Oleh PIC", "Verifikasi Data Oleh PIC"),
        ("Pembetulan Oleh Pemohon", "Pembetulan Oleh Pemohon"),
        ("Pengesahan Verifikasi", "Pengesahan Verifikasi"),
        ("Serahan Data", "Serahan Data"),
        ("Selesai", "Selesai"),
    ]

    status = models.CharField(
        max_length=200,
        choices=SERAHAN_STATUS,
        default="Borang Telah Dihantar",
    )

    jenis_data = models.CharField(max_length=255, blank=True, null=True)
    jenis_lain = models.CharField(max_length=200, blank=True, null=True)

    format_data = models.CharField(max_length=255, blank=True, null=True)
    format_lain = models.CharField(max_length=200, blank=True, null=True)

    unjuranKoordinat_data = models.CharField(max_length=255, blank=True, null=True)
    unjuranKoordinat_lain = models.CharField(max_length=200, blank=True, null=True)

    sumber_data = models.CharField(max_length=255, blank=True, null=True)
    sumber_lain = models.CharField(max_length=200, blank=True, null=True)

    meta_data = models.TextField(blank=True, null=True)

    namaagensi = models.CharField(max_length=100, blank=True, null=True)
    namaprojek = models.CharField(max_length=100, blank=True, null=True)
    tarikhprojek = models.CharField(max_length=100, blank=True, null=True)

    jenisdataformat = models.CharField(max_length=255, blank=True, null=True)
    klasifikasidata = models.CharField(max_length=255, blank=True, null=True)

    @property
    def borang_type(self):
        return "SERAHAN"

    def __str__(self):
        return f"SerahanRequest {self.id} - {self.namapemohon}"


class PinjamanRequest(AbstractRequest):

    PINJAMAN_STATUS = [
        ("Borang Telah Dihantar", "Borang Telah Dihantar"),
        ("Tidak Disokong Oleh Pengarah Bahagian", "Tidak Disokong Oleh Pengarah Bahagian"),
        ("Disokong Oleh Pengarah Bahagian", "Disokong Oleh Pengarah Bahagian"),
        ("Tidak Mendapat Kelulusan Pengarah BITG", "Tidak Mendapat Kelulusan Pengarah BITG"),
        ("Mendapat Kelulusan Pengarah BITG", "Mendapat Kelulusan Pengarah BITG"),
        ("Penugasan PIC Oleh Pengarah BITG", "Penugasan PIC Oleh Pengarah BITG"),
        ("Penyediaan Data", "Penyediaan Data"),
        ("Serahan Data", "Serahan Data"),
        ("Semakan Oleh Pemohon", "Semakan Oleh Pemohon"),
        ("Pembetulan Oleh Pemohon", "Pembetulan Oleh Pemohon"),
        ("Sahkan Penerimaan Data", "Sahkan Penerimaan Data"),
        ("Selesai", "Selesai"),
    ]

    status = models.CharField(
        max_length=200,
        choices=PINJAMAN_STATUS,
        default="Borang Telah Dihantar",
    )

    tujuan = models.TextField(max_length=200, blank=True, null=True)
    cacatan = models.TextField(max_length=200, blank=True, null=True)

    Setuju = models.BooleanField(default=False)
    nama = models.CharField(max_length=200, blank=True, null=True)
    Tarikh = models.CharField(max_length=50, blank=True, null=True)

    deadline = models.DateTimeField(blank=True, null=True)

    @property
    def borang_type(self):
        return "PINJAMAN"

    def __str__(self):
        return f"PinjamanRequest {self.id} - {self.namapemohon}"


class StatusLog(models.Model):

    BORANG_TYPE = [
        ("SERAHAN", "Borang Serahan Data"),
        ("PINJAMAN", "Borang Pinjaman Data"),
    ]

    borang_type = models.CharField(max_length=20, choices=BORANG_TYPE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    request_obj = GenericForeignKey("content_type", "object_id")

    status = models.CharField(max_length=200)
    ulasan = models.TextField(blank=True, null=True)
    sebab_tolak = models.TextField(blank=True, null=True)

    changed_by = models.ForeignKey(User, on_delete=models.PROTECT)
    changed_at = models.DateTimeField(auto_now_add=True)
    iteration = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-changed_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["borang_type", "status"]),
        ]

    def __str__(self):
        return f"StatusLog {self.id} - {self.borang_type} {self.object_id} - {self.status}"