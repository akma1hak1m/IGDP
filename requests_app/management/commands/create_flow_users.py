import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from requests_app.models import UserProfile, Bahagian

ROLES = {
    "pemohon": ["Staff"],
    "pengarah_bahagian": ["Pengarah Bahagian"],
    "pengarah_bitg": ["Pengarah Bahagian"],
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
        parser.add_argument(
            "--bahagian",
            default="BS",
            help="Bahagian assigned to pemohon and pengarah_bahagian (default: BS).",
        )

    def handle(self, *args, **opts):
        password = opts["password"] or DEFAULT_PASSWORD
        bahagian = Bahagian.objects.filter(nama=opts["bahagian"]).first()
        if not bahagian:
            self.stderr.write(self.style.ERROR(f"Bahagian '{opts['bahagian']}' tidak wujud."))
            return
        rows = []
        for username, groups in ROLES.items():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@mysa.local", "first_name": username},
            )
            user.set_password(password)
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if username in ("pemohon", "pengarah_bahagian"):
                profile.bahagian = bahagian
                profile.save()
            if username == "pengarah_bitg":
                bitg = Bahagian.objects.filter(nama="BITG").first()
                profile.bahagian = bitg
                profile.save()
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
