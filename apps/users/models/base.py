from django.db import models


class AbstractPersonModel(models.Model):
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    id_number = models.CharField(max_length=50, blank=True)

    class Meta:
        abstract = True
