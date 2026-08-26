from apps.users.models.base import AbstractPersonModel


class LegalRepresentative(AbstractPersonModel):
    # email inherits unique=True from AbstractPersonModel. This is intentional:
    # each LegalRepresentative is a distinct legal entity identified by email,
    # and the OneToOneField on Tenant means one rep can only be linked to one tenant.
    # If the requirement changes to allow one firm to represent multiple tenants,
    # drop unique=True from AbstractPersonModel and re-add it only to User.

    class Meta:
        db_table = "users_legalrepresentative"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
