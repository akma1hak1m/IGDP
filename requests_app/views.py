from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseForbidden
from .models import DataRequest
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import HttpResponseForbidden
from django.contrib.auth.models import User, Group
from .models import LoginLog
from django.db.models import Count
from django.utils.timezone import now
from .models import DataRequest, LoginLog, Negeri, Daerah, Mukim
from django.http import JsonResponse
from .models import Negeri, Daerah, Mukim
from django.contrib import messages
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.db.models import Q
from datetime import datetime


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

    return render(request, "login.html", {
        "error": error
    })


def user_logout(request):
    logout(request)
    return redirect("login")


@login_required
def home(request):
    return render(request, "home.html")


# ---------- BORANG SERAHAN ----------
@login_required
def borang_serahan(request):

    if request.method == "POST":

        print("DATA SAVED:", request.POST)
        print("DATA SAVED:", request.POST)

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

        metadata=request.POST.get("meta_data")
        metadata_lain = request.POST.get("meta_lain")
            
        jenisdataformat = request.POST.getlist("jenisdataformat")

        klasifikasidata = request.POST.getlist("klasifikasidata")


        uploaded_file = request.FILES.get("file")

        daerah = request.POST.get("daerah")

        if daerah == "LAIN":
            daerah = request.POST.get("daerah_lain")

        mukim = request.POST.get("mukim")

        if mukim == "LAIN":
            mukim = request.POST.get("mukim_lain")

        obj = DataRequest.objects.create(

            borang_type="SERAHAN",

            namapemohon=request.POST.get("namapemohon"),
            email=request.POST.get("email"),
            telefon=request.POST.get("telefon"),

            
            komponen_data=", ".join(komponen) + ("  " + komponen_lain if komponen_lain else ""),

            negeri=request.POST.get("negeri"),
            daerah=daerah,
            mukim=mukim,

            indeks=request.POST.get("indeks"),

            jenis_data=", ".join(jenis) + ("  " + jenis_lain if jenis_lain else ""),
            format_data=", ".join(format_data) + ("  " + format_lain if format_lain else ""),
            unjuranKoordinat_data=", ".join(unjuran) + ("  " + unjuranKoordinat_lain if unjuranKoordinat_lain else ""),
            sumber_data=", ".join(sumber) + ("  " + sumber_lain if sumber_lain else ""),

            meta_data=(metadata or "") + ("  " + metadata_lain if metadata_lain else ""),

            namaagensikerjasama=request.POST.get("namaagensi"),
            namaprojek=request.POST.get("namaprojek"),
            tarikhprojek=request.POST.get("tarikhprojek"),

            namaagensiluar=request.POST.get("namaagensiluar"),
            namaprojekluar=request.POST.get("namaprojekluar"),
            tarikhprojekluar=request.POST.get("tarikhprojekluar"),

            jenisdataformat=", ".join(jenisdataformat),

            klasifikasidata=", ".join(klasifikasidata),



            pemohon=request.user,


            uploaded_file=uploaded_file
        )


         # ✅ EMAIL TO USER
        send_mail(
            subject='Permohonan Serahan Diterima',
            message=f'Hi {obj.namapemohon}, permohonan anda telah dihantar. ID: {obj.id}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[obj.email],
        )

        # 🔥 GET Pengarah Bahagian (OUTSIDE send_mail)
        pengarah_bahagian_users = User.objects.filter(groups__name="Pengarah Bahagian")

        emails = [user.email for user in pengarah_bahagian_users if user.email]

        # 📧 EMAIL TO PENGARAH BAHAGIAN
        send_mail(
            subject="Permohonan Baru Memerlukan Kelulusan",
            message=f"""
        Permohonan baru telah dihantar.

        ID: {obj.id}
        Pemohon: {obj.namapemohon}

        Sila login sistem untuk kelulusan.
        {login_link(request)}
        """,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=emails,
        )
        


        print("USER:", request.user)

        return redirect("status")
    
    negeri_list = Negeri.objects.all()

    return render(request, "borang_serahan.html", {
        "negeri_list": negeri_list
    })


