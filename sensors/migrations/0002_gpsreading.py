# Generated manually for the GPS tracking API.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sensors", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GPSReading",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("device_id", models.CharField(db_index=True, max_length=50)),
                ("latitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("longitude", models.DecimalField(decimal_places=7, max_digits=10)),
                ("recorded_at", models.DateTimeField()),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("gps_fix", models.BooleanField(default=True)),
                (
                    "satellites",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "speed_kph",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=8, null=True
                    ),
                ),
                (
                    "heading",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=6, null=True
                    ),
                ),
                (
                    "battery_percent",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                ("signal_strength", models.SmallIntegerField(blank=True, null=True)),
                ("sequence_number", models.BigIntegerField()),
                ("raw_payload", models.JSONField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-id"],
                "indexes": [
                    models.Index(
                        fields=["device_id", "received_at"],
                        name="gps_device_received_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("device_id", "sequence_number"),
                        name="unique_gps_device_sequence",
                    )
                ],
            },
        ),
    ]
