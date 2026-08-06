from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .models import (
    DataRequest,
    LoginLog,
    Negeri,
    Daerah,
    Mukim,
    SerahanRequest,
    PinjamanRequest,
    StatusLog,
)

SERAHAN_STEPS = [
    "Borang Telah Dihantar",
    "Tidak Disokong Oleh Pengarah Bahagian",
    "Disokong Oleh Pengarah Bahagian",
    "Mendapat Kelulusan Pengarah BITG",
    "Semakan Dan Penugasan Oleh Pengurus Pengkalan Data",
    "Verifikasi Data Oleh PIC",
    "Pembetulan Data",
    "Pengesahan Verifikasi",
    "Serahan Data",
    "Selesai",
]

PINJAMAN_STEPS = [
    "Borang Telah Dihantar",
    "Tidak Disokong Oleh Pengarah Bahagian",
    "Disokong Oleh Pengarah Bahagian",
    "Mendapat Kelulusan Pengarah BITG",
    "Penugasan PIC Oleh Pengarah BITG",
    "Penyediaan Data",
    "Serahan Data",
    "Semakan Oleh Pemohon",
    "Pembetulan Oleh Pemohon",
    "Sahkan Penerimaan Data",
    "Selesai",
]

STEPS = {
    "SERAHAN": SERAHAN_STEPS,
    "PINJAMAN": PINJAMAN_STEPS,
}


# =============================
# HELPERS
# =============================

def has_group(user, name):
    return user.groups.filter(name=name).exists()


def is_pengarah_bahagian(user):
    return has_group(user, "Pengarah Bahagian")


def is_pengarah_bitg(user):
    return has_group(user, "Pengarah BITG")


def is_pengurus(user):
    return has_group(user, "Pengurus Pengkalan Data")


def is_pic(user):
    return has_group(user, "PIC")


def is_admin(user):
    return user.is_superuser or has_group(user, "Admin")


def is_reviewer(user):
    return (
        is_admin(user)
        or is_pic(user)
        or is_pengarah_bahagian(user)
        or is_pengarah_bitg(user)
        or is_pengurus(user)
    )


def get_request_obj(borang_type, request_id):
    if borang_type == "SERAHAN":
        return SerahanRequest.objects.filter(id=request_id).first()
    return PinjamanRequest.objects.filter(id=request_id).first()


def request_content_type(obj):
    return ContentType.objects.get_for_model(type(obj))


def log_status(obj, status, changed_by, ulasan=None, sebab_tolak=None, iteration=0):
    StatusLog.objects.create(
        borang_type=obj.borang_type,
        content_type=request_content_type(obj),
        object_id=obj.id,
        status=status,
        ulasan=ulasan,
        sebab_tolak=sebab_tolak,
        changed_by=changed_by,
        iteration=iteration,
    )
    obj.status = status
    obj.save()


def annotate_steps(obj):
    steps = STEPS[obj.borang_type]
    idx = steps.index(obj.status) if obj.status in steps else 0
    obj.steps = steps
    obj.step_idx = idx
    obj.overdue = bool(
        obj.borang_type == "PINJAMAN"
        and obj.deadline
        and obj.status in ["Penyediaan Data", "Pembetulan Oleh Pemohon"]
        and timezone.now() > obj.deadline
    )
    obj.status_logs = StatusLog.objects.filter(
        content_type=request_content_type(obj),
        object_id=obj.id,
    ).select_related("changed_by").order_by("-changed_at")[:5]
    return obj


def merged_requests():
    combined = list(SerahanRequest.objects.all()) + list(PinjamanRequest.objects.all())
    combined.sort(key=lambda o: o.created_at, reverse=True)
    for o in combined:
        annotate_steps(o)
    return combined


def send_notif(subject, message, recipient_list):
    if recipient_list:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=True,
        )


def group_emails(group_name):
    users = User.objects.filter(groups__name=group_name)
    return [u.email for u in users if u.email]


# =============================
# AUTH
# =============================

def user_login(request):
    error = False
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            LoginLog.objects.create(user=user)
            return redirect("home")
        else:
            error = True
    return render(request, "login.html", {"error": error})


def user_logout(request):
    logout(request)
    return redirect("login")


