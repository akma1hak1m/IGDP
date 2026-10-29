from django.apps import AppConfig
from django.contrib.auth.validators import UnicodeUsernameValidator


class RequestsAppConfig(AppConfig):
    name = 'requests_app'

    def ready(self):
        from django.contrib.auth.models import User

        username_field = User._meta.get_field('username')
        username_field.validators = [
            v for v in username_field.validators
            if not isinstance(v, UnicodeUsernameValidator)
        ]
