# Generated by Django 2.1.7 on 2019-04-25 12:50

from django.db import migrations
import hashid_field.field
from hashid_field import Hashid

from zds.member.models import Profile


def update_ids(*args, **kwargs):
    for profile in Profile.objects.all():
        profile.rss_token = Hashid(profile.pk)
        profile.save()


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0018_auto_20190114_1301'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='Jeton RSS',
            field=hashid_field.field.HashidField(
                alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890', default=Hashid(1),
                editable=False, min_length=7, unique=False, verbose_name='Jeton pour les flux personnels CSS'),
            preserve_default=False,
        ),
        migrations.RunPython(update_ids),
    ]