# ---------- BORANG PINJAMAN ----------
@login_required
def borang_pinjaman(request):

    if request.method == "POST":

        print("DATA SAVED:", request.POST)
        print("DATA SAVED:", request.POST)

        komponen = request.POST.getlist("komponen_data")
        komponen_lain = request.POST.get("komponen_lain")

        uploaded_file = request.FILES.get("file")


        obj = DataRequest.objects.create(
            borang_type="PINJAMAN",

            namapemohon=request.POST.get("namapemohon"),
            email=request.POST.get("email"),
            telefon=request.POST.get("telefon"),

            komponen_data=", ".join(komponen) + ("  " + komponen_lain if komponen_lain else ""),

            negeri=request.POST.get("negeri"),
            daerah=request.POST.get("daerah"),
            mukim=request.POST.get("mukim"),
            indeks=request.POST.get("indeks"),

            tujuan=request.POST.get("tujuan"),
            cacatan=request.POST.get("cacatan"),

            Setuju = bool(request.POST.get("Setuju")),

            nama=request.POST.get("nama"),
            Tarikh=request.POST.get("Tarikh"),

            pemohon=request.user,

            uploaded_file=uploaded_file

        )

        # ✅ EMAIL TO USER
        send_mail(
            subject='Permohonan Pinjaman Diterima',
            message=f'Hi {obj.namapemohon}, permohonan anda telah dihantar. ID: {obj.id}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[obj.email],
        )

        # 🔥 GET Pengarah Bahagian
        pengarah_bahagian_users = User.objects.filter(groups__name="Pengarah Bahagian")

        emails = [user.email for user in pengarah_bahagian_users if user.email]

        # 📧 EMAIL TO PENGARAH BAHAGIAN
        send_mail(
            subject="Permohonan Baru Memerlukan Kelulusan",
            message=f"""
        Permohonan baru telah dihantar.

        ID: {obj.id}
        Pemohon: {obj.namapemohon}

        Sila login sistem untuk kelulusan.
        {login_link(request)}
        """,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=emails,
        )


        

        print("USER:", request.user)

        return redirect("status")
    
    negeri_list = Negeri.objects.all()

    return render(request, "borang_pinjaman.html", {
    "negeri_list": negeri_list
})


@login_required
def status_view(request):

    requests = DataRequest.objects.filter(
        pemohon=request.user
    ).order_by("-id")

    is_pic = request.user.groups.filter(name="PIC").exists()

    return render(request, "status.html", {
        "requests": requests,
        "is_pic": is_pic
    })


def is_pic(user):
    return user.groups.filter(name="PIC").exists()


@login_required
@user_passes_test(is_pic)
def upload_data(request, request_id):

    try:
        data_request = DataRequest.objects.get(id=request_id)
    except DataRequest.DoesNotExist:
        return HttpResponseForbidden()

    if request.method == "POST":

        uploaded_file = request.FILES.get("data_file")

        if uploaded_file:
            data_request.uploaded_file = uploaded_file
            data_request.status = "upload"
            data_request.save()

        return redirect("status")

    return render(request, "upload.html", {
        "request_obj": data_request
    })

@login_required
def status_view(request):

    is_pic = request.user.groups.filter(name="PIC").exists()

    if is_pic:
        # PIC can see all requests
        requests = DataRequest.objects.all().order_by("-id")
    else:
        # Staff only see their own request
        requests = DataRequest.objects.filter(
            pemohon=request.user
        ).order_by("-id")

    return render(request, "status.html", {
        "requests": requests,
        "is_pic": is_pic
    })

@login_required
def upload_data(request, request_id):

    data_request = DataRequest.objects.get(id=request_id)

    if request.method == "POST":
        file = request.FILES.get("file")

        if file:
            data_request.uploaded_file = file
            data_request.status = "upload"
            data_request.save()

            return redirect("status")

    return render(request, "upload_data.html", {
        "request_obj": data_request
    })

@login_required
def update_status(request, request_id, new_status):

    data_request = get_object_or_404(DataRequest, id=request_id)

    if request.user.is_superuser:
        data_request.status = new_status
        data_request.save()

    return redirect("status")