@login_required
def home(request):
    return render(request, "home.html")


# =============================
# BORANG SERAHAN
# =============================

@login_required
def borang_serahan(request):
    if request.method == "POST":
        komponen = request.POST.getlist("komponen_data")
        komponen_lain = request.POST.get("komponen_lain")
        jenis = request.POST.getlist("jenis_data")
        jenis_lain = request.POST.get("jenis_lain")
        format_data = request.POST.getlist("format_data")
        format_lain = request.POST.get("format_lain")
        unjuran = request.POST.getlist("unjuranKoordinat_data")
        unjuranKoordinat_lain = request.POST.get("unjuranKoordinat_lain")
        sumber = request.POST.getlist("sumber_data")
        sumber_lain = request.POST.get("sumber_lain")
        metadata = request.POST.get("meta_data")
        metadata_lain = request.POST.get("meta_lain")
        jenisdataformat = request.POST.getlist("jenisdataformat")
        klasifikasidata = request.POST.getlist("klasifikasidata")
        uploaded_file = request.FILES.get("file")

        daerah = request.POST.get("daerah")
        daerah_text = None
        if daerah == "LAIN":
            daerah_text = request.POST.get("daerah_lain")
            daerah = None
        mukim = request.POST.get("mukim")
        mukim_text = None
        if mukim == "LAIN":
            mukim_text = request.POST.get("mukim_lain")
            mukim = None

        obj = SerahanRequest.objects.create(
            pemohon=request.user,
            namapemohon=request.POST.get("namapemohon"),
            email=request.POST.get("email"),
            telefon=request.POST.get("telefon"),
            komponen_data=", ".join(komponen) + ("  " + komponen_lain if komponen_lain else ""),
            negeri=Negeri.objects.filter(nama__iexact=request.POST.get("negeri")).first(),
            daerah=Daerah.objects.filter(nama__iexact=daerah).first() if daerah else None,
            mukim=Mukim.objects.filter(nama__iexact=mukim).first() if mukim else None,
            daerah_text=daerah_text,
            mukim_text=mukim_text,
            indeks=request.POST.get("indeks"),
            jenis_data=", ".join(jenis) + ("  " + jenis_lain if jenis_lain else ""),
            format_data=", ".join(format_data) + ("  " + format_lain if format_lain else ""),
            unjuranKoordinat_data=", ".join(unjuran) + ("  " + unjuranKoordinat_lain if unjuranKoordinat_lain else ""),
            sumber_data=", ".join(sumber) + ("  " + sumber_lain if sumber_lain else ""),
            meta_data=(metadata or "") + ("  " + metadata_lain if metadata_lain else ""),
            namaagensi=request.POST.get("namaagensi"),
            namaprojek=request.POST.get("namaprojek"),
            tarikhprojek=request.POST.get("tarikhprojek"),
            jenisdataformat=", ".join(jenisdataformat),
            klasifikasidata=", ".join(klasifikasidata),
            uploaded_file=uploaded_file,
        )
        log_status(obj, "Borang Telah Dihantar", request.user)
        send_notif(
            "Permohonan Serahan Diterima",
            f"Hi {obj.namapemohon}, permohonan anda telah dihantar. ID: {obj.id}",
            [obj.email],
        )
        send_notif(
            "Permohonan Baru Memerlukan Kelulusan",
            f"Permohonan baru telah dihantar.\n\nID: {obj.id}\nPemohon: {obj.namapemohon}\nSila login sistem untuk kelulusan.",
            group_emails("Pengarah Bahagian"),
        )
        return redirect("status")

    return render(request, "borang_serahan.html", {"negeri_list": Negeri.objects.all()})


# =============================
# BORANG PINJAMAN
# =============================

