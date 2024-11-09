# Generated by Django 5.0 on 2024-11-09 17:40

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    operations = [
        migrations.AddField(
            model_name='admininfo',
            name='paystack_active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='afaregistration',
            name='amount',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='bigtimetransaction',
            name='amount',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='isharebundletransaction',
            name='amount',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='mtntransaction',
            name='amount',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='topuprequest',
            name='payment_channel',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='vodafonetransaction',
            name='amount',
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name='afaregistration',
            name='transaction_status',
            field=models.CharField(choices=[('Pending', 'Pending'), ('Completed', 'Completed'), ('Processing', 'Processing'), ('Failed', 'Failed')], default='Pending', max_length=100),
        ),
        migrations.AlterField(
            model_name='bigtimetransaction',
            name='transaction_status',
            field=models.CharField(choices=[('Pending', 'Pending'), ('Completed', 'Completed'), ('Processing', 'Processing'), ('Failed', 'Failed')], default='Pending', max_length=100),
        ),
        migrations.AlterField(
            model_name='mtntransaction',
            name='transaction_status',
            field=models.CharField(choices=[('Pending', 'Pending'), ('Processing', 'Processing'), ('Completed', 'Completed'), ('Failed', 'Failed')], default='Completed', max_length=100),
        ),
    ]
