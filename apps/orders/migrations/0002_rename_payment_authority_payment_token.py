from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='order',
            old_name='payment_authority',
            new_name='payment_token',
        ),
        migrations.AlterField(
            model_name='order',
            name='payment_token',
            field=models.CharField(
                blank=True,
                max_length=50,
                verbose_name='توکن پرداخت سپ',
            ),
        ),
    ]
