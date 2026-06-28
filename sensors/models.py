from django.db import models


class SensorData(models.Model):
	received_at = models.DateTimeField(auto_now_add=True)
	payload = models.JSONField()

	class Meta:
		ordering = ["-received_at"]

	def __str__(self) -> str:
		return f"SensorData(id={self.id}, received_at={self.received_at:%Y-%m-%d %H:%M:%S})"


class GPSReading(models.Model):
	"""A validated GPS transmission received from a tracking device."""

	device_id = models.CharField(max_length=50, db_index=True)
	latitude = models.DecimalField(max_digits=10, decimal_places=7)
	longitude = models.DecimalField(max_digits=10, decimal_places=7)
	recorded_at = models.DateTimeField()
	received_at = models.DateTimeField(auto_now_add=True)
	gps_fix = models.BooleanField(default=True)
	satellites = models.PositiveSmallIntegerField(null=True, blank=True)
	speed_kph = models.DecimalField(
		max_digits=8, decimal_places=2, null=True, blank=True
	)
	heading = models.DecimalField(
		max_digits=6, decimal_places=2, null=True, blank=True
	)
	battery_percent = models.PositiveSmallIntegerField(null=True, blank=True)
	signal_strength = models.SmallIntegerField(null=True, blank=True)
	sequence_number = models.BigIntegerField()
	raw_payload = models.JSONField(null=True, blank=True)

	class Meta:
		ordering = ["-id"]
		constraints = [
			models.UniqueConstraint(
				fields=["device_id", "sequence_number"],
				name="unique_gps_device_sequence",
			),
		]
		indexes = [
			models.Index(
				fields=["device_id", "received_at"],
				name="gps_device_received_idx",
			),
		]

	def __str__(self) -> str:
		return (
			f"GPSReading(device={self.device_id}, sequence={self.sequence_number}, "
			f"position={self.latitude},{self.longitude})"
		)
