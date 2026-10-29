"""End-to-end tests for the serahan and pinjaman data workflows.

Run with:  manage.py test --settings=dgp_system.test_settings requests_app
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from requests_app.models import SerahanRequest, PinjamanRequest, StatusLog, Bahagian, UserProfile
from requests_app.views import annotate_steps

PASSWORD = "p@ssw0rd"


def make_user(username, group_name, bahagian=None):
    user = User.objects.create_user(
        username=username, email=f"{username}@mysa.local", password=PASSWORD
    )
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    if bahagian is not None:
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.bahagian = bahagian
        profile.save()
    return user


class FlowDataMixin:
    """Shared fixtures, clients and form-payload helpers (not a TestCase)."""

    @classmethod
    def setUpTestData(cls):
        cls.bs, _ = Bahagian.objects.get_or_create(nama="BS")
        cls.bkp, _ = Bahagian.objects.get_or_create(nama="BKP")
        cls.bitg_b, _ = Bahagian.objects.get_or_create(nama="BITG")
        cls.pemohon = make_user("pemohon", "Staff", bahagian=cls.bs)
        cls.pb = make_user("pb", "Pengarah Bahagian", bahagian=cls.bs)
        cls.bitg = make_user("bitg", "Pengarah Bahagian", bahagian=cls.bitg_b)
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
            "komponen_data": ["Jalan"],
            "kat_0_negeri": "SABAH",
            "kat_0_daerah": "KOTA KINABALU",
            "kat_0_mukim": "MUKIM",
            "kat_0_tahun": "2026",
            "tujuan": "Kajian tesis",
            "cacatan": "Tiada",
            "Setuju": "on",
            "Tarikh": "2026-01-01",
        }
        data.update(over)
        return data

    # ---------- submission helpers ----------

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


class FlowTestBase(FlowDataMixin, TestCase):
    # ---------- flow helpers ----------

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

    def hantar(self, s, user=None):
        user = user or self.pemohon
        return self.c(user).post(
            reverse("pemohon_hantar_data", args=[s.id]), {"catatan": "emel"}
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

        self.assign(s, self.bitg, self.pic)
        s.refresh_from_db()
        self.assertEqual(s.status, "Penugasan PIC")
        self.assertEqual(s.pic, self.pic)

        self.hantar(s)
        s.refresh_from_db()
        self.assertEqual(s.status, "Pemohon Hantar Data")

        self.verify(s, self.pic, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Verifikasi Data")

        self.verify(s, self.pic, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Selesai")

        self.assertEqual(
            self.log_chain(s),
            [
                "Borang Telah Dihantar",
                "Disokong Oleh Pengarah Bahagian",
                "Mendapat Kelulusan Pengarah BITG",
                "Penugasan PIC",
                "Pemohon Hantar Data",
                "Verifikasi Data",
                "Sahkan Penerimaan Data",
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
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)

        self.verify(s, self.pic, "reject", sebab_tolak="Salah unjuran")
        s.refresh_from_db()
        self.assertEqual(s.status, "Pembetulan Oleh Pemohon")
        log = StatusLog.objects.filter(
            object_id=s.id, borang_type="SERAHAN"
        ).order_by("id").last()
        self.assertEqual(log.sebab_tolak, "Salah unjuran")

        s2_id = s.id
        resp = self.c(self.pemohon).post(
            reverse("borang_serahan_edit", args=[s.id]),
            self.serah_payload(**{"komponen_data": ["Jalan", "Sungai", "DEM"]}),
        )
        self.assertEqual(resp.status_code, 302)
        s.refresh_from_db()
        self.assertEqual(s.id, s2_id)
        self.assertEqual(s.status, "Borang Telah Dihantar")
        self.assertIsNone(s.pic)
        self.assertEqual(s.komponen_data, "Jalan, Sungai, DEM")

        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        self.verify(s, self.pic, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Verifikasi Data")

        self.verify(s, self.pic, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Selesai")

    def test_serah_edit_guards(self):
        _, s = self.submit_serah()
        other = make_user("pemohon2", "Staff")

        resp = self.c(other).post(
            reverse("borang_serahan_edit", args=[s.id]), self.serah_payload()
        )
        self.assertEqual(resp.status_code, 302)
        s.refresh_from_db()
        self.assertEqual(s.status, "Borang Telah Dihantar")

        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        self.verify(s, self.pic, "reject")
        s.refresh_from_db()
        self.assertEqual(s.status, "Pembetulan Oleh Pemohon")

        wrong = make_user("pemohon3", "Staff")
        resp = self.c(wrong).post(
            reverse("borang_serahan_edit", args=[s.id]), self.serah_payload()
        )
        self.assertEqual(resp.status_code, 302)
        s.refresh_from_db()
        self.assertEqual(s.status, "Pembetulan Oleh Pemohon")

        self.approve(s, self.pb, action="approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Pembetulan Oleh Pemohon")

    def test_serah_pic_cannot_act_during_pemohon_correction(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        self.verify(s, self.pic, "reject")
        s.refresh_from_db()
        self.assertEqual(s.status, "Pembetulan Oleh Pemohon")

        resp = self.verify(s, self.pic, "approve")
        self.assertEqual(resp.status_code, 403)
        s.refresh_from_db()
        self.assertEqual(s.status, "Pembetulan Oleh Pemohon")

    def test_serah_edit_page_renders_with_prefill(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        self.verify(s, self.pic, "reject", sebab_tolak="Salah unjuran")
        s.refresh_from_db()

        resp = self.c(self.pemohon).get(
            reverse("borang_serahan_edit", args=[s.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "HANTAR SEMULA")
        self.assertContains(resp, 'name="komponen_data" value="Jalan" checked')
        self.assertContains(resp, "Mengedit Permohonan")

    def test_serah_pic_reject_sends_email_to_pemohon(self):
        from django.core import mail

        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        mail.outbox.clear()

        self.verify(s, self.pic, "reject", sebab_tolak="Data tidak lengkap")
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(all(sub.startswith("[TINDAKAN DIPERLUKAN] PERMOHONAN SERAHAN DATA") for sub in subjects))
        bodies = " ".join(m.body for m in mail.outbox)
        self.assertIn("pembetulan", bodies.lower())
        tos = [email for m in mail.outbox for email in m.to]
        self.assertIn(self.pemohon.email, tos)

    def test_serah_pic_accept_only_for_assigned_pic(self):
        other_pic = make_user("pic2", "PIC")
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        self.verify(s, self.pic, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Verifikasi Data")

        resp = self.verify(s, other_pic, "approve")
        self.assertEqual(resp.status_code, 403)
        s.refresh_from_db()
        self.assertEqual(s.status, "Verifikasi Data")

        self.verify(s, self.pic, "approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Selesai")

    def test_serah_hantar_data_guard(self):
        other = make_user("pemohon2", "Staff")
        _, s = self.submit_serah()
        resp = self.hantar(s, user=other)
        self.assertEqual(resp.status_code, 403)
        s.refresh_from_db()
        self.assertEqual(s.status, "Borang Telah Dihantar")

        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        s.refresh_from_db()
        self.assertEqual(s.status, "Penugasan PIC")

        self.hantar(s)
        s.refresh_from_db()
        self.assertEqual(s.status, "Pemohon Hantar Data")

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
        self.assertEqual(p.status, "Penugasan PIC")
        self.assertEqual(p.pic, self.pic)
        self.assertIsNotNone(p.deadline)

        self.verify(p, self.pic, "approve", ulasan="Hantar emel")
        p.refresh_from_db()
        self.assertEqual(p.status, "PIC Hantar Data")

        self.verify(p, self.pemohon, "approve", ulasan="Data diterima")
        p.refresh_from_db()
        self.assertEqual(p.status, "Selesai")

        self.assertEqual(
            self.log_chain(p),
            [
                "Borang Telah Dihantar",
                "Disokong Oleh Pengarah Bahagian",
                "Mendapat Kelulusan Pengarah BITG",
                "Penugasan PIC",
                "PIC Hantar Data",
                "Pemohon Semak Data",
                "Pemohon Sahkan Penerimaan Data",
                "Selesai",
            ],
        )

    def test_pinjam_pemohon_reject_returns_to_pic(self):
        _, p = self.submit_pinjam()
        self.approve(p, self.pb, action="approve")
        self.approve(p, self.bitg, action="approve")
        self.assign(p, self.bitg, self.pic)
        self.verify(p, self.pic, "approve")
        p.refresh_from_db()
        self.assertEqual(p.status, "PIC Hantar Data")

        self.verify(p, self.pemohon, "reject", sebab_tolak="Data tidak tepat")
        p.refresh_from_db()
        self.assertEqual(p.status, "Penugasan PIC")
        self.assertNotIn("Pembetulan Oleh Pemohon", self.log_chain(p))

        self.verify(p, self.pic, "approve")
        p.refresh_from_db()
        self.assertEqual(p.status, "PIC Hantar Data")

        self.verify(p, self.pemohon, "approve")
        p.refresh_from_db()
        self.assertEqual(p.status, "Selesai")

    def test_pinjam_pb_reject_then_edit_resubmit(self):
        _, p = self.submit_pinjam()
        self.approve(p, self.pb, action="reject", sebab_tolak="Data tidak lengkap")
        p.refresh_from_db()
        self.assertEqual(p.status, "Tidak Disokong Oleh Pengarah Bahagian")

        p_id = p.id
        resp = self.c(self.pemohon).post(
            reverse("borang_pinjaman_edit", args=[p.id]),
            self.pinjam_payload(**{"tujuan": "Kajian baru"}),
        )
        self.assertEqual(resp.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.id, p_id)
        self.assertEqual(p.status, "Borang Telah Dihantar")
        self.assertEqual(p.tujuan, "Kajian baru")

        self.approve(p, self.pb, action="approve")
        self.approve(p, self.bitg, action="approve")
        self.assign(p, self.bitg, self.pic)
        p.refresh_from_db()
        self.assertEqual(p.status, "Penugasan PIC")

    def test_pinjam_edit_page_renders_with_prefill(self):
        _, p = self.submit_pinjam()
        self.approve(p, self.pb, action="reject", sebab_tolak="x")
        resp = self.c(self.pemohon).get(
            reverse("borang_pinjaman_edit", args=[p.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "HANTAR SEMULA")
        self.assertContains(resp, 'name="komponen_data" value="Jalan" data-kat="0" checked')

    def test_pinjam_timeline_entries(self):
        _, p = self.submit_pinjam()
        self.approve(p, self.pb, action="approve")
        self.approve(p, self.bitg, action="approve")
        self.assign(p, self.bitg, self.pic)
        self.verify(p, self.pic, "approve", ulasan="Dihantar via emel")
        self.verify(p, self.pemohon, "approve", ulasan="Semua OK")
        p.refresh_from_db()

        resp = self.c(self.pemohon).get(
            reverse("request_detail", args=["PINJAMAN", p.id])
        )
        html = resp.content.decode()
        self.assertIn("Penugasan PIC", html)
        self.assertIn(f"PIC: {self.pic.username}", html)
        self.assertIn("PIC Hantar Data", html)
        self.assertIn("Pemohon Semak Data", html)
        self.assertIn("Pemohon Sahkan Penerimaan Data", html)
        self.assertIn("Selesai", html)
        self.assertIn("Dihantar via emel", html)
        self.assertIn("Semua OK", html)

    def test_pic_confirm_only_for_assigned_pic(self):
        other_pic = make_user("pic2", "PIC")
        _, p = self.submit_pinjam()
        self.approve(p, self.pb, action="approve")
        self.approve(p, self.bitg, action="approve")
        self.assign(p, self.bitg, self.pic)

        resp = self.verify(p, other_pic, "approve")
        self.assertEqual(resp.status_code, 403)
        p.refresh_from_db()
        self.assertEqual(p.status, "Penugasan PIC")

        self.verify(p, self.pic, "approve")
        p.refresh_from_db()
        self.assertEqual(p.status, "PIC Hantar Data")

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
            kat_0_daerah="LAIN", kat_0_daerah_lain="Daerah Khas",
            kat_0_mukim="LAIN", kat_0_mukim_lain="Mukim Khas",
        )
        self.assertIsNone(p.daerah)
        self.assertEqual(p.daerah_text, "Daerah Khas")
        self.assertEqual(p.mukim_text, "Mukim Khas")

    # ---------- notifications ----------

    def test_submit_sends_emails(self):
        from django.core import mail

        _, s = self.submit_serah()
        subjects = [m.subject for m in mail.outbox]
        self.assertEqual(len(mail.outbox), 2)
        self.assertTrue(all(sub.startswith("[TINDAKAN DIPERLUKAN] PERMOHONAN SERAHAN DATA") for sub in subjects))
        bodies = " ".join(m.body for m in mail.outbox)
        self.assertIn("Borang Telah Dihantar", bodies)
        self.assertIn("Pengarah Bahagian", bodies)

    def test_timeline_renders_on_status_and_admin_pages(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve", ulasan="OK")

        resp = self.c(self.pemohon).get(reverse("status"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "req-table")
        self.assertContains(resp, 'id="q"')

        resp = self.c(self.bitg).get(reverse("admin_borang"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "req-table")

    def test_request_detail_fragment_renders_timeline_and_actions(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve", ulasan="OK")

        resp = self.c(self.bitg).get(
            reverse("request_detail", args=["SERAHAN", s.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "status-timeline")
        self.assertContains(resp, "Ulasan: OK")
        self.assertContains(resp, "Mendapat Kelulusan Pengarah BITG")

        resp = self.c(self.pemohon).get(
            reverse("request_detail", args=["SERAHAN", s.id])
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "status-timeline")

    def test_status_logs_newest_first(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        self.verify(s, self.pic, "approve")
        self.verify(s, self.pic, "approve")
        s.refresh_from_db()

        annotate_steps(s)
        statuses = [log.status for log in s.status_logs]
        self.assertEqual(statuses[0], "Selesai")
        self.assertEqual(statuses[-1], "Borang Telah Dihantar")
        self.assertEqual(statuses, self.log_chain(s)[::-1])

    def test_status_logs_correct_role_per_step(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        self.verify(s, self.pic, "approve")
        self.verify(s, self.pic, "approve")
        s.refresh_from_db()

        annotate_steps(s)
        expected = [
            ("Borang Telah Dihantar", self.pemohon),
            ("Disokong Oleh Pengarah Bahagian", self.pb),
            ("Mendapat Kelulusan Pengarah BITG", self.bitg),
            ("Penugasan PIC", self.bitg),
            ("Pemohon Hantar Data", self.pemohon),
            ("Verifikasi Data", self.pic),
            ("Sahkan Penerimaan Data", self.pic),
            ("Selesai", self.pic),
        ]
        for log, (status, actor) in zip(reversed(s.status_logs), expected):
            self.assertEqual(log.status, status)
            self.assertEqual(log.changed_by_id, actor.id)

    def test_timeline_renders_role_label(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        resp = self.c(self.pemohon).get(
            reverse("request_detail", args=["SERAHAN", s.id])
        )
        html = resp.content.decode()
        self.assertIn("Pengarah Bahagian", html)
        self.assertIn("Staff", html)

    def test_timeline_serah_special_labels(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        self.approve(s, self.bitg, action="approve")
        self.assign(s, self.bitg, self.pic)
        self.hantar(s)
        self.verify(s, self.pic, "approve")
        self.verify(s, self.pic, "approve")
        s.refresh_from_db()

        resp = self.c(self.pemohon).get(
            reverse("request_detail", args=["SERAHAN", s.id])
        )
        html = resp.content.decode()
        self.assertIn("(Pengarah BITG)", html)
        self.assertIn("Penugasan PIC", html)
        self.assertIn(f"PIC: {self.pic.username}", html)
        self.assertIn("Pemohon Hantar Data", html)
        self.assertIn("Verifikasi Data", html)
        self.assertNotIn("Pengesahan Verifikasi", html)

    def test_request_detail_forbidden_for_outsider(self):
        _, s = self.submit_serah()
        other = make_user("lain", "Staff")
        resp = self.c(other).get(
            reverse("request_detail", args=["SERAHAN", s.id])
        )
        self.assertEqual(resp.status_code, 403)

    def test_requests_list_search_and_pagination(self):
        ids = []
        for i in range(3):
            _, s = self.submit_serah(komponen_data=[f"Jalan{i}"])
            ids.append(s.id)
        newest = max(ids)

        resp = self.c(self.pemohon).get(reverse("requests_list"), {"scope": "my"})
        data = resp.json()
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["rows"]), 3)
        self.assertEqual(data["rows"][0]["id"], newest)

        resp = self.c(self.pemohon).get(
            reverse("requests_list"), {"scope": "my", "q": str(ids[1])}
        )
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["rows"][0]["id"], ids[1])

        resp = self.c(self.pemohon).get(
            reverse("requests_list"), {"scope": "my", "per_page": 10, "page": 1}
        )
        self.assertEqual(resp.status_code, 200)

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
                "bahagian": self.bs.id,
            },
        )
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="newuser")
        self.assertEqual(user.first_name, "Test User")
        self.assertEqual(user.profile.phone, "0199999999")
        self.assertEqual(user.profile.bahagian, self.bs)

    def test_register_requires_bahagian(self):
        c = Client()
        resp = c.post(
            reverse("register"),
            {
                "fullname": "Test User",
                "username": "nobahagian",
                "email": "nb@x.com",
                "password": "password123",
                "confirm": "password123",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(User.objects.filter(username="nobahagian").exists())

    # ---------- bahagian routing ----------

    def test_serah_snapshot_bahagian(self):
        _, s = self.submit_serah()
        self.assertEqual(s.bahagian, self.bs)

    def test_duplicate_serah_submission_blocked(self):
        _, s1 = self.submit_serah()
        before = SerahanRequest.objects.filter(pemohon=self.pemohon).count()
        self.assertEqual(before, 1)

        r = self.c(self.pemohon).post(
            reverse("borang_serahan"), self.serah_payload()
        )
        self.assertEqual(r.status_code, 302)
        after = SerahanRequest.objects.filter(pemohon=self.pemohon).count()
        self.assertEqual(after, 1)
        self.assertEqual(SerahanRequest.objects.latest("id").id, s1.id)

    def test_distinct_serah_submission_allowed(self):
        self.submit_serah()
        self.submit_serah(komponen_data=["DEM"])
        self.assertEqual(
            SerahanRequest.objects.filter(pemohon=self.pemohon).count(), 2
        )

    def test_duplicate_pinjam_submission_blocked(self):
        _, p1 = self.submit_pinjam()
        r = self.c(self.pemohon).post(
            reverse("borang_pinjaman"), self.pinjam_payload()
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(PinjamanRequest.objects.filter(pemohon=self.pemohon).count(), 1)
        self.assertEqual(PinjamanRequest.objects.latest("id").id, p1.id)

    def test_pb_dashboard_filters_by_bahagian(self):
        pb_other = make_user("pb_bkp", "Pengarah Bahagian", bahagian=self.bkp)
        _, s = self.submit_serah()

        resp = self.c(self.pb).get(reverse("requests_list"), {"scope": "pb"})
        self.assertEqual(resp.status_code, 200)
        ids = [r["id"] for r in resp.json()["rows"]]
        self.assertIn(s.id, ids)

        resp = self.c(pb_other).get(reverse("requests_list"), {"scope": "pb"})
        ids = [r["id"] for r in resp.json()["rows"]]
        self.assertNotIn(s.id, ids)

    def test_pb_dashboard_renders_table(self):
        resp = self.c(self.pb).get(reverse("pengarah_dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "req-table")
        self.assertContains(resp, 'id="q"')

    def test_pb_cannot_approve_foreign_bahagian(self):
        pb_other = make_user("pb_bkp", "Pengarah Bahagian", bahagian=self.bkp)
        _, s = self.submit_serah()

        resp = self.approve(s, pb_other, action="approve")
        self.assertEqual(resp.status_code, 403)
        s.refresh_from_db()
        self.assertEqual(s.status, "Borang Telah Dihantar")

        self.approve(s, self.pb, action="approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Disokong Oleh Pengarah Bahagian")

    def test_pb_without_bitg_bahagian_cannot_do_bitg_approval(self):
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")
        s.refresh_from_db()
        self.assertEqual(s.status, "Disokong Oleh Pengarah Bahagian")

        resp = self.approve(s, self.pb, action="approve")
        self.assertEqual(resp.status_code, 403)
        s.refresh_from_db()
        self.assertEqual(s.status, "Disokong Oleh Pengarah Bahagian")

        self.approve(s, self.bitg, action="approve", ulasan="OK")
        s.refresh_from_db()
        self.assertEqual(s.status, "Mendapat Kelulusan Pengarah BITG")

    def test_bitg_pb_dashboard_shows_both_queues(self):
        pemohon_bitg = make_user("pemohon_bitg", "Staff", bahagian=self.bitg_b)
        r = self.c(pemohon_bitg).post(
            reverse("borang_serahan"), self.serah_payload()
        )
        s = SerahanRequest.objects.latest("id")
        self.assertEqual(s.bahagian, self.bitg_b)

        resp = self.c(self.bitg).get(reverse("requests_list"), {"scope": "bitg"})
        ids = [r["id"] for r in resp.json()["rows"]]
        self.assertIn(s.id, ids)

        _, s2 = self.submit_serah()
        resp = self.c(self.bitg).get(reverse("requests_list"), {"scope": "bitg"})
        ids = [r["id"] for r in resp.json()["rows"]]
        self.assertNotIn(s2.id, ids)

        self.approve(s2, self.pb, action="approve")
        s2.refresh_from_db()
        self.assertEqual(s2.status, "Disokong Oleh Pengarah Bahagian")

        resp = self.c(self.bitg).get(reverse("requests_list"), {"scope": "bitg"})
        ids = [r["id"] for r in resp.json()["rows"]]
        self.assertIn(s2.id, ids)

    def test_bitg_pb_can_approve_all_departments(self):
        pb_bkp = make_user("pb_bkp2", "Pengarah Bahagian", bahagian=self.bkp)
        pemohon_bkp = make_user("pemohon_bkp", "Staff", bahagian=self.bkp)
        _, s = self.submit_serah()
        self.approve(s, self.pb, action="approve")

        self.c(pemohon_bkp).post(reverse("borang_serahan"), self.serah_payload())
        s2 = SerahanRequest.objects.latest("id")
        self.assertEqual(s2.bahagian, self.bkp)

        self.approve(s2, pb_bkp, action="approve")
        s2.refresh_from_db()
        self.assertEqual(s2.status, "Disokong Oleh Pengarah Bahagian")

        self.approve(s2, self.bitg, action="approve", ulasan="OK")
        s2.refresh_from_db()
        self.assertEqual(s2.status, "Mendapat Kelulusan Pengarah BITG")


class AdminUserSessionIsolationTest(TestCase):
    """Admin (/admin) and normal-user (/) logins must be independent."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            "sysadmin", "sysadmin@mysa.local", PASSWORD
        )
        cls.staff = User.objects.create_user(
            "staffadmin", "staffadmin@mysa.local", PASSWORD
        )
        cls.staff.is_staff = True
        cls.staff.save()
        from django.contrib.auth.models import Permission

        cls.staff.user_permissions.add(
            Permission.objects.get(codename="view_user", content_type__app_label="auth")
        )
        cls.regular = User.objects.create_user(
            "regular", "regular@mysa.local", PASSWORD
        )

    def admin_login(self, c, username="sysadmin"):
        return c.post(
            "/admin/login/",
            {"username": username, "password": PASSWORD, "next": "/admin/"},
        )

    def assert_admin_logged_in(self, c):
        r = c.get("/admin/", follow=True)
        self.assertEqual(r.status_code, 200)

    def assert_admin_logged_out(self, c):
        r = c.get("/admin/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/admin/login/", r.url)

    def test_admin_login_does_not_grant_user_ui_access(self):
        c = Client()
        r = self.admin_login(c)
        self.assertEqual(r.status_code, 302)
        self.assert_admin_logged_in(c)
        # user UI still requires a separate login
        r2 = c.get(reverse("home"))
        self.assertEqual(r2.status_code, 302)
        self.assertTrue(r2.url.startswith("/"))

    def test_user_login_does_not_grant_admin_access(self):
        c = Client()
        c.post(reverse("login"), {"username": "regular", "password": PASSWORD})
        self.assertEqual(c.get(reverse("home")).status_code, 200)
        self.assert_admin_logged_out(c)

    def test_admin_logout_preserves_user_session(self):
        c = Client()
        c.post(reverse("login"), {"username": "regular", "password": PASSWORD})
        self.admin_login(c)
        r = c.post("/admin/logout/")
        self.assertEqual(r.status_code, 302)
        self.assert_admin_logged_out(c)
        # user session untouched
        self.assertEqual(c.get(reverse("home")).status_code, 200)

    def test_user_logout_preserves_admin_session(self):
        c = Client()
        self.admin_login(c)
        c.post(reverse("login"), {"username": "regular", "password": PASSWORD})
        r = c.get(reverse("logout"))
        self.assertEqual(r.status_code, 302)
        # admin session untouched
        self.assert_admin_logged_in(c)
        # user session gone
        r2 = c.get(reverse("home"))
        self.assertEqual(r2.status_code, 302)

    def test_staff_user_can_login_admin(self):
        c = Client()
        r = self.admin_login(c, username="staffadmin")
        self.assertEqual(r.status_code, 302)
        self.assert_admin_logged_in(c)

    def test_non_staff_user_cannot_login_admin(self):
        c = Client()
        r = self.admin_login(c, username="regular")
        # invalid form re-rendered; no admin session created
        self.assertEqual(r.status_code, 200)
        self.assert_admin_logged_out(c)

    def test_direct_access_to_admin_pages_requires_admin_login(self):
        c = Client()
        # even a logged-in staff user-session must not open admin pages
        c.post(reverse("login"), {"username": "staffadmin", "password": PASSWORD})
        self.assertEqual(c.get(reverse("home")).status_code, 200)
        r = c.get("/admin/auth/user/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/admin/login/", r.url)


