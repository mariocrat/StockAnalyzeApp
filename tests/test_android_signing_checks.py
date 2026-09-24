"""H4-C synthetic signing configuration checks; no real signing tools."""

from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_android_upload_key.py"


def load_module():
    require_storage_boundary()
    if not sys.dont_write_bytecode:
        raise RuntimeError("signing imports require bytecode disabled")
    spec = importlib.util.spec_from_file_location("generate_android_upload_key", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AndroidSigningChecksTest(unittest.TestCase):
    def setUp(self):
        baseline = (dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path), sys.dont_write_bytecode)
        modules = dict(sys.modules)
        self.addCleanup(self._assert_restored, baseline, modules)
        fixture = self.enterContext(storage_fixture())
        self._case_container = fixture.root.parent
        self.enterContext(patch.object(sys, "path", list(sys.path)))
        self.enterContext(patch.dict(sys.modules))
        self.enterContext(patch.object(sys, "dont_write_bytecode", True))
        original_exists = Path.exists

        def owned_exists(path, *args, **kwargs):
            # A1 guards file opens/writes, but Python stat/exists has no audit
            # event. Keep the real result while rejecting outside-case probes.
            if not path.resolve().is_relative_to(fixture.root):
                raise AssertionError("signing exists outside testcase workspace")
            return original_exists(path, *args, **kwargs)

        self.enterContext(patch.object(Path, "exists", owned_exists))
        self.module = load_module()
        self.addCleanup(delattr, self, "module")
        for name in ("main", "create_upload_key", "find_keytool", "_repo_root"):
            blocked = self.enterContext(patch.object(
                self.module, name, side_effect=AssertionError("signing tool entrypoint forbidden")))
            self.addCleanup(blocked.assert_not_called)

    def _assert_restored(self, baseline, modules):
        self.assertEqual((dict(os.environ), Path.cwd(), tempfile.tempdir, list(sys.path), sys.dont_write_bytecode), baseline)
        self.assertEqual(set(sys.modules), set(modules))
        self.assertTrue(all(sys.modules[name] is module for name, module in modules.items()))
        container = self.__dict__.pop("_case_container", None)
        if container is not None:
            self.assertFalse(container.exists())
        self.assertFalse(hasattr(self, "module"))

    def test_default_pkcs12_passwords_match(self):
        module = self.module
        with tempfile.TemporaryDirectory() as temp_dir:
            values = module.default_android_signing_values(Path(temp_dir))

        self.assertEqual(
            values["ALPHAMATE_ANDROID_KEYSTORE_PASSWORD"],
            values["ALPHAMATE_ANDROID_KEY_PASSWORD"],
        )

    def test_fills_empty_frontend_release_signing_values_without_overwriting_existing_values(self):
        module = self.module
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frontend = root / "frontend"
            frontend.mkdir()
            (frontend / ".env.release").write_text(
                "\n".join([
                    "VITE_ALPHAMATE_ENV=production",
                    "ALPHAMATE_ANDROID_KEYSTORE_FILE=",
                    "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD=keep-existing-store-password",
                    "ALPHAMATE_ANDROID_KEY_ALIAS=",
                    "ALPHAMATE_ANDROID_KEY_PASSWORD=",
                    "",
                ]),
                encoding="utf-8",
            )

            result = module.fill_empty_android_signing_values(
                root,
                {
                    "ALPHAMATE_ANDROID_KEYSTORE_FILE": "D:/private/alphamate-upload.jks",
                    "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD": "new-store-password",
                    "ALPHAMATE_ANDROID_KEY_ALIAS": "alphamate-upload",
                    "ALPHAMATE_ANDROID_KEY_PASSWORD": "new-key-password",
                },
            )

            env_text = (frontend / ".env.release").read_text(encoding="utf-8")
            self.assertEqual([
                "ALPHAMATE_ANDROID_KEYSTORE_FILE",
                "ALPHAMATE_ANDROID_KEY_ALIAS",
                "ALPHAMATE_ANDROID_KEY_PASSWORD",
            ], result["filled"])
            self.assertEqual(["ALPHAMATE_ANDROID_KEYSTORE_PASSWORD"], result["skipped_existing"])
            self.assertIn("ALPHAMATE_ANDROID_KEYSTORE_FILE=D:/private/alphamate-upload.jks", env_text)
            self.assertIn("ALPHAMATE_ANDROID_KEYSTORE_PASSWORD=keep-existing-store-password", env_text)
            self.assertIn("ALPHAMATE_ANDROID_KEY_ALIAS=alphamate-upload", env_text)
            self.assertIn("ALPHAMATE_ANDROID_KEY_PASSWORD=new-key-password", env_text)
            self.assertNotIn("new-store-password", env_text)

    def test_replaces_template_secure_keystore_path_with_private_project_path(self):
        module = self.module
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frontend = root / "frontend"
            frontend.mkdir()
            (frontend / ".env.release").write_text(
                "\n".join([
                    "ALPHAMATE_ANDROID_KEYSTORE_FILE=D:/secure/alphamate/alphamate-upload.jks",
                    "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD=",
                    "ALPHAMATE_ANDROID_KEY_ALIAS=alphamate-upload",
                    "ALPHAMATE_ANDROID_KEY_PASSWORD=",
                    "",
                ]),
                encoding="utf-8",
            )

            defaults = module.default_android_signing_values(root)
            result = module.fill_empty_android_signing_values(root, defaults)
            values = module.load_android_signing_values(root)

            self.assertIn("ALPHAMATE_ANDROID_KEYSTORE_FILE", result["filled"])
            self.assertEqual(defaults["ALPHAMATE_ANDROID_KEYSTORE_FILE"], values["ALPHAMATE_ANDROID_KEYSTORE_FILE"])
            self.assertIn("/release-private/android/alphamate-upload.jks", values["ALPHAMATE_ANDROID_KEYSTORE_FILE"])

    def test_replaces_stale_project_private_keystore_path_after_workspace_move(self):
        module = self.module
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            root = workspace / "current"
            root.mkdir()
            old_key = workspace / "old" / "release-private" / "android" / "alphamate-upload.jks"
            self.assertFalse(old_key.exists())
            frontend = root / "frontend"
            frontend.mkdir()
            (frontend / ".env.release").write_text(
                "\n".join([
                    f"ALPHAMATE_ANDROID_KEYSTORE_FILE={old_key.as_posix()}",
                    "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD=keep-store-password",
                    "ALPHAMATE_ANDROID_KEY_ALIAS=alphamate-upload",
                    "ALPHAMATE_ANDROID_KEY_PASSWORD=keep-key-password",
                    "",
                ]),
                encoding="utf-8",
            )

            defaults = module.default_android_signing_values(root)
            result = module.fill_empty_android_signing_values(root, defaults)
            values = module.load_android_signing_values(root)

            self.assertIn("ALPHAMATE_ANDROID_KEYSTORE_FILE", result["filled"])
            self.assertEqual(defaults["ALPHAMATE_ANDROID_KEYSTORE_FILE"], values["ALPHAMATE_ANDROID_KEYSTORE_FILE"])
            self.assertEqual("keep-store-password", values["ALPHAMATE_ANDROID_KEYSTORE_PASSWORD"])
            self.assertEqual("keep-key-password", values["ALPHAMATE_ANDROID_KEY_PASSWORD"])

    def test_builds_keytool_upload_key_command_without_printing_passwords(self):
        module = self.module
        command = module.build_keytool_command(
            keytool_path=Path("D:/jdk/bin/keytool.exe"),
            values={
                "ALPHAMATE_ANDROID_KEYSTORE_FILE": "D:/private/alphamate-upload.jks",
                "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD": "store-password",
                "ALPHAMATE_ANDROID_KEY_ALIAS": "alphamate-upload",
                "ALPHAMATE_ANDROID_KEY_PASSWORD": "key-password",
            },
        )

        self.assertIn("keytool.exe", str(command[0]))
        self.assertIn("-genkeypair", command)
        self.assertIn("-keystore", command)
        self.assertIn("D:/private/alphamate-upload.jks", command)
        self.assertIn("-alias", command)
        self.assertIn("alphamate-upload", command)
        self.assertIn("-keyalg", command)
        self.assertIn("RSA", command)
        self.assertIn("-validity", command)
        self.assertIn("10000", command)

    def test_status_output_does_not_include_generated_passwords(self):
        module = self.module
        output = module.format_result(
            {
                "filled": [
                    "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD",
                    "ALPHAMATE_ANDROID_KEY_PASSWORD",
                ],
                "skipped_existing": [],
                "missing_file": "",
            },
            {"created": True, "skipped_existing": False, "error": ""},
        )

        self.assertIn("ALPHAMATE_ANDROID_KEYSTORE_PASSWORD", output)
        self.assertIn("ALPHAMATE_ANDROID_KEY_PASSWORD", output)
        self.assertIn("Android 서명 설정", output)
        self.assertIn("Android 업로드 키스토어 파일을 만들었습니다.", output)
        self.assertIn("GitHub에 올리지 마세요.", output)
        self.assertNotIn("store-password", output)
        self.assertNotIn("key-password", output)
        self.assertNotIn("Updated private Android", output)
        self.assertNotIn("Do not commit", output)

    def test_reads_existing_frontend_release_signing_values_after_fill(self):
        module = self.module
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            frontend = root / "frontend"
            frontend.mkdir()
            (frontend / ".env.release").write_text(
                "\n".join([
                    "ALPHAMATE_ANDROID_KEYSTORE_FILE=D:/secure/custom-upload.jks",
                    "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD=",
                    "ALPHAMATE_ANDROID_KEY_ALIAS=custom-upload",
                    "ALPHAMATE_ANDROID_KEY_PASSWORD=",
                    "",
                ]),
                encoding="utf-8",
            )

            module.fill_empty_android_signing_values(
                root,
                {
                    "ALPHAMATE_ANDROID_KEYSTORE_FILE": "D:/private/default-upload.jks",
                    "ALPHAMATE_ANDROID_KEYSTORE_PASSWORD": "new-store-password",
                    "ALPHAMATE_ANDROID_KEY_ALIAS": "alphamate-upload",
                    "ALPHAMATE_ANDROID_KEY_PASSWORD": "new-key-password",
                },
            )
            values = module.load_android_signing_values(root)

            self.assertEqual("D:/secure/custom-upload.jks", values["ALPHAMATE_ANDROID_KEYSTORE_FILE"])
            self.assertEqual("new-store-password", values["ALPHAMATE_ANDROID_KEYSTORE_PASSWORD"])
            self.assertEqual("custom-upload", values["ALPHAMATE_ANDROID_KEY_ALIAS"])
            self.assertEqual("new-key-password", values["ALPHAMATE_ANDROID_KEY_PASSWORD"])

    def test_android_upload_key_result_uses_korean_owner_messages(self):
        module = self.module
        output = module.format_result(
            {
                "filled": ["ALPHAMATE_ANDROID_KEY_ALIAS"],
                "skipped_existing": ["ALPHAMATE_ANDROID_KEYSTORE_FILE"],
                "missing_file": "D:/app/frontend/.env.release",
            },
            {"created": False, "skipped_existing": False, "error": "keytool 실행에 실패해 Android 업로드 키를 만들지 못했습니다."},
        )

        self.assertIn("Android 서명 설정", output)
        self.assertIn("채움: ALPHAMATE_ANDROID_KEY_ALIAS", output)
        self.assertIn("이미 값이 있어서 유지함: ALPHAMATE_ANDROID_KEYSTORE_FILE", output)
        self.assertIn("prepare_release_env_files.bat를 먼저 실행", output)
        self.assertIn("keytool 실행에 실패", output)
        self.assertNotIn("Skipped existing value", output)
        self.assertNotIn("Run prepare_release_env_files.bat first", output)


if __name__ == "__main__":
    unittest.main()