@login_required
def borang_pinjaman(request):
    if request.method == "POST":
        komponen = request.POST.getlist("komponen_data")
        komponen_lain = request.POST.get("komponen_lain")
        uploaded_file = request.FILES.get("file")

        daerah = request.POST.get("daerah")
        daerah_text = None
        if daerah == "LAIN":
            daerah_text = request.POST.get("daerah_lain")
            daerah = None
        mukim = request.POST.get("mukim")
        mukim_text = None
        if mukim == "LAIN":
            mukim_text = request.POST.get("mukim_lain")
            mukim = None

        obj = PinjamanRequest.objects.create(
            pemohon=request.user,
            namapemohon=request.POST.get("namapemohon"),
            email=request.POST.get("email"),
            telefon=request.POST.get("telefon"),
            komponen_data=", ".join(komponen) + ("  " + komponen_lain if komponen_lain else ""),
            negeri=Negeri.objects.filter(nama__iexact=request.POST.get("negeri")).first(),
            daerah=Daerah.objects.filter(nama__iexact=daerah).first() if daerah else None,
            mukim=Mukim.objects.filter(nama__iexact=mukim).first() if mukim else None,
            daerah_text=daerah_text,
            mukim_text=mukim_text,
            indeks=request.POST.get("indeks"),
            tujuan=request.POST.get("tujuan"),
            cacatan=request.POST.get("cacatan"),
            Setuju=bool(request.POST.get("Setuju")),
            nama=request.POST.get("nama"),
            Tarikh=request.POST.get("Tarikh"),
            uploaded_file=uploaded_file,
        )
        log_status(obj, "Borang Telah Dihantar", request.user)
        send_notif(
            "Permohonan Pinjaman Diterima",
            f"Hi {obj.namapemohon}, permohonan anda telah dihantar. ID: {obj.id}",
            [obj.email],
        )
        send_notif(
            "Permohonan Baru Memerlukan Kelulusan",
            f"Permohonan baru telah dihantar.\n\nID: {obj.id}\nPemohon: {obj.namapemohon}\nSila login sistem untuk kelulusan.",
            group_emails("Pengarah Bahagian"),
        )
        return redirect("status")

    return render(request, "borang_pinjaman.html", {"negeri_list": Negeri.objects.all()})


# =============================
# STATUS VIEW
# =============================

@login_required
def status_view(request):
    if is_reviewer(request.user):
        combined = merged_requests()
    else:
        combined = (
            list(SerahanRequest.objects.filter(pemohon=request.user))
            + list(PinjamanRequest.objects.filter(pemohon=request.user))
        )
        combined.sort(key=lambda o: o.created_at, reverse=True)
        for o in combined:
            annotate_steps(o)
    return render(request, "status.html", {"requests": combined})


# =============================
# ADMIN BORANG (SEARCH)
# =============================

@login_required
def admin_borang(request):
    if not is_reviewer(request.user):
        return redirect("home")

    keyword = request.GET.get("q", "").strip()
    serah = SerahanRequest.objects.all()
    pinjam = PinjamanRequest.objects.all()

    if keyword:
        k = Q(id__icontains=keyword) | Q(namapemohon__icontains=keyword) | Q(email__icontains=keyword) | Q(status__icontains=keyword) | Q(negeri__nama__icontains=keyword)
        serah = serah.filter(k)
        pinjam = pinjam.filter(k)

    combined = list(serah) + list(pinjam)
    combined.sort(key=lambda o: o.created_at, reverse=True)
    for o in combined:
        annotate_steps(o)

    return render(request, "admin_borang.html", {"requests": combined, "keyword": keyword})


# =============================
# PENGARAH / PENGURUS / PIC DASHBOARD
# =============================

@login_required
def pengarah_dashboard(request):
    user = request.user
    qs = []

    if is_pengarah_bahagian(user):
        qs = list(SerahanRequest.objects.filter(status="Borang Telah Dihantar")) + list(PinjamanRequest.objects.filter(status="Borang Telah Dihantar"))
    elif is_pengarah_bitg(user):
        qs = list(SerahanRequest.objects.filter(status="Disokong Oleh Pengarah Bahagian")) + list(PinjamanRequest.objects.filter(status="Disokong Oleh Pengarah Bahagian"))
    elif is_pengurus(user):
        qs = list(SerahanRequest.objects.filter(status__in=["Mendapat Kelulusan Pengarah BITG", "Pengesahan Verifikasi"]))
    elif is_pic(user):
        qs = list(SerahanRequest.objects.filter(pic=user, status__in=["Verifikasi Data Oleh PIC", "Pembetulan Data"])) + list(PinjamanRequest.objects.filter(pic=user, status__in=["Penyediaan Data", "Pembetulan Oleh Pemohon"]))
    else:
        return redirect("home")

    qs.sort(key=lambda o: o.created_at, reverse=True)
    for o in qs:
        annotate_steps(o)

    return render(request, "pengarah_dashboard.html", {
        "requests": qs,
        "is_pengarah_bahagian": is_pengarah_bahagian(user),
        "is_pengarah_bitg": is_pengarah_bitg(user),
        "is_pengurus": is_pengurus(user),
        "is_pic": is_pic(user),
        "users": User.objects.filter(groups__name="PIC"),
    })


