# -*- coding: utf-8 -*-
# Generated by Django 1.11.9 on 2018-08-26 16:16
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('member', '0017_profile_email_for_new_mp'),
        ('utils', '0022_auto_20190115_1249'),
    ]

    operations = [
        migrations.AddField(
            model_name='alert',
            name='profile',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='alerts_on_this_profile', to='member.Profile', verbose_name='Profil'),
        ),
        migrations.AlterField(
            model_name='alert',
            name='scope',
            field=models.CharField(choices=[('PROFILE', 'Profil'), ('FORUM', 'Forum'), ('CONTENT', 'Contenu'), ('TUTORIAL', 'Tutoriel'), ('ARTICLE', 'Article'), ('OPINION', 'Billet')], db_index=True, max_length=10),
        ),
    ]
