"""Pruebas unitarias de política de excepciones F4 (Directiva OCC-003A).

Verifica tanto los casos positivos (reconocimiento estricto de las 4 excepciones
autorizadas y preservación del baseline histórico) como los casos negativos
(rechazo de drift de 1 byte, modificaciones en otras rutas congeladas,
archivos nuevos bajo rutas congeladas y fallos de integridad local).
"""

from __future__ import annotations

import hashlib
import unittest
from unittest.mock import MagicMock, patch

from scripts import freeze_check
from scripts.freeze_check import F4_AUTHORIZED_EXCEPTIONS, FILE_PINS, Report


class TestF4AllowlistPositive(unittest.TestCase):
    """Casos positivos: integridad estructural y coincidencia exacta de hashes."""

    def test_baseline_remains_immutable(self) -> None:
        """El baseline histórico NO debe ser modificado (debe ser exactamente cd6b58e)."""
        self.assertEqual(
            freeze_check.BASELINE, "cd6b58eb9bd4b9a22b8937c4cda73be46322cddb"
        )

    def test_file_pins_remain_intact(self) -> None:
        """Los FILE_PINS existentes deben permanecer idénticos a su definición original."""
        expected_pins = {
            "db/migration/V001__enable_postgis.sql": (
                "5f3606cb3b51ffbcbb509213493b36f6ff2e5c298b2dedd1b39ed16aa99db0df"
            ),
            "db/migration/V002__create_sapi_v2_schema.sql": (
                "22df9f6843a21e4d00609b882e6afa9f337d6a6dbdda82626f19549241584206"
            ),
            "db/migration/V003__seed_celdas_geom.sql": (
                "02690a1684aa19bb40c7bb856a892096211ed352221d715e99d3f93cbf5bf009"
            ),
            "models/prototype_model_d.pkl": (
                "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f"
            ),
            "models/prototype_model_d_metadata.json": (
                "fc2c62341d821ddf2c4483050c917a2b2f0ab96607d134bb9ba05b7f82a07bd9"
            ),
            "artifacts/hito1/reproducibility/manifest.json": (
                "a02500da7fb2e055766c76b154fbcf8e11b957a3f413d3e3c8c59d0ef2afa439"
            ),
        }
        self.assertEqual(FILE_PINS, expected_pins)

    def test_allowlist_contains_exactly_four_authorized_paths(self) -> None:
        """La lista blanca debe contener únicamente las cuatro rutas autorizadas."""
        expected_paths = {
            "src/inference/scoring_inputs.py",
            "src/procesamiento/firms_source.py",
            "src/refresh/dmc_refresh.py",
            "src/refresh/firms_refresh.py",
        }
        self.assertEqual(set(F4_AUTHORIZED_EXCEPTIONS.keys()), expected_paths)

    def test_allowlist_metadata_fields_are_complete(self) -> None:
        """Cada entrada debe contener todos los campos de trazabilidad y gobernanza."""
        required_fields = {
            "authorized_commit",
            "blob_sha",
            "content_sha256",
            "defect_id",
            "author",
            "reason",
            "evidence",
            "scope",
        }
        for path, meta in F4_AUTHORIZED_EXCEPTIONS.items():
            self.assertTrue(
                required_fields.issubset(meta.keys()),
                f"Metadatos incompletos para {path}: faltan {required_fields - set(meta.keys())}",
            )
            self.assertEqual(
                meta["authorized_commit"],
                "7dcd0b666e05bb5efd64c1c98685902e8b4908bf",
                f"Commit no coincide en {path}",
            )
            self.assertEqual(meta["author"], "DanielCortezF002")

    def test_current_repo_blobs_match_allowlist_hashes_exactly(self) -> None:
        """Los 4 archivos en el commit HEAD deben coincidir exactamente con los
        hashes de la lista.
        """
        for path, meta in F4_AUTHORIZED_EXCEPTIONS.items():
            blob_head = freeze_check.git("rev-parse", f"HEAD:{path}")
            bytes_head = freeze_check.git_bytes("HEAD", path)
            sha256_head = hashlib.sha256(bytes_head).hexdigest()

            self.assertEqual(
                blob_head,
                meta["blob_sha"],
                f"Git blob SHA diverge en {path}: {blob_head} != {meta['blob_sha']}",
            )
            self.assertEqual(
                sha256_head,
                meta["content_sha256"],
                f"Content SHA-256 diverge en {path}: {sha256_head} != {meta['content_sha256']}",
            )