# =============================
# APPROVE / REJECT (PENGARAH BAHAGIAN + BITG)
# =============================

@login_required
def approve_request(request, borang_type, request_id):
    data = get_request_obj(borang_type, request_id)
    if not data:
        return HttpResponseForbidden("Not found")

    user = request.user
    if request.method != "POST":
        return HttpResponseForbidden("POST only")

    action = request.POST.get("action")
    sebab = request.POST.get("sebab_tolak")
    ulasan = request.POST.get("ulasan")

    # Pengarah Bahagian
    if is_pengarah_bahagian(user) and data.status == "Borang Telah Dihantar":
        if action == "reject":
            log_status(data, "Tidak Disokong Oleh Pengarah Bahagian", user, sebab_tolak=sebab or "-")
            send_notif("Permohonan Tidak Disokong", f"Permohonan ID {data.id} tidak disokong.\nSebab: {sebab}", [data.email])
        else:
            log_status(data, "Disokong Oleh Pengarah Bahagian", user)
            send_notif("Permohonan Diluluskan (Bahagian)", f"Permohonan ID {data.id} telah disokong oleh Pengarah Bahagian.", [data.email])
            send_notif("Permohonan Memerlukan Kelulusan BITG", f"ID: {data.id}\nPemohon: {data.namapemohon}\nSila login sistem untuk kelulusan.", group_emails("Pengarah BITG"))

    # Pengarah BITG
    elif is_pengarah_bitg(user) and data.status == "Disokong Oleh Pengarah Bahagian":
        if action == "reject":
            log_status(data, "Tidak Disokong Oleh Pengarah Bahagian", user, ulasan=ulasan, sebab_tolak=sebab or "-")
            send_notif("Permohonan Tidak Disokong", f"Permohonan ID {data.id} tidak disokong.\nSebab: {sebab}", [data.email])
        else:
            log_status(data, "Mendapat Kelulusan Pengarah BITG", user, ulasan=ulasan)
            send_notif("Permohonan Diluluskan (BITG)", f"Permohonan ID {data.id} telah diluluskan oleh Pengarah BITG.\nUlasan: {ulasan or '-'}", [data.email])
            if data.borang_type == "SERAHAN":
                send_notif("Permohonan Memerlukan Semakan", f"ID: {data.id}\nPemohon: {data.namapemohon}\nSila login sistem untuk semakan & penugasan.", group_emails("Pengurus Pengkalan Data"))
            else:
                send_notif("Permohonan Memerlukan Penugasan", f"ID: {data.id}\nPemohon: {data.namapemohon}\nSila login sistem untuk penugasan PIC.", group_emails("Pengarah BITG"))
    else:
        return HttpResponseForbidden("Not allowed")

    return redirect("pengarah_dashboard")


# =============================
# ASSIGN PIC
# =============================

@login_required
def assign_pic(request, borang_type, request_id):
    data = get_request_obj(borang_type, request_id)
    if not data:
        return HttpResponseForbidden("Not found")

    user = request.user
    if request.method == "POST":
        pic_id = request.POST.get("pic")
        if not pic_id:
            return redirect("assign_pic_page")
        pic_user = User.objects.filter(id=pic_id).first()
        if not pic_user:
            return redirect("assign_pic_page")

        # SERAHAN: Pengurus Pengkalan Data assigns
        if data.borang_type == "SERAHAN" and is_pengurus(user) and data.status == "Mendapat Kelulusan Pengarah BITG":
            data.pic = pic_user
            data.save()
            log_status(data, "Verifikasi Data Oleh PIC", user)
        # PINJAMAN: Pengarah BITG assigns
        elif data.borang_type == "PINJAMAN" and is_pengarah_bitg(user) and data.status == "Mendapat Kelulusan Pengarah BITG":
            data.pic = pic_user
            data.deadline = timezone.now() + timedelta(days=5)
            data.save()
            log_status(data, "Penyediaan Data", user)
        else:
            return HttpResponseForbidden("Not allowed")

        send_notif("Tugasan Baru Diterima", f"Anda telah ditugaskan untuk permohonan ID {data.id}.\nPemohon: {data.namapemohon}", [pic_user.email])
        send_notif("PIC Telah Ditetapkan", f"Permohonan anda (ID {data.id}) diberikan kepada PIC untuk diproses.", [data.email])
        return redirect("pengarah_dashboard")

    return HttpResponseForbidden("POST only")