class FormStructureTest(FlowDataMixin, TestCase):
    """Hantar must sit inside <form> inside .form-card (natural scroll flow)."""

    def form_inner(self, route):
        r = self.c(self.pemohon).get(route)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        start = html.index("<form")
        end = html.index("</form>")
        self.assertGreater(end, start, "missing </form>")
        return html[start:end]

    def test_pinjam_submit_inside_form(self):
        inner = self.form_inner(reverse("borang_pinjaman"))
        self.assertIn('class="form-submit"', inner)
        self.assertIn("HANTAR", inner)

    def test_serah_submit_inside_form(self):
        inner = self.form_inner(reverse("borang_serahan"))
        self.assertIn('class="form-submit"', inner)

    def test_pinjam_no_submit_elements_after_form(self):
        r = self.c(self.pemohon).get(reverse("borang_pinjaman"))
        html = r.content.decode()
        after = html.split("</form>", 1)[1]
        self.assertNotIn('class="form-submit"', after)
        self.assertNotIn('class="divider-line"', after)

    def test_serah_no_submit_elements_after_form(self):
        r = self.c(self.pemohon).get(reverse("borang_serahan"))
        html = r.content.decode()
        after = html.split("</form>", 1)[1]
        self.assertNotIn('class="form-submit"', after)


