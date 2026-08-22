"""
Kaggle dataset download client.

Downloads the Zomato delivery dataset from Kaggle using the Kaggle Python
library. Credentials are injected from the project settings object so
callers never need to manage environment variables directly.

After extraction the downloaded CSV is renamed to the project's canonical
filename (``delivery_data.csv``) regardless of what Kaggle calls it.
"""

import os
import shutil
from pathlib import Path

import structlog

from config.settings import get_settings

log = structlog.get_logger(__name__)

# Canonical filename used throughout the project, regardless of Kaggle's name.
CANONICAL_FILENAME = "delivery_data.csv"


def _configure_kaggle_credentials() -> None:
    """
    Inject Kaggle credentials from settings into the environment.

    The ``kaggle`` library reads ``KAGGLE_USERNAME`` and ``KAGGLE_KEY``
    from the environment. This function ensures those are set from the
    project settings object so the caller does not have to manage them.
    """
    s = get_settings()
    os.environ["KAGGLE_USERNAME"] = s.kaggle_username
    os.environ["KAGGLE_KEY"] = s.kaggle_key


def download_dataset(
    download_dir: Path,
    *,
    dataset_slug: str | None = None,
) -> Path:
    """
    Download the configured Kaggle dataset and extract it to ``download_dir``.

    Args:
        download_dir: Directory where the dataset will be extracted.
                      Created automatically if it does not exist.
        dataset_slug: Kaggle dataset identifier (``owner/name``).
                      Defaults to the value in settings.

    Returns:
        Path to the downloaded CSV file (``delivery_data.csv``).

    Raises:
        FileNotFoundError: If no CSV file is found after extraction.
        RuntimeError: If the Kaggle API call fails.
    """
    _configure_kaggle_credentials()

    slug = dataset_slug or get_settings().kaggle_dataset
    download_dir.mkdir(parents=True, exist_ok=True)

    log.info("kaggle.download.start", dataset=slug, destination=str(download_dir))

    try:
        # Import inside the function so tests can patch kaggle.api before
        # any module-level import side-effects are triggered.
        import kaggle

        kaggle.api.authenticate()
        kaggle.api.dataset_download_files(
            slug,
            path=str(download_dir),
            unzip=True,
            quiet=False,
        )
    except Exception as exc:
        log.error("kaggle.download.failed", dataset=slug, error=str(exc))
        raise RuntimeError(f"Kaggle download failed for dataset '{slug}': {exc}") from exc

    csv_files = list(download_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV file found in '{download_dir}' after extracting '{slug}'. "
            "Verify the dataset contents on Kaggle."
        )

    if len(csv_files) > 1:
        log.warning(
            "kaggle.download.multiple_csv",
            files=[f.name for f in csv_files],
            selected=csv_files[0].name,
            message="Multiple CSV files found; using the first one.",
        )

    source_csv = csv_files[0]
    canonical_path = download_dir / CANONICAL_FILENAME

    if source_csv != canonical_path:
        shutil.move(str(source_csv), str(canonical_path))
        log.info(
            "kaggle.download.renamed",
            original=source_csv.name,
            canonical=CANONICAL_FILENAME,
        )

    log.info(
        "kaggle.download.complete",
        path=str(canonical_path),
        size_bytes=canonical_path.stat().st_size,
    )
    return canonical_path