@login_required
def assign_pic_page(request):
    user = request.user
    if is_pengurus(user):
        borang_list = SerahanRequest.objects.filter(status="Mendapat Kelulusan Pengarah BITG")
    elif is_pengarah_bitg(user):
        borang_list = PinjamanRequest.objects.filter(status="Mendapat Kelulusan Pengarah BITG")
    else:
        return redirect("home")

    for o in borang_list:
        annotate_steps(o)

    return render(request, "assign_pic.html", {
        "borang_list": borang_list,
        "users": User.objects.filter(groups__name="PIC"),
    })


# =============================
# VERIFY / DELIVER / CONFIRM
# =============================

@login_required
def verify_data(request, borang_type, request_id):
    data = get_request_obj(borang_type, request_id)
    if not data:
        return HttpResponseForbidden("Not found")

    user = request.user
    if request.method != "POST":
        return HttpResponseForbidden("POST only")

    action = request.POST.get("action")
    sebab = request.POST.get("sebab_tolak")

    # SERAHAN: PIC verifikasi / pembetulan
    if data.borang_type == "SERAHAN" and is_pic(user) and data.pic_id == user.id and data.status in ["Verifikasi Data Oleh PIC", "Pembetulan Data"]:
        if action == "reject":
            log_status(data, "Pembetulan Data", user, sebab_tolak=sebab or "-")
            send_notif("Pembetulan Diperlukan", f"Data permohonan ID {data.id} perlu pembetulan.\nSebab: {sebab}", group_emails("Pengurus Pengkalan Data"))
        else:
            log_status(data, "Pengesahan Verifikasi", user)
            send_notif("Verifikasi Data Selesai", f"Verifikasi permohonan ID {data.id} selesai.", group_emails("Pengurus Pengkalan Data"))

    # SERAHAN: Pengurus sahkan verifikasi -> serahan -> selesai
    elif data.borang_type == "SERAHAN" and is_pengurus(user) and data.status == "Pengesahan Verifikasi":
        if action == "reject":
            log_status(data, "Verifikasi Data Oleh PIC", user, sebab_tolak=sebab or "-")
        else:
            log_status(data, "Serahan Data", user)
            log_status(data, "Selesai", user)
            send_notif("Serahan Data Selesai", f"Data permohonan ID {data.id} telah diserahkan.", [data.email])

    # PINJAMAN: Pemohon sahkan penerimaan / pembetulan
    elif data.borang_type == "PINJAMAN" and data.pemohon_id == user.id and data.status == "Serahan Data":
        if action == "reject":
            data.deadline = timezone.now() + timedelta(days=5)
            data.save()
            log_status(data, "Penyediaan Data", user, sebab_tolak=sebab or "-")
            log_status(data, "Pembetulan Oleh Pemohon", user, sebab_tolak=sebab or "-")
            send_notif("Pembetulan Diperlukan", f"Pemohon memerlukan pembetulan untuk permohonan ID {data.id}.\nSebab: {sebab}", [data.pic.email] if data.pic else [])
        else:
            log_status(data, "Sahkan Penerimaan Data", user)
            log_status(data, "Selesai", user)
            send_notif("Pinjaman Disahkan", f"Pemohon telah mengesahkan penerimaan data permohonan ID {data.id}.", group_emails("PIC"))
    else:
        return HttpResponseForbidden("Not allowed")

    return redirect("status")


# =============================
# PIC UPLOAD (DELIVERY / PREPARATION)
# =============================

