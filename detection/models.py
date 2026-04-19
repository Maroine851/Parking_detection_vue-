from django.db import models


class ParkingLog(models.Model):
    """
    Mappe la table parking_log déjà créée par parking.py
    Django ne la recrée pas — elle existe déjà dans parking.db
    """
    spot     = models.CharField(max_length=20)
    car_id   = models.CharField(max_length=20)
    duration = models.FloatField()   # en minutes
    price    = models.FloatField()   # en MAD

    class Meta:
        # ← nom exact de la table créée par parking.py
        db_table  = 'parking_log'
        # ← Django ne touche pas à cette table (elle est gérée par parking.py)
        managed   = False

    def __str__(self):
        return f"{self.spot} | {self.car_id} | {self.duration:.1f} min | {self.price:.2f} MAD"