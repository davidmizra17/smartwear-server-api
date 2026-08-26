import fnmatch
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.imaging import process_and_store_image

DEFAULT_EXCLUDE_PATTERNS = ["hero.*", "identidad-*"]
VALID_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class Command(BaseCommand):
    help = (
        "One-time import of manually-downloaded product images (from the vendor's "
        "Google Drive folder) into object storage. Creates Image rows only — does "
        "not create Product/Variant/ProductImageLink rows, since filenames don't "
        "encode size/color/SKU. Link images to products afterward via the admin API."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dir", required=True, help="Local directory of downloaded images.")
        parser.add_argument(
            "--exclude",
            action="append",
            default=None,
            help="Filename glob pattern to skip (repeatable). Defaults to hero/identidad brand assets.",
        )

    def handle(self, *args, **options):
        source_dir = Path(options["dir"])
        if not source_dir.is_dir():
            raise CommandError(f"{source_dir} is not a directory")

        exclude_patterns = options["exclude"] or DEFAULT_EXCLUDE_PATTERNS

        results = []
        for path in sorted(source_dir.iterdir()):
            if not path.is_file() or path.suffix.lower() not in VALID_EXTENSIONS:
                continue
            if any(fnmatch.fnmatch(path.name.lower(), pattern.lower()) for pattern in exclude_patterns):
                self.stdout.write(f"skip (excluded): {path.name}")
                continue

            with path.open("rb") as f:
                image = process_and_store_image(f, original_filename=path.name)
            results.append((path.name, image.id))
            self.stdout.write(self.style.SUCCESS(f"imported: {path.name} -> {image.id}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Imported {len(results)} image(s)."))
        for filename, image_id in results:
            self.stdout.write(f"  {filename} -> {image_id}")
