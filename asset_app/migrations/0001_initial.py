# Generated by Django 5.2 on 2025-07-01 09:39

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AssetAssignmentHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_assigned', models.DateTimeField()),
                ('date_returned', models.DateTimeField()),
                ('location', models.CharField(choices=[('Main Room', 'Main Room'), ('Meeting Room', 'Meeting Room'), ('Main Office', 'Main Office')], max_length=100)),
                ('notes', models.TextField(blank=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'Assignment Histories',
                'ordering': ['-date_returned'],
            },
        ),
        migrations.CreateModel(
            name='AssetCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=100, unique=True)),
                ('has_os', models.BooleanField(default=False)),
                ('has_ip', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='AssetIssue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reported_date', models.DateTimeField(auto_now_add=True)),
                ('issue_type', models.CharField(choices=[('hardware', 'Hardware Problem'), ('software', 'Software Problem'), ('performance', 'Performance Issue'), ('other', 'Other')], max_length=20)),
                ('description', models.TextField()),
                ('notes', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('resolved', 'Resolved')], default='pending', max_length=20)),
                ('resolved_date', models.DateTimeField(blank=True, null=True)),
                ('resolution_method', models.TextField(blank=True, help_text='How the issue was resolved', null=True)),
                ('time_taken', models.DurationField(blank=True, help_text='Time taken to resolve the issue', null=True)),
                ('is_recurring', models.BooleanField(default=False, help_text='Does this issue occur frequently?')),
                ('recurrence_notes', models.TextField(blank=True, help_text='Notes about recurring issues', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Assets',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset_name', models.CharField(blank=True, max_length=100, null=True)),
                ('asset_serial_number', models.CharField(blank=True, max_length=100, unique=True)),
                ('asset_brand', models.CharField(max_length=100)),
                ('asset_image', models.ImageField(blank=True, null=True, upload_to='images/')),
                ('is_asset_issued', models.BooleanField(default=False)),
                ('asset_added_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_date', models.DateTimeField(auto_now=True)),
                ('return_date', models.DateTimeField(blank=True, null=True)),
                ('asset_condition', models.CharField(blank=True, choices=[('new', 'New'), ('used', 'Used')], max_length=100, null=True)),
                ('os_version', models.CharField(blank=True, default=None, max_length=100, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, default=None, null=True)),
                ('processor', models.CharField(blank=True, max_length=100, null=True)),
                ('ram', models.CharField(blank=True, max_length=50, null=True)),
                ('storage', models.CharField(blank=True, max_length=50, null=True)),
                ('barcode', models.ImageField(blank=True, null=True, upload_to='barcodes/')),
                ('quantity', models.PositiveIntegerField(default=1)),
            ],
        ),
        migrations.CreateModel(
            name='AssetsIssuance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('asset_location', models.CharField(choices=[('Main Room', 'Main Room'), ('Meeting Room', 'Meeting Room'), ('Main Office', 'Main Office')], max_length=100)),
                ('date_issued', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
        migrations.CreateModel(
            name='Assetssearch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('location', models.CharField(max_length=255)),
                ('description', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Notify_Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_read', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'Employee Notification',
                'verbose_name_plural': 'Employee Notifications',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='Notify_Manager',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('approved', models.BooleanField(default=None, null=True)),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_read', models.BooleanField(default=False)),
            ],
        ),
    ]
