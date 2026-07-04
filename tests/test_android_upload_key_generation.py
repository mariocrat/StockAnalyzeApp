import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_android_upload_key.py"
BATCH = ROOT / "generate_android_upload_key.bat"


def load_module():
    spec = importlib.util.spec_from_file_location("generate_android_upload_key", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AndroidUploadKeyGenerationTest(unittest.TestCase):
    def test_fills_empty_frontend_release_signing_values_without_overwriting_existing_values(self):
        module = load_module()
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
        module = load_module()
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

    def test_builds_keytool_upload_key_command_without_printing_passwords(self):
        module = load_module()
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
        module = load_module()
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
        module = load_module()
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

    def test_double_click_batch_runs_android_upload_key_script_as_ascii_safe_wrapper(self):
        batch = BATCH.read_text(encoding="utf-8")

        self.assertIn("chcp 65001 >nul", batch)
        self.assertIn("scripts\\generate_android_upload_key.py", batch)
        self.assertIn("--create-key", batch)
        self.assertIn(".venv\\Scripts\\python.exe", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("Preparing private Android upload signing key", batch)
        self.assertIn("Python virtual environment was not found", batch)
        self.assertIn("pause", batch.lower())

    def test_android_upload_key_result_uses_korean_owner_messages(self):
        module = load_module()
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
