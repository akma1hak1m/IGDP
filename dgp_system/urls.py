"""
URL configuration for dgp_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from requests_app import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.user_login, name='login'),

    path('home/', views.home, name='home'),

    path('borang-serahan/', views.borang_serahan, name='borang_serahan'),

    path('borang-serahan/<int:request_id>/edit/', views.borang_serahan_edit, name='borang_serahan_edit'),

    path('borang-pinjaman/<int:request_id>/edit/', views.borang_pinjaman_edit, name='borang_pinjaman_edit'),

    path('hantar-data/<int:request_id>/', views.pemohon_hantar_data, name='pemohon_hantar_data'),

    path('borang-pinjaman/', views.borang_pinjaman, name='borang_pinjaman'),

    path('status/', views.status_view, name='status'),

    path('logout/', views.user_logout, name='logout'),

    path('upload/', views.upload_page, name='upload_page'),

    path("flow-update/", views.flow_update, name="flow_update"),

    path("status-update/", views.status_update, name="status_update"),

    # KEEP ONLY THIS ONE
    path("status-update/<str:borang_type>/<int:request_id>/", views.status_update, name="status_update"),

    path("update-status/<str:borang_type>/<int:request_id>/<str:new_status>/", views.update_status, name="update_status"),
    
    path("verify/<str:borang_type>/<int:request_id>/", views.verify_data, name="verify_data"),

    path("admin-borang/", views.admin_borang, name="admin_borang"),

    path("requests-list/", views.requests_list, name="requests_list"),

    path("requests-detail/<str:borang_type>/<int:request_id>/", views.request_detail, name="request_detail"),

    path('pengarah/', views.pengarah_dashboard, name='pengarah_dashboard'),

    path('approve/<str:borang_type>/<int:request_id>/', views.approve_request, name='approve_request'),

    path('assign/<str:borang_type>/<int:request_id>/', views.assign_pic, name='assign_pic'),

    path('assign-pic/', views.assign_pic_page, name='assign_pic_page'),

    path("statistics/", views.statistics, name="statistics"),

    path("get-daerah/", views.get_daerah, name="get_daerah"),
    
    path("get-mukim/", views.get_mukim, name="get_mukim"),

    path("register/", views.register_page, name="register"),
    
    path("forgot-password/", views.forgot_password_page, name="forgot_password"),
    
    path(
    "reset/<uidb64>/<token>/",
    auth_views.PasswordResetConfirmView.as_view(
        template_name="reset_password.html"
    ),
    name="password_reset_confirm"),

    path(
        "reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="reset_complete.html"
        ),
        name="password_reset_complete")
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)