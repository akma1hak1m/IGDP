from django.contrib import admin
from .models import (
    DataRequest,
    Negeri,
    Daerah,
    Mukim,
    SerahanRequest,
    PinjamanRequest,
    StatusLog,
)

admin.site.register(DataRequest)

admin.site.register(SerahanRequest)
admin.site.register(PinjamanRequest)
admin.site.register(StatusLog)

admin.site.register(Negeri)
admin.site.register(Daerah)
admin.site.register(Mukim)