@login_required
def upload_data(request, request_id):

    data_request = get_object_or_404(DataRequest, id=request_id)

    if request.method == "POST":

        uploaded_file = request.FILES.get("file")

        if uploaded_file:
            data_request.uploaded_file = uploaded_file
            data_request.status = "verify"
            data_request.save()

        return redirect("status")

    return render(request, "upload.html", {"request": data_request})

@login_required
def verify_data(request, request_id):

    data_request = get_object_or_404(DataRequest, id=request_id)

    if request.user == data_request.pemohon:
        data_request.status = "complete"
        data_request.save()

    return redirect("status")

@login_required
def upload_page(request):

    if not request.user.groups.filter(name="PIC").exists():
        return redirect("home")

    return render(request,"upload.html")


@login_required
def status_update(request):

    requests = DataRequest.objects.all()

    return render(request, "status_update.html", {
        "requests": requests
    })

@login_required
def upload_page(request):

    if not request.user.groups.filter(name="PIC").exists():
        return redirect("home")

    requests = DataRequest.objects.filter(status="pic")

    return render(request, "upload.html", {
        "requests": requests
    })


@login_required
def status_update(request):

    requests = DataRequest.objects.all().order_by("-id")

    return render(request, "status_update.html", {
        "requests": requests
    })

@login_required
def flow_update(request):

    # Restrict access to PIC and Admin only
    if not request.user.groups.filter(name__in=["PIC","Admin"]).exists():
        return redirect("home")

    requests = DataRequest.objects.all().order_by("-id")

    return render(request, "status_update.html", {
        "requests": requests
    })


