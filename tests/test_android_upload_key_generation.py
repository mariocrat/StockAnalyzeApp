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
        self.assertNotIn("store-password", output)
        self.assertNotIn("key-password", output)

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

    def test_double_click_batch_runs_android_upload_key_script(self):
        batch = BATCH.read_text(encoding="utf-8")

        self.assertIn("scripts\\generate_android_upload_key.py", batch)
        self.assertIn("--create-key", batch)
        self.assertIn(".venv\\Scripts\\python.exe", batch)
        self.assertIn("pause", batch.lower())


if __name__ == "__main__":
    unittest.main()
