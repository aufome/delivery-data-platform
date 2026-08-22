"""
Unit tests for ingestion.kaggle_client.

The ``kaggle`` library is fully mocked — no network or Kaggle credentials needed.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from ingestion.kaggle_client import CANONICAL_FILENAME, download_dataset

# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_kaggle_api(download_dir: Path, csv_filename: str = "some_dataset.csv") -> mock.MagicMock:
    """
    Return a mock of ``kaggle.api`` that writes a CSV file to ``download_dir``
    when ``dataset_download_files`` is called.
    """

    def fake_download(slug: str, path: str, unzip: bool, quiet: bool) -> None:
        (Path(path) / csv_filename).write_text("id,value\n1,hello\n")

    api_mock = mock.MagicMock()
    api_mock.dataset_download_files.side_effect = fake_download
    return api_mock


# ── download_dataset ──────────────────────────────────────────────────────────


class TestDownloadDataset:
    def setup_method(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.download_dir = Path(self._tmp)

    def teardown_method(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_returns_canonical_path(self, settings_env: None) -> None:
        api_mock = _mock_kaggle_api(self.download_dir, csv_filename="weird_name.csv")

        with mock.patch.dict("sys.modules", {"kaggle": mock.MagicMock(api=api_mock)}):
            result = download_dataset(self.download_dir)

        assert result.name == CANONICAL_FILENAME
        assert result.exists()

    def test_canonical_file_readable(self, settings_env: None) -> None:
        api_mock = _mock_kaggle_api(self.download_dir)

        with mock.patch.dict("sys.modules", {"kaggle": mock.MagicMock(api=api_mock)}):
            result = download_dataset(self.download_dir)

        content = result.read_text()
        assert "id,value" in content

    def test_creates_download_dir_if_missing(self, settings_env: None) -> None:
        new_dir = self.download_dir / "nested" / "subdir"
        api_mock = _mock_kaggle_api(new_dir)

        with mock.patch.dict("sys.modules", {"kaggle": mock.MagicMock(api=api_mock)}):
            result = download_dataset(new_dir)

        assert result.exists()

    def test_custom_slug_used(self, settings_env: None) -> None:
        api_mock = _mock_kaggle_api(self.download_dir)

        with mock.patch.dict("sys.modules", {"kaggle": mock.MagicMock(api=api_mock)}):
            download_dataset(self.download_dir, dataset_slug="owner/custom-dataset")

        api_mock.dataset_download_files.assert_called_once()
        call_args = api_mock.dataset_download_files.call_args
        assert call_args[0][0] == "owner/custom-dataset"

    def test_raises_file_not_found_when_no_csv(self, settings_env: None) -> None:
        def fake_download_no_csv(slug: str, path: str, unzip: bool, quiet: bool) -> None:
            pass  # Writes nothing

        api_mock = mock.MagicMock()
        api_mock.dataset_download_files.side_effect = fake_download_no_csv

        with mock.patch.dict("sys.modules", {"kaggle": mock.MagicMock(api=api_mock)}):
            with pytest.raises(FileNotFoundError, match="No CSV file found"):
                download_dataset(self.download_dir)

    def test_raises_runtime_error_on_kaggle_failure(self, settings_env: None) -> None:
        api_mock = mock.MagicMock()
        api_mock.dataset_download_files.side_effect = Exception("API quota exceeded")

        with mock.patch.dict("sys.modules", {"kaggle": mock.MagicMock(api=api_mock)}):
            with pytest.raises(RuntimeError, match="Kaggle download failed"):
                download_dataset(self.download_dir)

    def test_credentials_injected_into_environment(self, settings_env: None) -> None:
        api_mock = _mock_kaggle_api(self.download_dir)

        with mock.patch.dict("sys.modules", {"kaggle": mock.MagicMock(api=api_mock)}):
            download_dataset(self.download_dir)

        assert os.environ.get("KAGGLE_USERNAME") == "test_user"
        assert os.environ.get("KAGGLE_KEY") == "test_key_abc123"