@login_required
def upload_data(request, borang_type, request_id):
    data = get_request_obj(borang_type, request_id)
    if not data:
        return HttpResponseForbidden("Not found")

    user = request.user
    if request.method == "POST":
        uploaded_file = request.FILES.get("data_file") or request.FILES.get("file")
        if not uploaded_file:
            return redirect("upload_page")
        data.uploaded_file = uploaded_file
        data.save()

        if data.borang_type == "PINJAMAN" and is_pic(user) and data.pic_id == user.id and data.status in ["Penyediaan Data", "Pembetulan Oleh Pemohon"]:
            log_status(data, "Serahan Data", user)
            send_notif("Data Sedia Untuk Semakan", f"Data permohonan ID {data.id} telah disediakan. Sila semak.", [data.email])
        elif data.borang_type == "SERAHAN" and is_pic(user) and data.pic_id == user.id and data.status in ["Verifikasi Data Oleh PIC", "Pembetulan Data"]:
            log_status(data, "Pembetulan Data" if data.status == "Pembetulan Data" else "Verifikasi Data Oleh PIC", user)

        return redirect("upload_page")

    return HttpResponseForbidden("POST only")


@login_required
def upload_page(request):
    if not is_pic(request.user):
        return redirect("home")
    tasks = (
        list(SerahanRequest.objects.filter(pic=request.user, status__in=["Verifikasi Data Oleh PIC", "Pembetulan Data"]))
        + list(PinjamanRequest.objects.filter(pic=request.user, status__in=["Penyediaan Data", "Pembetulan Oleh Pemohon"]))
    )
    tasks.sort(key=lambda o: o.created_at, reverse=True)
    for o in tasks:
        annotate_steps(o)
    return render(request, "upload.html", {"requests": tasks})


# =============================
# MANUAL STATUS OVERRIDE (ADMIN / PIC)
# =============================

@login_required
def status_update(request, borang_type=None, request_id=None):
    if not (is_admin(request.user) or is_pic(request.user) or is_pengurus(request.user)):
        return redirect("home")

    all_requests = merged_requests()

    if request.method == "POST":
        req_id = request.POST.get("request_id")
        req_bt = request.POST.get("borang_type")
        new_status = request.POST.get("status")
        sebab = request.POST.get("sebab_tolak")
        ulasan = request.POST.get("ulasan")
        obj = get_request_obj(req_bt, req_id)
        if obj:
            log_status(obj, new_status, request.user, ulasan=ulasan, sebab_tolak=sebab)
            send_notif(
                "Status Permohonan Dikemaskini",
                f"Hi {obj.namapemohon},\n\nStatus permohonan anda telah dikemaskini.\n\nID: {obj.id}\nStatus Baru: {new_status}\n\nSila login sistem untuk semakan lanjut.",
                [obj.email],
            )
        return redirect("status_update", borang_type=req_bt, request_id=req_id)

    data = get_request_obj(borang_type, request_id) if request_id else None
    if data:
        annotate_steps(data)
        options = STEPS[data.borang_type]
    else:
        options = SERAHAN_STEPS + [s for s in PINJAMAN_STEPS if s not in SERAHAN_STEPS]

    return render(request, "status_update.html", {
        "data": data,
        "all_requests": all_requests,
        "options": options,
    })


@login_required
def flow_update(request):
    return status_update(request)


@login_required
def update_status(request, borang_type, request_id, new_status):
    obj = get_request_obj(borang_type, request_id)
    if obj and is_admin(request.user):
        log_status(obj, new_status, request.user)
    return redirect("status_update", borang_type=borang_type, request_id=request_id)


# =============================
# STATISTICS
# =============================

