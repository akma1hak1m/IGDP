import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from requests_app.models import UserProfile

ROLES = {
    "pemohon": ["Staff"],
    "pengarah_bahagian": ["Pengarah Bahagian"],
    "pengarah_bitg": ["Pengarah BITG"],
    "pengurus_pangkalan": ["Pengurus Pengkalan Data"],
    "pic": ["PIC"],
}

DEFAULT_PASSWORD = os.environ.get("FLOW_USER_PASSWORD", "MysaDgb@123")


class Command(BaseCommand):
    help = (
        "Create users for the serahan/pinjaman workflow roles. "
        "Idempotent: existing users are updated (password reset + groups ensured)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=None,
            help="Password for all created users (default: env FLOW_USER_PASSWORD or placeholder).",
        )

    def handle(self, *args, **opts):
        password = opts["password"] or DEFAULT_PASSWORD
        rows = []
        for username, groups in ROLES.items():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@mysa.local", "first_name": username},
            )
            user.set_password(password)
            user.save()
            UserProfile.objects.get_or_create(user=user)
            for group_name in groups:
                group, _ = Group.objects.get_or_create(name=group_name)
                user.groups.add(group)
            rows.append((username, " ".join(groups), "created" if created else "exists"))

        self.stdout.write("Workflow users:")
        for username, groups, state in rows:
            self.stdout.write(f"  {username:<20} groups={groups:<35} {state}")

        if opts["password"] is None and "FLOW_USER_PASSWORD" not in os.environ:
            self.stderr.write(
                self.style.WARNING(
                    f"\nUsed default password '{DEFAULT_PASSWORD}'. "
                    "Change it now (manage.py changepassword <user>) or set FLOW_USER_PASSWORD env var."
                )
            )