class FullDetailPopupTest(FlowDataMixin, TestCase):
    """The Tindakan popup must show the complete submitted record."""

    def popup(self, obj, as_user=None):
        return self.c(as_user or self.pemohon).get(
            reverse("request_detail", args=[obj.borang_type, obj.id])
        ).content.decode()

    # ---------- pinjaman ----------

    def test_pinjam_popup_shows_complete_submission(self):
        _, p = self.submit_pinjam(
            komponen_data=["Jalan", "DEM"],
            telefon="0161112222",
            tujuan="Tujuan penuh ujian",
            cacatan="Catatan penuh ujian",
            Tarikh="2026-05-20",
            Setuju="on",
            kat_0_negeri="SABAH",
            kat_0_daerah="KOTA KINABALU",
            kat_0_mukim="LIQUAM",
            kat_0_tahun="2026",
            kat_1_negeri="SELANGOR",
            kat_1_daerah="GOMBAK",
            kat_1_mukim="BATU",
            kat_1_tahun="2025",
        )
        p.refresh_from_db()
        self.assertEqual(p.telefon, "0161112222")
        self.assertEqual(p.kawasan["DATA ASAS"]["tahun"], "2026")
        self.assertEqual(p.kawasan["FASILITI"]["mukim"], "BATU")

        html = self.popup(p)
        # section headings
        self.assertIn("Maklumat Pemohon", html)
        self.assertIn("Komponen & Jenis Data", html)
        self.assertIn("Kawasan", html)
        self.assertIn("Tujuan Pinjaman / Kegunaan Data / Projek", html)
        # applicant fields
        self.assertIn("0161112222", html)
        self.assertIn("2026-05-20", html)
        self.assertIn("Pemohon Setuju: Ya", html)
        self.assertIn("Tarikh Hantar:", html)
        # components
        self.assertIn("Jalan, DEM", html)
        # per-category kawasan incl. tahun
        self.assertIn("DATA ASAS", html)
        self.assertIn("FASILITI", html)
        self.assertIn("SABAH", html)
        self.assertIn("KOTA KINABALU", html)
        self.assertIn("LIQUAM", html)
        self.assertIn("SELANGOR", html)
        self.assertIn("GOMBAK", html)
        self.assertIn("BATU", html)
        self.assertIn("2025", html)
        # purpose
        self.assertIn("Tujuan penuh ujian", html)
        self.assertIn("Catatan penuh ujian", html)
        # serahan-only fields must not leak in
        self.assertNotIn("Maklumat Data", html)
        self.assertNotIn("Klasifikasi Data", html)

    def test_pinjam_legacy_record_without_kawasan_displays_correctly(self):
        p = PinjamanRequest.objects.create(
            pemohon=self.pemohon,
            namapemohon="Pemohon Lama",
            email="lama@mysa.local",
            komponen_data="Jalan",
            tujuan="Tujuan lama",
            tahun="2024",
            kawasan=None,
            status="Borang Telah Dihantar",
        )
        html = self.popup(p)
        self.assertIn("Negeri:", html)
        self.assertIn("Tahun: 2024", html)
        self.assertIn("Tujuan lama", html)
        self.assertNotIn("Kawasan Mengikut Kategori", html)

    # ---------- serahan ----------

    def test_serah_popup_shows_complete_submission(self):
        _, s = self.submit_serah(
            telefon="0169998888",
            komponen_data=["Jalan", "Sungai"],
            jenis_data=["Poligon", "Garisan"],
            jenis_lain="Jenis Lain ujian",
            meta_data="Meta penuh ujian",
            klasifikasidata=["Awam"],
            jenisdataformat=["Digital", "Peta"],
            namaagensi="Agensi Penuh Ujian",
            namaprojek="Projek Penuh Ujian",
            tarikhprojek="2026-06-15",
            daerah="LAIN",
            daerah_lain="Daerah Khas Ujian",
            mukim="LAIN",
            mukim_lain="Mukim Khas Ujian",
        )
        html = self.popup(s)
        # section headings
        self.assertIn("Maklumat Pemohon", html)
        self.assertIn("Komponen & Jenis Data", html)
        self.assertIn("Kawasan", html)
        self.assertIn("Maklumat Data", html)
        # applicant fields
        self.assertIn("0169998888", html)
        self.assertIn("Tarikh: 2026-06-15", html)
        self.assertIn("Tarikh Hantar:", html)
        # components incl. lain text
        self.assertIn("Jalan, Sungai", html)
        # kawasan incl. lain text
        self.assertIn("Daerah Khas Ujian", html)
        self.assertIn("Mukim Khas Ujian", html)
        # data details
        self.assertIn("Poligon", html)
        self.assertIn("Garisan", html)
        self.assertIn("Jenis Lain ujian", html)
        self.assertIn("Meta penuh ujian", html)
        self.assertIn("Awam", html)
        self.assertIn("Digital", html)
        self.assertIn("Agensi Penuh Ujian", html)
        self.assertIn("Projek Penuh Ujian", html)
        # pinjaman-only fields must not leak in
        self.assertNotIn("Pemohon Setuju", html)
        self.assertNotIn("Tujuan Pinjaman", html)
        self.assertNotIn("Kawasan Mengikut Kategori", html)

    # ---------- no mixing ----------

    def test_popup_shows_correct_record_not_mixed(self):
        _, p = self.submit_pinjam(tujuan="ZZZ-TUJUAN-UNIK")
        _, s = self.submit_serah(namaprojek="YYY-PROJEK-UNIK")

        html_p = self.popup(p)
        html_s = self.popup(s)
        self.assertIn("ZZZ-TUJUAN-UNIK", html_p)
        self.assertNotIn("YYY-PROJEK-UNIK", html_p)
        self.assertIn("YYY-PROJEK-UNIK", html_s)
        self.assertNotIn("ZZZ-TUJUAN-UNIK", html_s)

    # ---------- actions preserved ----------

    def test_popup_action_buttons_preserved(self):
        _, s = self.submit_serah()
        html = self.c(self.pb).get(
            reverse("request_detail", args=["SERAHAN", s.id])
        ).content.decode()
        self.assertIn("Sokong", html)
        self.assertIn("Tidak Sokong", html)