def statistics(request):
    from django.utils.timezone import now
    from datetime import datetime

    current = now()
    month = request.GET.get("month", current.month)
    year = request.GET.get("year", current.year)
    month = int(month)
    year = int(year)
    current_year = datetime.now().year

    logins = LoginLog.objects.filter(login_time__month=month, login_time__year=year)
    total_login = logins.count()
    unique_users = logins.values("user").distinct().count()

    total_serahan = SerahanRequest.objects.filter(created_at__month=month, created_at__year=year).count()
    total_pinjaman = PinjamanRequest.objects.filter(created_at__month=month, created_at__year=year).count()

    month_serah = list(SerahanRequest.objects.filter(created_at__month=month, created_at__year=year))
    month_pinjam = list(PinjamanRequest.objects.filter(created_at__month=month, created_at__year=year))

    from collections import Counter
    komponen_counter = Counter()
    kawasan_counter = Counter()
    jenis_counter = Counter()
    klas_counter = Counter()

    def bump(counter, val):
        if val:
            counter[val] += 1

    for r in month_serah + month_pinjam:
        bump(komponen_counter, r.komponen_data)
        kawasan_counter[str(r.negeri) + "|" + str(r.daerah) + "|" + str(r.mukim)] += 1
        bump(jenis_counter, getattr(r, "jenis_data", None))
        bump(klas_counter, getattr(r, "klasifikasidata", None))

    def kawasan_list(counter, n=5):
        out = []
        for k, v in counter.most_common(n):
            parts = k.split("|")
            out.append({
                "negeri": parts[0] if len(parts) > 0 else "",
                "daerah": parts[1] if len(parts) > 1 else "",
                "mukim": parts[2] if len(parts) > 2 else "",
                "total": v,
            })
        return out

    def field_list(counter, key, n=5):
        return [{key: k, "total": v} for k, v in counter.most_common(n)]

    context = {
        "month": month,
        "year": year,
        "years": range(current_year, current_year - 5, -1),
        "total_login": total_login,
        "unique_users": unique_users,
        "total_serahan": total_serahan,
        "total_pinjaman": total_pinjaman,
        "top_kawasan": kawasan_list(kawasan_counter),
        "top_komponen": field_list(komponen_counter, "komponen_data"),
        "top_metadata": [],
        "top_jenis": field_list(jenis_counter, "jenis_data"),
        "top_klasifikasi": field_list(klas_counter, "klasifikasidata"),
    }
    return render(request, "statistics.html", context)


# =============================
# KAWASAN AJAX
# =============================

def get_daerah(request):
    negeri_name = request.GET.get("negeri")
    negeri = Negeri.objects.filter(nama__iexact=negeri_name).first()
    if not negeri:
        return JsonResponse([], safe=False)
    data = list(Daerah.objects.filter(negeri=negeri).values("id", "nama").order_by("nama"))
    return JsonResponse(data, safe=False)


def get_mukim(request):
    daerah_name = request.GET.get("daerah")
    daerah = Daerah.objects.filter(nama__iexact=daerah_name).first()
    if not daerah:
        return JsonResponse([], safe=False)
    data = list(Mukim.objects.filter(daerah=daerah).values("id", "nama").order_by("nama"))
    return JsonResponse(data, safe=False)


# =============================
# REGISTER
# =============================

def register_page(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        fullname = request.POST.get("fullname", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm", "")

        if not fullname or not username or not email:
            messages.error(request, "Sila lengkapkan semua maklumat.")
            return redirect("register")
        if password != confirm:
            messages.error(request, "Kata laluan tidak sepadan.")
            return redirect("register")
        if len(password) < 8:
            messages.error(request, "Kata laluan minimum 8 aksara.")
            return redirect("register")
        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username telah digunakan.")
            return redirect("register")
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Email telah digunakan.")
            return redirect("register")

        user = User.objects.create_user(username=username, email=email, password=password, first_name=fullname)
        staff_group, created = Group.objects.get_or_create(name="Staff")
        user.groups.add(staff_group)
        login(request, user)
        messages.success(request, "Pendaftaran berjaya! Akaun anda telah didaftarkan.")
        return redirect("login")

    return render(request, "register.html")


# =============================
# FORGOT PASSWORD
# =============================

def forgot_password_page(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = request.build_absolute_uri(
                reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
            )
            send_mail(
                "Reset Kata Laluan MYSA",
                f"Klik pautan berikut:\n{link}",
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )
            messages.success(request, "Link reset dihantar ke email.")
        except Exception:
            messages.error(request, "Email tidak dijumpai.")
        return redirect("forgot_password")

    return render(request, "forgot_password.html")


def login_link(request):
    return request.build_absolute_uri("/")
