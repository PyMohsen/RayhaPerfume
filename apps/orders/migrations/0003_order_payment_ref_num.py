from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_rename_payment_authority_payment_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='payment_ref_num',
            field=models.CharField(
                blank=True,
                max_length=50,
                null=True,
                unique=True,
                verbose_name='رسید دیجیتال SEP',
            ),
        ),
    ]
