import os, sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "valuenetwork.settings")

import django
django.setup()


from pinax.notifications import models as notification

nts = notification.NoticeType.objects.all()

for nt in nts:
    pass #nt.default = 0
    #nt.save()

print()
print("not changed ", nts.count(), "NoticeType defaults to 0.")

nsets = notification.NoticeSetting.objects.all()

for nset in nsets:
    pass #nset.send = False
    #nset.save()

print("not changed ", nsets.count(), "NoticeSetting send flags to False.")
print("This don't turn off all email notifications.")

