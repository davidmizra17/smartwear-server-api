from django.test.runner import DiscoverRunner


class UnmanagedModelTestRunner(DiscoverRunner):
    """
    Makes managed=False models usable in tests by patching both the live model
    meta and the CreateModel migration operations before the test DB is built.
    """

    def setup_test_environment(self, **kwargs):
        from django.apps import apps
        self._unmanaged = [m for m in apps.get_models() if not m._meta.managed]
        for model in self._unmanaged:
            model._meta.managed = True
        super().setup_test_environment(**kwargs)

    def setup_databases(self, **kwargs):
        # Patch migration operations that carry managed=False so the test DB
        # actually creates those tables when running migrations.
        from django.db.migrations.loader import MigrationLoader
        loader = MigrationLoader(None, ignore_no_migrations=True)
        for migration in loader.disk_migrations.values():
            for op in migration.operations:
                if hasattr(op, "options") and not op.options.get("managed", True):
                    op.options = {**op.options, "managed": True}
        return super().setup_databases(**kwargs)

    def teardown_test_environment(self, **kwargs):
        super().teardown_test_environment(**kwargs)
        for model in self._unmanaged:
            model._meta.managed = False
