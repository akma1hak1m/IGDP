from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseNotFound, JsonResponse
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
    LoginLog,
    Negeri,
    Daerah,
    Mukim,
    Bahagian,
    SerahanRequest,
    PinjamanRequest,
    StatusLog,
    UserProfile,
)

SERAHAN_STEPS = [
    "Borang Telah Dihantar",
    "Tidak Disokong Oleh Pengarah Bahagian",
    "Disokong Oleh Pengarah Bahagian",
    "Tidak Mendapat Kelulusan Pengarah BITG",
    "Mendapat Kelulusan Pengarah BITG",
    "Verifikasi Data Oleh PIC",
    "Pembetulan Oleh Pemohon",
    "Pengesahan Verifikasi",
    "Serahan Data",
    "Selesai",
]

PINJAMAN_STEPS = [
    "Borang Telah Dihantar",
    "Tidak Disokong Oleh Pengarah Bahagian",
    "Disokong Oleh Pengarah Bahagian",
    "Tidak Mendapat Kelulusan Pengarah BITG",
    "Mendapat Kelulusan Pengarah BITG",
    "Penugasan PIC Oleh Pengarah BITG",
    "Penyediaan Data",
    "Semakan Oleh Pemohon",
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


def is_bitg(user):
    """Pengarah Bahagian whose department is BITG — acts as the BITG-level approver."""
    if not has_group(user, "Pengarah Bahagian"):
        return False
    b = user_bahagian(user)
    return b is not None and b.nama == "BITG"


def is_pic(user):
    return has_group(user, "PIC")


def is_admin(user):
    return user.is_superuser or has_group(user, "Admin")


def is_reviewer(user):
    return (
        is_admin(user)
        or is_pic(user)
        or is_pengarah_bahagian(user)
        or is_bitg(user)
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
        and obj.status in ["Penyediaan Data", "Semakan Oleh Pemohon"]
        and timezone.now() > obj.deadline
    )
    obj.status_logs = StatusLog.objects.filter(
        content_type=request_content_type(obj),
        object_id=obj.id,
    ).select_related("changed_by").order_by("-changed_at")
    return obj


def merged_requests():
    combined = list(SerahanRequest.objects.all()) + list(PinjamanRequest.objects.all())
    combined.sort(key=lambda o: o.created_at, reverse=True)
    for o in combined:
        annotate_steps(o)
    return combined


SORT_FIELDS = {"id", "borang_type", "namapemohon", "email", "status", "bahagian", "created_at"}


def request_base_segments(scope, user):
    """List of (model, queryset) for a scope. Search/filters applied per segment."""
    if scope == "my":
        return [
            (SerahanRequest, SerahanRequest.objects.filter(pemohon=user)),
            (PinjamanRequest, PinjamanRequest.objects.filter(pemohon=user)),
        ]
    if scope == "all":
        return [
            (SerahanRequest, SerahanRequest.objects.all()),
            (PinjamanRequest, PinjamanRequest.objects.all()),
        ]
    if scope in ("pb", "bitg"):
        b = user_bahagian(user)
        segments = [
            (SerahanRequest, SerahanRequest.objects.filter(status="Borang Telah Dihantar", bahagian=b)),
            (PinjamanRequest, PinjamanRequest.objects.filter(status="Borang Telah Dihantar", bahagian=b)),
        ]
        if scope == "bitg":
            segments += [
                (SerahanRequest, SerahanRequest.objects.filter(status="Disokong Oleh Pengarah Bahagian")),
                (PinjamanRequest, PinjamanRequest.objects.filter(status="Disokong Oleh Pengarah Bahagian")),
            ]
        return segments
    if scope == "pic":
        return [
            (SerahanRequest, SerahanRequest.objects.filter(pic=user, status="Verifikasi Data Oleh PIC")),
            (PinjamanRequest, PinjamanRequest.objects.filter(pic=user, status="Penyediaan Data")),
        ]
    return []


def _sort_value(rec, field):
    if field == "id":
        return rec["id"]
    if field == "borang_type":
        return rec["bt"] or ""
    if field == "bahagian":
        return rec["bahagian"] or ""
    if field == "created_at":
        return rec["created_at"] or datetime.min
    return rec.get(field) or ""


def row_json(o):
    overdue = bool(
        o.borang_type == "PINJAMAN"
        and o.deadline
        and o.status in ["Penyediaan Data", "Semakan Oleh Pemohon"]
        and timezone.now() > o.deadline
    )
    return {
        "id": o.id,
        "borang_type": o.borang_type,
        "namapemohon": o.namapemohon,
        "email": o.email,
        "bahagian": o.bahagian.nama if o.bahagian_id else "",
        "status": o.status,
        "negeri": str(o.negeri) if o.negeri_id else "",
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "overdue": overdue,
        "pic": o.pic.username if o.pic_id else "",
    }


def request_list_context():
    statuses = SERAHAN_STEPS + [s for s in PINJAMAN_STEPS if s not in SERAHAN_STEPS]
    return {
        "status_options": statuses,
        "negeri_options": Negeri.objects.all(),
        "bahagian_options": Bahagian.objects.all(),
        "per_page_options": [10, 15, 20, 50],
    }


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


def bahagian_pb_emails(bahagian):
    """Emails of Pengarah Bahagian users assigned to the given department."""
    if not bahagian:
        return []
    users = User.objects.filter(groups__name="Pengarah Bahagian", profile__bahagian=bahagian)
    return [u.email for u in users if u.email]


def bitg_emails():
    """Emails of Pengarah Bahagian users whose department is BITG."""
    users = User.objects.filter(groups__name="Pengarah Bahagian", profile__bahagian__nama="BITG")
    return [u.email for u in users if u.email]


def user_bahagian(user):
    profile = getattr(user, "profile", None)
    return profile.bahagian if profile else None


SERAH_SIG_KEYS = ["komponen_data", "daerah_text", "mukim_text", "indeks", "jenis_data", "format_data", "unjuranKoordinat_data", "sumber_data", "meta_data", "namaagensi", "namaprojek", "tarikhprojek", "jenisdataformat", "klasifikasidata"]
PINJAM_SIG_KEYS = ["komponen_data", "daerah_text", "mukim_text", "indeks", "tujuan", "cacatan", "Setuju", "nama", "Tarikh"]


def duplicate_submission(user, model, data, keys):
    """True if the user posted the identical form within the last 5 seconds."""
    cutoff = timezone.now() - timedelta(seconds=5)
    last = model.objects.filter(pemohon=user, created_at__gte=cutoff).order_by("-created_at").first()
    if not last:
        return False
    new_sig = tuple(str(data.get(k) or "") for k in keys)
    old_sig = tuple(str(getattr(last, k) or "") for k in keys)
    return new_sig == old_sig


def applicant_info(user):
    """Applicant details always come from the logged-in account."""
    name = (user.get_full_name() or "").strip() or user.username
    email = user.email or ""
    phone = ""
    profile = getattr(user, "profile", None)
    if profile and profile.phone:
        phone = profile.phone
    return name, email, phone


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

def serah_form_data(request):
    """Parse submitted serahan form fields into a dict for create/update."""
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

    return {
        "komponen_data": ", ".join(komponen) + ("  " + komponen_lain if komponen_lain else ""),
        "negeri": Negeri.objects.filter(nama__iexact=request.POST.get("negeri")).first(),
        "daerah": Daerah.objects.filter(nama__iexact=daerah).first() if daerah else None,
        "mukim": Mukim.objects.filter(nama__iexact=mukim).first() if mukim else None,
        "daerah_text": daerah_text,
        "mukim_text": mukim_text,
        "indeks": request.POST.get("indeks"),
        "jenis_data": ", ".join(jenis) + ("  " + jenis_lain if jenis_lain else ""),
        "format_data": ", ".join(format_data) + ("  " + format_lain if format_lain else ""),
        "unjuranKoordinat_data": ", ".join(unjuran) + ("  " + unjuranKoordinat_lain if unjuranKoordinat_lain else ""),
        "sumber_data": ", ".join(sumber) + ("  " + sumber_lain if sumber_lain else ""),
        "meta_data": (metadata or "") + ("  " + metadata_lain if metadata_lain else ""),
        "namaagensi": request.POST.get("namaagensi"),
        "namaprojek": request.POST.get("namaprojek"),
        "tarikhprojek": request.POST.get("tarikhprojek"),
        "jenisdataformat": ", ".join(jenisdataformat),
        "klasifikasidata": ", ".join(klasifikasidata),
        "uploaded_file": request.FILES.get("file"),
    }


def split_lain(field):
    """Recover the 'lain-lain' free text stored after a double space."""
    if field and "  " in field:
        return field.split("  ", 1)[1]
    return ""


def selected_values(field):
    """Checkbox values stored as comma-joined string, with optional lain part."""
    if not field:
        return []
    main, _, _ = field.partition("  ")
    return [v.strip() for v in main.split(",") if v.strip()]


def serah_prefill(obj):
    """Selected checkbox values + lain text for edit mode prefill."""
    return {
        "komponen_data": selected_values(obj.komponen_data),
        "komponen_lain": split_lain(obj.komponen_data),
        "jenis_data": selected_values(obj.jenis_data),
        "jenis_lain": split_lain(obj.jenis_data),
        "format_data": selected_values(obj.format_data),
        "format_lain": split_lain(obj.format_data),
        "unjuranKoordinat_data": selected_values(obj.unjuranKoordinat_data),
        "unjuranKoordinat_lain": split_lain(obj.unjuranKoordinat_data),
        "sumber_data": selected_values(obj.sumber_data),
        "sumber_lain": split_lain(obj.sumber_data),
        "meta_data": selected_values(obj.meta_data),
        "meta_lain": split_lain(obj.meta_data),
        "jenisdataformat": selected_values(obj.jenisdataformat),
        "klasifikasidata": selected_values(obj.klasifikasidata),
    }


@login_required
def borang_serahan(request):
    if request.method == "POST":
        data = serah_form_data(request)
        if duplicate_submission(request.user, SerahanRequest, data, SERAH_SIG_KEYS):
            return redirect("status")
        obj = SerahanRequest.objects.create(
            pemohon=request.user,
            namapemohon=applicant_info(request.user)[0],
            email=applicant_info(request.user)[1],
            telefon=request.POST.get("telefon") or applicant_info(request.user)[2],
            bahagian=user_bahagian(request.user),
            **data,
        )
        log_status(obj, "Borang Telah Dihantar", request.user)
        send_notif(
            "Permohonan Serahan Diterima",
            f"Hi {obj.namapemohon}, permohonan anda telah dihantar. ID: {obj.id}",
            [obj.email],
        )
        send_notif(
            "Permohonan Baru Memerlukan Kelulusan",
            f"Permohonan baru telah dihantar.\n\nID: {obj.id}\nPemohon: {obj.namapemohon}\nBahagian: {obj.bahagian}\nSila login sistem untuk kelulusan.",
            bahagian_pb_emails(obj.bahagian),
        )
        return redirect("status")

    applicant_name, applicant_email, applicant_phone = applicant_info(request.user)

    return render(request, "borang_serahan.html", {
        "negeri_list": Negeri.objects.all(),
        "applicant_name": applicant_name,
        "applicant_email": applicant_email,
        "applicant_phone": applicant_phone,
    })


@login_required
def borang_serahan_edit(request, request_id):
    obj = SerahanRequest.objects.filter(id=request_id).first()
    if not obj or obj.pemohon_id != request.user.id or obj.status != "Pembetulan Oleh Pemohon":
        return redirect("status")

    if request.method == "POST":
        logs = StatusLog.objects.filter(borang_type=obj.borang_type, object_id=obj.id)
        last_pembetulan = logs.filter(status="Pembetulan Oleh Pemohon").order_by("-changed_at").first()
        last_resubmit = logs.filter(status="Borang Telah Dihantar", changed_by=request.user).order_by("-changed_at").first()
        if last_resubmit and (not last_pembetulan or last_resubmit.changed_at > last_pembetulan.changed_at):
            return redirect("status")
        data = serah_form_data(request)
        data.pop("uploaded_file")
        data["telefon"] = request.POST.get("telefon") or obj.telefon
        for field, value in data.items():
            setattr(obj, field, value)
        obj.bahagian = user_bahagian(request.user) or obj.bahagian
        obj.pic = None
        obj.save()
        log_status(obj, "Borang Telah Dihantar", request.user)
        send_notif(
            "Permohonan Serahan Dihantar Semula",
            f"Hi {obj.namapemohon}, permohonan anda telah dikemaskini dan dihantar semula. ID: {obj.id}",
            [obj.email],
        )
        send_notif(
            "Permohonan Semula Memerlukan Kelulusan",
            f"Permohonan telah dikemaskini dan dihantar semula.\n\nID: {obj.id}\nPemohon: {obj.namapemohon}\nBahagian: {obj.bahagian}\nSila login sistem untuk kelulusan.",
            bahagian_pb_emails(obj.bahagian),
        )
        return redirect("status")

    applicant_name, applicant_email, applicant_phone = applicant_info(request.user)

    return render(request, "borang_serahan.html", {
        "negeri_list": Negeri.objects.all(),
        "applicant_name": applicant_name,
        "applicant_email": applicant_email,
        "applicant_phone": applicant_phone,
        "editing": True,
        "obj": obj,
        "prefill": serah_prefill(obj),
    })


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

        sig = {
            "komponen_data": ", ".join(komponen) + ("  " + komponen_lain if komponen_lain else ""),
            "daerah_text": daerah_text or "",
            "mukim_text": mukim_text or "",
            "indeks": request.POST.get("indeks") or "",
            "tujuan": request.POST.get("tujuan") or "",
            "cacatan": request.POST.get("cacatan") or "",
            "Setuju": bool(request.POST.get("Setuju")),
            "nama": request.POST.get("nama") or "",
            "Tarikh": request.POST.get("Tarikh") or "",
        }
        if duplicate_submission(request.user, PinjamanRequest, sig, PINJAM_SIG_KEYS):
            return redirect("status")

        obj = PinjamanRequest.objects.create(
            pemohon=request.user,
            namapemohon=applicant_info(request.user)[0],
            email=applicant_info(request.user)[1],
            telefon=applicant_info(request.user)[2],
            bahagian=user_bahagian(request.user),
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
            f"Permohonan baru telah dihantar.\n\nID: {obj.id}\nPemohon: {obj.namapemohon}\nBahagian: {obj.bahagian}\nSila login sistem untuk kelulusan.",
            bahagian_pb_emails(obj.bahagian),
        )
        return redirect("status")

    applicant_name, applicant_email, applicant_phone = applicant_info(request.user)

    return render(request, "borang_pinjaman.html", {
        "negeri_list": Negeri.objects.all(),
        "applicant_name": applicant_name,
        "applicant_email": applicant_email,
        "applicant_phone": applicant_phone,
    })


# =============================
# STATUS VIEW
# =============================

@login_required
def status_view(request):
    scope = "all" if is_reviewer(request.user) else "my"
    return render(request, "list_requests.html", {
        "page_title": "STATUS PERMOHONAN DATA",
        "scope": scope,
        **request_list_context(),
    })


# =============================
# ADMIN BORANG (SEARCH)
# =============================

@login_required
def admin_borang(request):
    if not is_reviewer(request.user):
        return redirect("home")

    return render(request, "list_requests.html", {
        "page_title": "SEMAKAN BORANG",
        "scope": "all",
        **request_list_context(),
    })


# =============================
# ASYNC LIST / DETAIL (pagination + filters)
# =============================

@login_required
def requests_list(request):
    user = request.user
    scope = request.GET.get("scope", "my")
    if scope not in {"my", "all", "pb", "bitg", "pic"}:
        scope = "my"
    if scope == "all" and not is_reviewer(user):
        scope = "my"
    if scope in ("pb", "bitg") and not is_pengarah_bahagian(user):
        scope = "my"
    if scope == "bitg" and not is_bitg(user):
        scope = "pb"
    if scope == "pic" and not is_pic(user):
        scope = "my"

    segments = request_base_segments(scope, user)

    q = request.GET.get("q", "").strip()
    statuses = [s for s in request.GET.getlist("status") if s]
    negeris = [n for n in request.GET.getlist("negeri") if n]
    bahagians = [b for b in request.GET.getlist("bahagian") if b]
    types = [t for t in request.GET.getlist("type") if t in ("SERAHAN", "PINJAMAN")]

    recs = []
    for model, qs in segments:
        bt = "SERAHAN" if model is SerahanRequest else "PINJAMAN"
        if types and bt not in types:
            continue
        if q:
            qs = qs.filter(Q(id__icontains=q) | Q(namapemohon__icontains=q) | Q(email__icontains=q))
        if statuses:
            qs = qs.filter(status__in=statuses)
        if negeris:
            qs = qs.filter(negeri__nama__in=negeris)
        if bahagians:
            qs = qs.filter(bahagian__nama__in=bahagians)
        for row in qs.values("id", "namapemohon", "email", "status", "bahagian__nama", "negeri__nama", "created_at"):
            row["bt"] = bt
            row["bahagian"] = row.pop("bahagian__nama")
            row["negeri"] = row.pop("negeri__nama")
            recs.append(row)

    sort = request.GET.get("sort", "created_at")
    order = request.GET.get("order", "desc")
    if sort not in SORT_FIELDS:
        sort = "created_at"
    if order not in ("asc", "desc"):
        order = "desc"
    recs.sort(key=lambda r: _sort_value(r, sort), reverse=(order == "desc"))

    total = len(recs)
    try:
        per_page = int(request.GET.get("per_page", 15))
    except (TypeError, ValueError):
        per_page = 15
    if per_page not in (10, 15, 20, 50):
        per_page = 15
    try:
        page = int(request.GET.get("page", 1)) or 1
    except (TypeError, ValueError):
        page = 1
    pages = max(1, -(-total // per_page)) if total else 1
    if page > pages:
        page = pages
    start = (page - 1) * per_page
    end = start + per_page
    page_recs = recs[start:end]

    serah_ids = [r["id"] for r in page_recs if r["bt"] == "SERAHAN"]
    pinjam_ids = [r["id"] for r in page_recs if r["bt"] == "PINJAMAN"]
    objs = {}
    for o in SerahanRequest.objects.filter(id__in=serah_ids).select_related("pic", "bahagian", "negeri"):
        objs[("SERAHAN", o.id)] = o
    for o in PinjamanRequest.objects.filter(id__in=pinjam_ids).select_related("pic", "bahagian", "negeri"):
        objs[("PINJAMAN", o.id)] = o

    rows = [row_json(objs[(r["bt"], r["id"])]) for r in page_recs if (r["bt"], r["id"]) in objs]
    return JsonResponse({"rows": rows, "total": total, "page": page, "pages": pages, "per_page": per_page})


@login_required
def request_detail(request, borang_type, request_id):
    obj = get_request_obj(borang_type, request_id)
    if not obj:
        return HttpResponseNotFound("Not found")

    user = request.user
    allowed = is_reviewer(user) or obj.pemohon_id == user.id or (obj.pic_id and obj.pic_id == user.id)
    if not allowed:
        return HttpResponseForbidden("Tiada akses")

    annotate_steps(obj)
    return render(request, "_request_detail.html", {
        "r": obj,
        "is_pengarah_bahagian": is_pengarah_bahagian(user),
        "is_bitg": is_bitg(user),
        "is_pic": is_pic(user),
    })


# =============================
# PENGARAH / PIC DASHBOARD
# =============================

@login_required
def pengarah_dashboard(request):
    user = request.user
    if is_pengarah_bahagian(user):
        scope = "bitg" if is_bitg(user) else "pb"
    elif is_pic(user):
        scope = "pic"
    else:
        return redirect("home")

    return render(request, "list_requests.html", {
        "page_title": "PAPAN KELULUSAN",
        "scope": scope,
        **request_list_context(),
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

    # Pengarah Bahagian (mesti bahagian sama dengan pemohon)
    if is_pengarah_bahagian(user) and data.status == "Borang Telah Dihantar":
        if user_bahagian(user) != data.bahagian:
            return HttpResponseForbidden("Bukan bahagian anda")
        if action == "reject":
            log_status(data, "Tidak Disokong Oleh Pengarah Bahagian", user, sebab_tolak=sebab or "-")
            send_notif("Permohonan Tidak Disokong", f"Permohonan ID {data.id} tidak disokong.\nSebab: {sebab}", [data.email])
        else:
            log_status(data, "Disokong Oleh Pengarah Bahagian", user)
            send_notif("Permohonan Diluluskan (Bahagian)", f"Permohonan ID {data.id} telah disokong oleh Pengarah Bahagian.", [data.email])
            send_notif("Permohonan Memerlukan Kelulusan BITG", f"ID: {data.id}\nPemohon: {data.namapemohon}\nSila login sistem untuk kelulusan.", bitg_emails())

    # BITG-level approval (Pengarah Bahagian dengan bahagian BITG)
    elif is_bitg(user) and data.status == "Disokong Oleh Pengarah Bahagian":
        if action == "reject":
            log_status(data, "Tidak Mendapat Kelulusan Pengarah BITG", user, ulasan=ulasan, sebab_tolak=sebab or "-")
            send_notif("Permohonan Tidak Diluluskan (BITG)", f"Permohonan ID {data.id} tidak diluluskan oleh Pengarah BITG.\nSebab: {sebab}", [data.email])
        else:
            log_status(data, "Mendapat Kelulusan Pengarah BITG", user, ulasan=ulasan)
            send_notif("Permohonan Diluluskan (BITG)", f"Permohonan ID {data.id} telah diluluskan oleh Pengarah BITG.\nUlasan: {ulasan or '-'}", [data.email])
            if data.borang_type == "SERAHAN":
                send_notif("Permohonan Memerlukan Penugasan PIC", f"ID: {data.id}\nPemohon: {data.namapemohon}\nSila login sistem untuk penugasan PIC.", bitg_emails())
            else:
                send_notif("Permohonan Memerlukan Penugasan", f"ID: {data.id}\nPemohon: {data.namapemohon}\nSila login sistem untuk penugasan PIC.", bitg_emails())
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

        # SERAHAN / PINJAMAN: BITG-level Pengarah assigns
        if data.borang_type == "SERAHAN" and is_bitg(user) and data.status == "Mendapat Kelulusan Pengarah BITG":
            data.pic = pic_user
            data.save()
            log_status(data, "Verifikasi Data Oleh PIC", user)
        elif data.borang_type == "PINJAMAN" and is_bitg(user) and data.status == "Mendapat Kelulusan Pengarah BITG":
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
    if not is_bitg(user):
        return redirect("home")

    borang_list = list(SerahanRequest.objects.filter(status="Mendapat Kelulusan Pengarah BITG")) + list(PinjamanRequest.objects.filter(status="Mendapat Kelulusan Pengarah BITG"))
    borang_list.sort(key=lambda o: o.created_at, reverse=True)
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

    # SERAHAN: PIC verifikasi / pembetulan (kembali kepada pemohon)
    if data.borang_type == "SERAHAN" and is_pic(user) and data.pic_id == user.id and data.status == "Verifikasi Data Oleh PIC":
        if action == "reject":
            log_status(data, "Pembetulan Oleh Pemohon", user, sebab_tolak=sebab or "-")
            send_notif(
                "Pembetulan Diperlukan",
                f"Data permohonan ID {data.id} perlu pembetulan.\nSebab: {sebab}\nSila login untuk mengedit dan menghantar semula.",
                [data.email],
            )
            send_notif("Pembetulan Diperlukan", f"Permohonan ID {data.id} dikembalikan kepada pemohon untuk pembetulan.\nSebab: {sebab}", bitg_emails())
        else:
            log_status(data, "Pengesahan Verifikasi", user)
            send_notif("Verifikasi Data Selesai", f"Verifikasi permohonan ID {data.id} selesai.", bitg_emails())

    # SERAHAN: BITG sahkan verifikasi -> serahan -> selesai
    elif data.borang_type == "SERAHAN" and is_bitg(user) and data.status == "Pengesahan Verifikasi":
        if action == "reject":
            log_status(data, "Verifikasi Data Oleh PIC", user, sebab_tolak=sebab or "-")
        else:
            log_status(data, "Serahan Data", user)
            log_status(data, "Selesai", user)
            send_notif("Serahan Data Selesai", f"Data permohonan ID {data.id} telah diserahkan.", [data.email])

    # PINJAMAN: PIC sahkan data sedia -> semakan oleh pemohon
    elif data.borang_type == "PINJAMAN" and is_pic(user) and data.pic_id == user.id and data.status == "Penyediaan Data":
        data.deadline = timezone.now() + timedelta(days=5)
        data.save()
        log_status(data, "Semakan Oleh Pemohon", user)
        send_notif("Data Sedia Untuk Semakan", f"Data permohonan ID {data.id} telah disediakan. Sila semak.", [data.email])

    # PINJAMAN: Pemohon sahkan penerimaan / kembali kepada PIC
    elif data.borang_type == "PINJAMAN" and data.pemohon_id == user.id and data.status == "Semakan Oleh Pemohon":
        if action == "reject":
            data.deadline = timezone.now() + timedelta(days=5)
            data.save()
            log_status(data, "Penyediaan Data", user, sebab_tolak=sebab or "-")
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
def upload_page(request):
    if not is_pic(request.user):
        return redirect("home")

    return render(request, "list_requests.html", {
        "page_title": "TUGASAN PIC",
        "scope": "pic",
        **request_list_context(),
    })


# =============================
# MANUAL STATUS OVERRIDE (ADMIN / PIC)
# =============================

@login_required
def status_update(request, borang_type=None, request_id=None):
    if not (is_admin(request.user) or is_pic(request.user)):
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
    meta_counter = Counter()

    def bump(counter, val):
        if val:
            counter[val] += 1

    for r in month_serah + month_pinjam:
        bump(komponen_counter, r.komponen_data)
        kawasan_counter[str(r.negeri) + "|" + str(r.daerah) + "|" + str(r.mukim)] += 1
        bump(jenis_counter, getattr(r, "jenis_data", None))
        bump(klas_counter, getattr(r, "klasifikasidata", None))
        bump(meta_counter, getattr(r, "meta_data", None))

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
        "top_metadata": field_list(meta_counter, "meta_data"),
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

        bahagian = Bahagian.objects.filter(id=request.POST.get("bahagian")).first()
        if not bahagian:
            messages.error(request, "Sila pilih bahagian.")
            return redirect("register")

        user = User.objects.create_user(username=username, email=email, password=password, first_name=fullname)
        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "phone": request.POST.get("telefon", "").strip(),
                "bahagian": bahagian,
            },
        )
        staff_group, created = Group.objects.get_or_create(name="Staff")
        user.groups.add(staff_group)
        login(request, user)
        messages.success(request, "Pendaftaran berjaya! Akaun anda telah didaftarkan.")
        return redirect("login")

    return render(request, "register.html", {"bahagian_list": Bahagian.objects.all()})


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
