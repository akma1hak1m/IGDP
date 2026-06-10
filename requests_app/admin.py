from django.contrib import admin
from .models import DataRequest
from .models import Negeri, Daerah, Mukim

admin.site.register(DataRequest)


admin.site.register(Negeri)
admin.site.register(Daerah)
admin.site.register(Mukim)