class TestF4AllowlistNegative(unittest.TestCase):
    """Casos negativos: detección y rechazo de alteraciones, archivos no autorizados y drift."""

    def setUp(self) -> None:
        self.report = Report()

    @patch("scripts.freeze_check.git_bytes")
    @patch("scripts.freeze_check.git")
    def test_single_byte_drift_in_authorized_file_triggers_fail(
        self, mock_git: MagicMock, mock_git_bytes: MagicMock
    ) -> None:
        """Si un archivo autorizado diverge por un byte en contenido, debe producirse FAIL."""
        target = "src/inference/scoring_inputs.py"

        def fake_git(*args: str) -> str:
            if args[0] == "diff" and args[1] == "--name-only":
                return target
            if args[0] == "rev-parse" and f"HEAD:{target}" in args[1]:
                # Blob distinto
                return "0000000000000000000000000000000000000000"
            return ""

        mock_git.side_effect = fake_git
        mock_git_bytes.return_value = b"# drifted byte"

        freeze_check.check_frozen_paths(self.report)
        status = {row["check"]: row["status"] for row in self.report.rows}
        self.assertEqual(status["F4 congelados (commits)"], "FAIL")

    @patch("scripts.freeze_check.git")
    def test_modification_in_unauthorized_frozen_path_triggers_fail(
        self, mock_git: MagicMock
    ) -> None:
        """Si se modifica otra ruta congelada (p. ej. src/geo/grid.py), debe producirse FAIL."""
        unauthorized_file = "src/geo/grid.py"

        def fake_git(*args: str) -> str:
            if args[0] == "diff" and args[1] == "--name-only":
                return f"src/inference/scoring_inputs.py\n{unauthorized_file}"
            if args[0] == "rev-parse":
                return F4_AUTHORIZED_EXCEPTIONS["src/inference/scoring_inputs.py"][
                    "blob_sha"
                ]
            return ""

        mock_git.side_effect = fake_git

        with patch("scripts.freeze_check.git_bytes") as mock_bytes:
            expected_hash = F4_AUTHORIZED_EXCEPTIONS["src/inference/scoring_inputs.py"][
                "content_sha256"
            ]
            # Mock de bytes correctos para el archivo autorizado
            mock_bytes.return_value = b"correct content"
            with patch("hashlib.sha256") as mock_sha:
                mock_sha.return_value.hexdigest.return_value = expected_hash
                freeze_check.check_frozen_paths(self.report)

        status = {row["check"]: row["status"] for row in self.report.rows}
        self.assertEqual(status["F4 congelados (commits)"], "FAIL")

    @patch("scripts.freeze_check.git")
    def test_uncommitted_local_modification_triggers_worktree_fail(
        self, mock_git: MagicMock
    ) -> None:
        """Una modificación local no commiteada en rutas congeladas debe producir FAIL."""

        def fake_git(*args: str) -> str:
            # diff BASELINE HEAD limpio (solo autorizados)
            if args[0] == "diff" and args[2] == freeze_check.BASELINE:
                return "src/inference/scoring_inputs.py"
            # diff HEAD worktree sucio
            if args[0] == "diff" and args[2] == "HEAD":
                return "src/inference/scoring_inputs.py"
            if args[0] == "rev-parse":
                return F4_AUTHORIZED_EXCEPTIONS["src/inference/scoring_inputs.py"][
                    "blob_sha"
                ]
            return ""

        mock_git.side_effect = fake_git

        with patch("scripts.freeze_check.git_bytes"):
            with patch("hashlib.sha256") as mock_sha:
                mock_sha.return_value.hexdigest.return_value = F4_AUTHORIZED_EXCEPTIONS[
                    "src/inference/scoring_inputs.py"
                ]["content_sha256"]
                freeze_check.check_frozen_paths(self.report)

        status = {row["check"]: row["status"] for row in self.report.rows}
        self.assertEqual(status["F4 congelados (worktree)"], "FAIL")

    @patch("scripts.freeze_check.git")
    def test_untracked_file_under_frozen_paths_triggers_new_files_fail(
        self, mock_git: MagicMock
    ) -> None:
        """Un archivo nuevo no trackeado bajo rutas congeladas debe producir FAIL."""

        def fake_git(*args: str) -> str:
            if args[0] == "diff" and args[2] == freeze_check.BASELINE:
                return "src/inference/scoring_inputs.py"
            if args[0] == "ls-files" and "--others" in args:
                return "src/inference/unauthorized_new_file.py"
            if args[0] == "rev-parse":
                return F4_AUTHORIZED_EXCEPTIONS["src/inference/scoring_inputs.py"][
                    "blob_sha"
                ]
            return ""

        mock_git.side_effect = fake_git

        with patch("scripts.freeze_check.git_bytes"):
            with patch("hashlib.sha256") as mock_sha:
                mock_sha.return_value.hexdigest.return_value = F4_AUTHORIZED_EXCEPTIONS[
                    "src/inference/scoring_inputs.py"
                ]["content_sha256"]
                freeze_check.check_frozen_paths(self.report)

        status = {row["check"]: row["status"] for row in self.report.rows}
        self.assertEqual(status["F4 congelados (archivos nuevos)"], "FAIL")

    @patch("scripts.freeze_check.git")
    def test_incorrect_content_sha256_triggers_fail(self, mock_git: MagicMock) -> None:
        """Si el blob SHA coincide pero el contenido sha256 difiere, debe producirse FAIL."""
        target = "src/inference/scoring_inputs.py"

        def fake_git(*args: str) -> str:
            if args[0] == "diff" and args[1] == "--name-only":
                return target
            if args[0] == "rev-parse":
                return F4_AUTHORIZED_EXCEPTIONS[target]["blob_sha"]
            return ""

        mock_git.side_effect = fake_git

        with patch("scripts.freeze_check.git_bytes") as mock_bytes:
            mock_bytes.return_value = b"corrupted bytes"
            with patch("hashlib.sha256") as mock_sha:
                mock_sha.return_value.hexdigest.return_value = "bad_hash_value"
                freeze_check.check_frozen_paths(self.report)

        status = {row["check"]: row["status"] for row in self.report.rows}
        self.assertEqual(status["F4 congelados (commits)"], "FAIL")


if __name__ == "__main__":
    unittest.main()
