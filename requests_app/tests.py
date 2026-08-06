"""End-to-end tests for the serahan and pinjaman data workflows.

Run with:  manage.py test --settings=dgp_system.test_settings requests_app
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from requests_app.models import SerahanRequest, PinjamanRequest, StatusLog

PASSWORD = "p@ssw0rd"


def make_user(username, group_name):
    user = User.objects.create_user(
        username=username, email=f"{username}@mysa.local", password=PASSWORD
    )
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


class FlowTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pemohon = make_user("pemohon", "Staff")
        cls.pb = make_user("pb", "Pengarah Bahagian")
        cls.bitg = make_user("bitg", "Pengarah BITG")
        cls.pengurus = make_user("pengurus", "Pengurus Pengkalan Data")
        cls.pic = make_user("pic", "PIC")

    def c(self, user):
        client = Client()
        client.force_login(user)
        return client

    # ---------- form payloads ----------

    def serah_payload(self, **over):
        data = {
            "namapemohon": "Ali Serah",
            "email": "ali@mysa.local",
            "telefon": "0123456789",
            "negeri": "KEDAH",
            "daerah": "BALING",
            "mukim": "Baling",
            "komponen_data": ["Jalan", "Sungai"],
            "jenis_data": ["Poligon"],
            "format_data": ["Shapefile"],
            "unjuranKoordinat_data": ["RSO"],
            "sumber_data": ["Peta Topo"],
            "indeks": "NB-1",
            "namaagensi": "Agensi Uji",
            "namaprojek": "Projek Uji",
            "tarikhprojek": "2026-01-01",
            "jenisdataformat": ["Digital"],
            "klasifikasidata": ["Terhad"],
        }
        data.update(over)
        return data

    def pinjam_payload(self, **over):
        data = {
            "namapemohon": "Ali Pinjam",
            "email": "ali@mysa.local",
            "telefon": "0123456789",
            "negeri": "SABAH",
            "daerah": "KOTA KINABALU",
            "mukim": "MUKIM",
            "komponen_data": ["Jalan"],
            "indeks": "SB-1",
            "tujuan": "Kajian tesis",
            "cacatan": "Tiada",
            "Setuju": "on",
            "nama": "Ali Pinjam",
            "Tarikh": "2026-01-01",
        }
        data.update(over)
        return data

    # ---------- flow helpers ----------

    def submit_serah(self, **over):
        r = self.c(self.pemohon).post(
            reverse("borang_serahan"), self.serah_payload(**over)
        )
        obj = SerahanRequest.objects.latest("id")
        return r, obj

    def submit_pinjam(self, **over):
        r = self.c(self.pemohon).post(
            reverse("borang_pinjaman"), self.pinjam_payload(**over)
        )
        obj = PinjamanRequest.objects.latest("id")
        return r, obj

    def approve(self, obj, user, **data):
        return self.c(user).post(
            reverse("approve_request", args=[obj.borang_type, obj.id]), data
        )

    def assign(self, obj, user, pic):
        return self.c(user).post(
            reverse("assign_pic", args=[obj.borang_type, obj.id]),
            {"pic": pic.id},
        )

    def verify(self, obj, user, action, **data):
        data.setdefault("action", action)
        return self.c(user).post(
            reverse("verify_data", args=[obj.borang_type, obj.id]), data
        )

    def upload(self, obj, user, filename="data.txt", content=b"data"):
        return self.c(user).post(
            reverse("upload_data", args=[obj.borang_type, obj.id]),
            {"data_file": SimpleUploadedFile(filename, content)},
        )

    def log_chain(self, obj):
        return list(
            StatusLog.objects.filter(
                object_id=obj.id, borang_type=obj.borang_type
            ).order_by("id").values_list("status", flat=True)
        )

    # ---------- serah happy path ----------

    def test_serah_happy_path(self):
        _, s = self.submit_serah()
        self.assertEqual(s.status, "Borang Telah Dihantar")

        self.approve(s, self.pb, action="approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Disokong Oleh Pengarah Bahagian")

        self.approve(s, self.bitg, action="approve", ulasan="OK")
        s.refresh_from_db()
        self.assertEqual(s.status, "Mendapat Kelulusan Pengarah BITG")

        self.assign(s, self.pengurus, self.pic)
        s.refresh_from_db()
        self.assertEqual(s.status, "Verifikasi Data Oleh PIC")
        self.assertEqual(s.pic, self.pic)

        self.verify(s, self.pic, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Pengesahan Verifikasi")

        self.verify(s, self.pengurus, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Selesai")

        self.assertEqual(
            self.log_chain(s),
            [
                "Borang Telah Dihantar",
                "Disokong Oleh Pengarah Bahagian",
                "Mendapat Kelulusan Pengarah BITG",
                "Verifikasi Data Oleh PIC",
                "Pengesahan Verifikasi",
                "Serahan Data",
                "Selesai",
            ],
        )

    def test_serah_pb_rejection_terminal(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="reject", sebab_tolak="Data tidak lengkap")
        s.refresh_from_db()
        self.assertEqual(s.status, "Tidak Disokong Oleh Pengarah Bahagian")
        log = StatusLog.objects.filter(
            object_id=s.id, borang_type="SERAHAN"
        ).order_by("id").last()
        self.assertEqual(log.sebab_tolak, "Data tidak lengkap")

        resp = self.approve(s, self.pb, action="approve")
        self.assertEqual(resp.status_code, 403)
        s.refresh_from_db()
        self.assertEqual(s.status, "Tidak Disokong Oleh Pengarah Bahagian")

    def test_serah_pic_pembetulan_loop(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.pengurus, self.pic)

        self.verify(s, self.pic, "reject", sebab_tolak="Salah unjuran")
        s.refresh_from_db()
        self.assertEqual(s.status, "Pembetulan Data")

        self.verify(s, self.pic, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Pengesahan Verifikasi")

        self.verify(s, self.pengurus, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Selesai")

    def test_serah_pengurus_reject_back_to_verify(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.pengurus, self.pic)
        self.verify(s, self.pic, "approve")

        self.verify(s, self.pengurus, "reject", sebab_tolak="Semak semula")
        s.refresh_from_db()
        self.assertEqual(s.status, "Verifikasi Data Oleh PIC")

    def test_serah_bitg_reject_uses_correct_status(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="reject", sebab_tolak="Data tidak lengkap")
        s.refresh_from_db()
        self.assertEqual(s.status, "Tidak Mendapat Kelulusan Pengarah BITG")
        log = StatusLog.objects.filter(
            object_id=s.id, borang_type="SERAHAN"
        ).order_by("id").last()
        self.assertEqual(log.sebab_tolak, "Data tidak lengkap")

    def test_pinjam_bitg_reject_uses_correct_status(self):
        _, p = self.submit_pinjam()
        self.approve(p, self.pb, action="approve")
        self.approve(p, self.bitg, action="reject", sebab_tolak="Permintaan tidak lengkap")
        p.refresh_from_db()
        self.assertEqual(p.status, "Tidak Mendapat Kelulusan Pengarah BITG")

    # ---------- pinjam happy path ----------

    def test_pinjam_happy_path(self):
        _, p = self.submit_pinjam()
        self.assertEqual(p.status, "Borang Telah Dihantar")

        self.approve(p, self.pb, action="approve")
        p.refresh_from_db()
        self.assertEqual(p.status, "Disokong Oleh Pengarah Bahagian")

        self.approve(p, self.bitg, action="approve", ulasan="Lulus")
        p.refresh_from_db()
        self.assertEqual(p.status, "Mendapat Kelulusan Pengarah BITG")

        self.assign(p, self.bitg, self.pic)
        p.refresh_from_db()
        self.assertEqual(p.status, "Penyediaan Data")
        self.assertEqual(p.pic, self.pic)
        self.assertIsNotNone(p.deadline)

        self.upload(p, self.pic)
        p.refresh_from_db()
        self.assertEqual(p.status, "Serahan Data")
        self.assertTrue(p.uploaded_file)

        self.verify(p, self.pemohon, "approve")
        p.refresh_from_db()
        self.assertEqual(p.status, "Selesai")

        self.assertEqual(
            self.log_chain(p),
            [
                "Borang Telah Dihantar",
                "Disokong Oleh Pengarah Bahagian",
                "Mendapat Kelulusan Pengarah BITG",
                "Penyediaan Data",
                "Serahan Data",
                "Sahkan Penerimaan Data",
                "Selesai",
            ],
        )

    def test_pinjam_pemohon_reject_loop(self):
        _, p = self.submit_pinjam()
        self.approve(p, self.pb, action="approve")
        self.approve(p, self.bitg, action="approve")
        self.assign(p, self.bitg, self.pic)
        self.upload(p, self.pic)
        p.refresh_from_db()
        self.assertEqual(p.status, "Serahan Data")

        self.verify(p, self.pemohon, "reject", sebab_tolak="Data tidak tepat")
        p.refresh_from_db()
        self.assertEqual(p.status, "Penyediaan Data")
        logs = self.log_chain(p)
        self.assertIn("Pembetulan Oleh Pemohon", logs)

        self.upload(p, self.pic)
        p.refresh_from_db()
        self.assertEqual(p.status, "Serahan Data")

        self.verify(p, self.pemohon, "approve")
        p.refresh_from_db()
        self.assertEqual(p.status, "Selesai")

    # ---------- permissions ----------

    def test_staff_cannot_approve(self):
        _, s = self.submit_serah()
        resp = self.approve(s, self.pemohon, action="approve")
        self.assertEqual(resp.status_code, 403)

    def test_pb_cannot_approve_bitg_stage(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        resp = self.approve(s, self.pb, action="approve")
        self.assertEqual(resp.status_code, 403)

    def test_wrong_borang_type_returns_forbidden(self):
        _, s = self.submit_serah()
        resp = self.c(self.pb).post(
            reverse("approve_request", args=["PINJAMAN", s.id]),
            {"action": "approve"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_pic_assignment_only_for_assigned_pic(self):
        other_pic = make_user("pic2", "PIC")
        _, p = self.submit_pinjam()
        self.approve(p, self.pb, action="approve")
        self.approve(p, self.bitg, action="approve")
        self.assign(p, self.bitg, self.pic)

        resp = self.c(other_pic).post(
            reverse("upload_data", args=[p.borang_type, p.id]),
            {"data_file": SimpleUploadedFile("x.txt", b"x")},
        )
        self.assertEqual(resp.status_code, 403)
        p.refresh_from_db()
        self.assertEqual(p.status, "Penyediaan Data")

    # ---------- cross-table id collision ----------

    def test_same_id_serah_and_pinjam_route_independently(self):
        _, s = self.submit_serah()
        _, p = self.submit_pinjam()
        self.assertEqual(s.id, p.id, "both tables should start ids at 1")

        self.approve(s, self.pb, action="approve")
        self.approve(p, self.pb, action="approve")
        s.refresh_from_db()
        p.refresh_from_db()
        self.assertEqual(s.status, "Disokong Oleh Pengarah Bahagian")
        self.assertEqual(p.status, "Disokong Oleh Pengarah Bahagian")

    # ---------- kawasan lain-lain ----------

    def test_serah_lain_kawasan_stored_as_text(self):
        _, s = self.submit_serah(
            daerah="LAIN", daerah_lain="Daerah Khas", mukim="LAIN", mukim_lain="Mukim Khas"
        )
        self.assertIsNone(s.daerah)
        self.assertIsNone(s.mukim)
        self.assertEqual(s.daerah_text, "Daerah Khas")
        self.assertEqual(s.mukim_text, "Mukim Khas")

    def test_pinjam_lain_kawasan_stored_as_text(self):
        _, p = self.submit_pinjam(
            daerah="LAIN", daerah_lain="Daerah Khas", mukim="LAIN", mukim_lain="Mukim Khas"
        )
        self.assertIsNone(p.daerah)
        self.assertEqual(p.daerah_text, "Daerah Khas")
        self.assertEqual(p.mukim_text, "Mukim Khas")

    # ---------- notifications ----------

    def test_submit_sends_emails(self):
        from django.core import mail

        _, s = self.submit_serah()
        subjects = [m.subject for m in mail.outbox]
        self.assertIn("Permohonan Serahan Diterima", subjects)
        self.assertIn("Permohonan Baru Memerlukan Kelulusan", subjects)

    # ---------- applicant auto-fill ----------

    def test_pemohon_details_auto_filled_from_logged_in_user(self):
        _, s = self.submit_serah(namapemohon="HACKED", email="hack@x.com")
        self.assertEqual(s.namapemohon, self.pemohon.username)
        self.assertEqual(s.email, self.pemohon.email)

        _, p = self.submit_pinjam(namapemohon="HACKED", email="hack@x.com")
        self.assertEqual(p.namapemohon, self.pemohon.username)
        self.assertEqual(p.email, self.pemohon.email)

    def test_register_stores_phone_in_profile(self):
        c = Client()
        resp = c.post(
            reverse("register"),
            {
                "fullname": "Test User",
                "username": "newuser",
                "email": "new@x.com",
                "password": "password123",
                "confirm": "password123",
                "telefon": "0199999999",
            },
        )
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="newuser")
        self.assertEqual(user.first_name, "Test User")
        self.assertEqual(user.profile.phone, "0199999999")
