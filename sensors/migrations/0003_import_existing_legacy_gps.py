from decimal import Decimal, InvalidOperation

from django.db import migrations


LEGACY_SEQUENCE_OFFSET = 9_000_000_000_000_000


def import_existing_legacy_gps(apps, schema_editor):
    SensorData = apps.get_model("sensors", "SensorData")
    GPSReading = apps.get_model("sensors", "GPSReading")

    for entry in SensorData.objects.order_by("id").iterator():
        payload = entry.payload
        if not isinstance(payload, dict) or "gps_location" not in payload:
            continue
        parts = str(payload.get("gps_location", "")).split(",")
        if len(parts) != 2:
            continue
        try:
            latitude = Decimal(parts[0].strip())
            longitude = Decimal(parts[1].strip())
        except (InvalidOperation, ValueError):
            continue
        if not latitude.is_finite() or not longitude.is_finite():
            continue
        if not Decimal("-90") <= latitude <= Decimal("90"):
            continue
        if not Decimal("-180") <= longitude <= Decimal("180"):
            continue
        if latitude == 0 and longitude == 0:
            continue

        device_id = str(
            payload.get("device_id")
            or payload.get("sensor_id")
            or "GPS-PROTOTYPE-001"
        ).strip()[:50]
        GPSReading.objects.get_or_create(
            device_id=device_id,
            sequence_number=LEGACY_SEQUENCE_OFFSET + entry.id,
            defaults={
                "latitude": latitude,
                "longitude": longitude,
                "recorded_at": entry.received_at,
                "gps_fix": True,
                "raw_payload": payload,
            },
        )


def remove_imported_legacy_gps(apps, schema_editor):
    GPSReading = apps.get_model("sensors", "GPSReading")
    GPSReading.objects.filter(
        sequence_number__gte=LEGACY_SEQUENCE_OFFSET
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sensors", "0002_gpsreading"),
    ]

    operations = [
        migrations.RunPython(
            import_existing_legacy_gps,
            remove_imported_legacy_gps,
        ),
    ]
