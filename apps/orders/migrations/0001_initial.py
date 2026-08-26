import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.TextField(unique=True)),
                ("sku", models.TextField(blank=True, null=True)),
            ],
            options={
                "db_table": "product",
                "managed": False,
            },
        ),
    ]