@login_required
def status_update(request, request_id):

    req = get_object_or_404(DataRequest, id=request_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        req.status = new_status
        req.save()

        return redirect("status")

    return render(request, "status_update.html", {"request": req})


@login_required
def admin_borang(request):

    if not request.user.groups.filter(
        name__in=["PIC", "Admin", "Pengarah Bahagian", "Pengarah BITG"]
    ).exists():
        return redirect("home")
    
    keyword = request.GET.get("q", "").strip()

    requests = DataRequest.objects.all().order_by("-id")

    if keyword:
        requests = requests.filter(
            Q(id__icontains=keyword) |
            Q(namapemohon__icontains=keyword) |
            Q(email__icontains=keyword) |
            Q(borang_type__icontains=keyword) |
            Q(status__icontains=keyword) |
            Q(negeri__icontains=keyword) |
            Q(daerah__icontains=keyword) |
            Q(mukim__icontains=keyword)
        )

    return render(request, "admin_borang.html", {
        "requests": requests,
        "keyword": keyword
    })


@login_required
def status_update(request, request_id):

    req = get_object_or_404(DataRequest, id=request_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        req.status = new_status
        req.save()
        return redirect("flow_update")

    return render(request, "status_update.html", {"request": req})

@login_required
def status_update(request, request_id):
    data = DataRequest.objects.get(id=request_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        data.status = new_status
        data.save()
        return redirect("status")

    return render(request, "status_update.html", {"data": data})

@login_required
def status_update(request, request_id):
    data = DataRequest.objects.get(id=request_id)

    return render(request, "status_update.html", {
        "data": data
    })

@login_required
def status_update(request, request_id=None):

    if request_id:
        data = DataRequest.objects.filter(id=request_id).first()
        all_requests = DataRequest.objects.all()
    else:
        data = None
        all_requests = DataRequest.objects.all()

    if request.method == "POST":
        req_id = request.POST.get("request_id")
        new_status = request.POST.get("status")

        obj = DataRequest.objects.get(id=req_id)
        obj.status = new_status
        obj.save()

        # ✅ SEND EMAIL TO USER
        send_mail(
            subject='Status Permohonan Dikemaskini',
            message=f'''
Hi {obj.namapemohon},

Status permohonan anda telah dikemaskini.

ID: {obj.id}
Status Baru: {new_status}

Sila login sistem untuk semakan lanjut.
            ''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[obj.email],
        )

        return redirect("status_update", request_id=req_id)

    return render(request, "status_update.html", {
        "data": data,
        "all_requests": all_requests
    })


def is_pengarah_bahagian(user):
    return user.groups.filter(name="Pengarah Bahagian").exists()

def is_pengarah_bitg(user):
    return user.groups.filter(name="Pengarah BITG").exists()


@login_required
def pengarah_dashboard(request):

    user = request.user

    if is_pengarah_bahagian(user):
        requests = DataRequest.objects.filter(status="submit")

    elif is_pengarah_bitg(user):
        requests = DataRequest.objects.filter(status="bahagian")

    else:
        return redirect("home")

    return render(request, "pengarah_dashboard.html", {
        "requests": requests
    })

@login_required
def approve_request(request, request_id):

    data = get_object_or_404(DataRequest, id=request_id)
    user = request.user

    # 👔 Pengarah Bahagian
    if user.groups.filter(name="Pengarah Bahagian").exists() and data.status == "Borang Telah Dihantar":
        data.status = "Pengarah Bahagian Telah Sahkan"

        # 🔥 STEP 3: EMAIL TO BITG
        bitg_users = User.objects.filter(groups__name="Pengarah BITG")
        emails = [u.email for u in bitg_users if u.email]

        send_mail(
            subject="Permohonan Memerlukan Kelulusan BITG",
            message=f"""
Permohonan telah diluluskan oleh Pengarah Bahagian.

ID: {data.id}
Pemohon: {data.namapemohon}

Sila login sistem untuk kelulusan seterusnya.
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=emails,
        )

    # 👔 Pengarah BITG
    elif user.groups.filter(name="Pengarah BITG").exists() and data.status == "Pengarah Bahagian Telah Sahkan":
        data.status = "Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik"

    else:
        return HttpResponseForbidden("Not allowed")

    data.save()

    return redirect("pengarah_dashboard")

@login_required
def assign_pic(request, request_id):

    data = get_object_or_404(DataRequest, id=request_id)

    if not request.user.groups.filter(name="Pengarah BITG").exists():
        return HttpResponseForbidden("Not allowed")

    if request.method == "POST":
        pic_id = request.POST.get("pic")
        data.pic_id = pic_id
        data.status = "Penugasan PIC"
        data.save()

        return redirect("pengarah_dashboard")

    pics = User.objects.filter(groups__name="PIC")

    return render(request, "assign_pic.html", {
        "data": data,
        "pics": pics
    })

@login_required
def approve_request(request, request_id):

    data = get_object_or_404(DataRequest, id=request_id)
    user = request.user

    # 👔 Pengarah Bahagian
    if user.groups.filter(name="Pengarah Bahagian").exists() and data.status == "Borang Telah Dihantar":
        data.status = "Pengarah Bahagian Telah Sahkan"

        send_mail(
            subject="Permohonan Diluluskan (Bahagian)",
            message=f"""
Hi {data.namapemohon},

Permohonan anda (ID: {data.id}) telah diluluskan oleh Pengarah Bahagian.

Sila tunggu kelulusan seterusnya.
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[data.email],
        )

    # 👔 Pengarah BITG
    elif user.groups.filter(name="Pengarah BITG").exists() and data.status == "Pengarah Bahagian Telah Sahkan":
        data.status = "Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik"

        send_mail(
            subject="Permohonan Diluluskan (BITG)",
            message=f"""
Hi {data.namapemohon},

Permohonan anda (ID: {data.id}) telah diluluskan oleh Pengarah BITG.

Proses seterusnya adalah penugasan PIC.
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[data.email],
        )

    else:
        return HttpResponseForbidden("Not allowed")

    data.save()

    return redirect("pengarah_dashboard")

@login_required
def pengarah_dashboard(request):

    user = request.user

    if user.groups.filter(name="Pengarah Bahagian").exists():
        requests = DataRequest.objects.filter(status="Borang Telah Dihantar")

    elif user.groups.filter(name="Pengarah BITG").exists():
        requests = DataRequest.objects.filter(status="Pengarah Bahagian Telah Sahkan")

    else:
        requests = []

    return render(request, "pengarah_dashboard.html", {
        "requests": requests
    })

@login_required
def assign_pic(request, request_id):

    data = get_object_or_404(DataRequest, id=request_id)

    if not request.user.groups.filter(name="Pengarah BITG").exists():
        return HttpResponseForbidden("Not allowed")

    if data.status != "Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik":
        return HttpResponseForbidden("Invalid stage")

    if request.method == "POST":
        pic_id = request.POST.get("pic")

        data.pic_id = pic_id
        data.status = "Penugasan PIC"
        data.save()

        # 🔥 GET PIC USER
        pic_user = User.objects.get(id=pic_id)

        # 📧 EMAIL TO USER
        send_mail(
            subject="PIC Telah Ditetapkan",
            message=f"""
Hi {data.namapemohon},

Permohonan anda (ID: {data.id}) telah diberikan kepada PIC untuk diproses.

Sila tunggu perkembangan seterusnya.
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[data.email],
        )

        # 📧 EMAIL TO PIC
        send_mail(
            subject="Tugasan Baru Diterima",
            message=f"""
Hi {pic_user.username},

Anda telah ditugaskan untuk mengurus permohonan berikut:

ID: {data.id}
Pemohon: {data.namapemohon}

Sila login sistem untuk tindakan lanjut.
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[pic_user.email],
        )

        return redirect("pengarah_dashboard")

    pics = User.objects.filter(groups__name="PIC")

    return render(request, "assign_pic.html", {
        "data": data,
        "pics": pics
    })
@login_required
def assign_pic_page(request):

    # 🔒 Only Pengarah BITG
    if not request.user.groups.filter(name="Pengarah BITG").exists():
        return HttpResponseForbidden("Not allowed")

    # ✅ Only show approved by BITG
    borang_list = DataRequest.objects.filter(
        status="Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik"
    )

    return render(request, "assign_pic.html", {
        "borang_list": borang_list
    })

@login_required
def assign_pic_page(request):

    if not request.user.groups.filter(name="Pengarah BITG").exists():
        return HttpResponseForbidden("Not allowed")

    borang_list = DataRequest.objects.filter(
        status="Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik"
    )

    pics = User.objects.filter(groups__name="PIC")

    return render(request, "assign_pic.html", {
        "borang_list": borang_list,
        "users": pics
    })

@login_required
def approve_request(request, request_id):

    data = get_object_or_404(DataRequest, id=request_id)
    user = request.user

    # ====================================
    # PENGARAH BAHAGIAN APPROVE
    # ====================================
    if user.groups.filter(name="Pengarah Bahagian").exists():

        if data.status != "Borang Telah Dihantar":
            return HttpResponseForbidden("Invalid stage")

        data.status = "Pengarah Bahagian Telah Sahkan"
        data.save()

        # Email user
        send_mail(
            subject="Permohonan Diluluskan (Bahagian)",
            message=f"""
Hi {data.namapemohon},

Permohonan anda (ID: {data.id}) telah diluluskan oleh Pengarah Bahagian.

Sila tunggu kelulusan Pengarah BITG.
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[data.email],
        )

        # Email BITG
        bitg_users = User.objects.filter(groups__name="Pengarah BITG")
        emails = [u.email for u in bitg_users if u.email]

        if emails:
            send_mail(
                subject="Permohonan Memerlukan Kelulusan BITG",
                message=f"""
Permohonan baru memerlukan kelulusan anda.

ID: {data.id}
Pemohon: {data.namapemohon}

Sila login sistem:
{login_link(request)}
""",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=emails,
            )

    # ====================================
    # PENGARAH BITG APPROVE
    # ====================================
    elif user.groups.filter(name="Pengarah BITG").exists():

        if data.status != "Pengarah Bahagian Telah Sahkan":
            return HttpResponseForbidden("Invalid stage")

        data.status = "Mendapat Kelulusan Daripada Pengarah Bahagian Pembangunan ICT Dan Geoinformatik"
        data.save()

        # Email user
        send_mail(
            subject="Permohonan Diluluskan (BITG)",
            message=f"""
Hi {data.namapemohon},

Permohonan anda (ID: {data.id}) telah diluluskan oleh Pengarah BITG.

Proses seterusnya adalah penugasan PIC.
""",
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[data.email],
        )

        # ONLY SERAHAN send to PIC
        if data.borang_type == "SERAHAN":

            pic_users = User.objects.filter(groups__name="PIC")
            pic_emails = [u.email for u in pic_users if u.email]

            if pic_emails:
                send_mail(
                    subject="BORANG SERAHAN Baru Untuk Tindakan PIC",
                    message=f"""
BORANG SERAHAN telah diluluskan oleh Pengarah BITG.

ID: {data.id}
Pemohon: {data.namapemohon}

Sila login sistem:
{login_link(request)}
""",
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=pic_emails,
                )

    else:
        return HttpResponseForbidden("Not allowed")

    return redirect("pengarah_dashboard")

def statistics(request):

    current = now()

    month = request.GET.get("month", current.month)
    year = request.GET.get("year", current.year)

    month = int(month)
    year = int(year)

    current_year = datetime.now().year

    # LOGIN REPORT
    logins = LoginLog.objects.filter(
        login_time__month=month,
        login_time__year=year
    )

    total_login = logins.count()
    unique_users = logins.values("user").distinct().count()

    requests = DataRequest.objects.filter(
        created_at__month=month,
        created_at__year=year
    )

    total_serahan = requests.filter(
        borang_type="SERAHAN"
    ).count()

    total_pinjaman = requests.filter(
        borang_type="PINJAMAN"
    ).count()

    top_komponen = requests.values(
        "komponen_data"
    ).annotate(
        total=Count("komponen_data")
    ).order_by("-total")[:5]

    top_kawasan = requests.values(
        "negeri", "daerah", "mukim"
    ).annotate(
        total=Count("id")
    ).order_by("-total")[:5]

    top_metadata = requests.values(
        "meta_data"
    ).annotate(
        total=Count("meta_data")
    ).order_by("-total")[:5]

    top_jenis = requests.values(
        "jenis_data"
    ).annotate(
        total=Count("jenis_data")
    ).order_by("-total")[:5]

    top_klasifikasi = requests.values(
        "klasifikasidata"
    ).annotate(
        total=Count("klasifikasidata")
    ).order_by("-total")[:5]

    context = {
        "month": month,
        "year": year,

        "years": range(current_year, current_year - 5, -1),

        "total_login": total_login,
        "unique_users": unique_users,
        "total_serahan": total_serahan,
        "total_pinjaman": total_pinjaman,

        "top_komponen": top_komponen,
        "top_kawasan": top_kawasan,
        "top_metadata": top_metadata,
        "top_jenis": top_jenis,
        "top_klasifikasi": top_klasifikasi,
    }

    return render(request, "statistics.html", context)

def get_daerah(request):

    negeri_name = request.GET.get("negeri")

    negeri = Negeri.objects.filter(
        nama__iexact=negeri_name
    ).first()

    if not negeri:
        return JsonResponse([], safe=False)

    data = list(
        Daerah.objects.filter(negeri=negeri)
        .values("id", "nama")
        .order_by("nama")
    )

    return JsonResponse(data, safe=False)


def get_mukim(request):

    daerah_name = request.GET.get("daerah")

    daerah = Daerah.objects.filter(
        nama__iexact=daerah_name
    ).first()

    if not daerah:
        return JsonResponse([], safe=False)

    data = list(
        Mukim.objects.filter(daerah=daerah)
        .values("id", "nama")
        .order_by("nama")
    )

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

        # =====================
        # VALIDATION
        # =====================
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

        # =====================
        # CREATE USER
        # =====================
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=fullname
        )

        # =====================
        # AUTO ADD STAFF ROLE
        # =====================
        staff_group, created = Group.objects.get_or_create(name="Staff")
        user.groups.add(staff_group)

        # =====================
        # AUTO LOGIN
        # =====================
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
                reverse(
                    "password_reset_confirm",
                    kwargs={
                        "uidb64": uid,
                        "token": token
                    }
                )
            )

            send_mail(
                "Reset Kata Laluan MYSA",
                f"Klik pautan berikut:\n{link}",
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False
            )

            messages.success(request, "Link reset dihantar ke email.")

        except:
            messages.error(request, "Email tidak dijumpai.")

        return redirect("forgot_password")

    return render(request, "forgot_password.html")


def login_link(request):
    return request.build_absolute_uri("/")


