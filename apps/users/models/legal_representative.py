from apps.users.models.base import AbstractPersonModel


class LegalRepresentative(AbstractPersonModel):
    class Meta:
        db_table = "users_legalrepresentative"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
