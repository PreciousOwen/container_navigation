from django.db import models


class SensorData(models.Model):
	received_at = models.DateTimeField(auto_now_add=True)
	payload = models.JSONField()

	class Meta:
		ordering = ["-received_at"]

	def __str__(self) -> str:
		return f"SensorData(id={self.id}, received_at={self.received_at:%Y-%m-%d %H:%M:%S})"
