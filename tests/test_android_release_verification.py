import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AndroidReleaseVerificationTest(unittest.TestCase):
    def test_double_click_batch_runs_android_release_verification_script(self):
        batch = (ROOT / "verify_android_release.bat").read_text(encoding="utf-8")

        self.assertIn("chcp 65001 >nul", batch)
        self.assertIn("scripts\\verify_android_release.ps1", batch)
        self.assertIn("ExecutionPolicy Bypass", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("Android release build verification passed.", batch)
        self.assertIn("if errorlevel 1", batch)
        self.assertNotIn("%EXIT_CODE%", batch)
        self.assertIn("ALPHAMATE_NO_PAUSE", batch)
        self.assertIn("if not \"%ALPHAMATE_NO_PAUSE%\"==\"1\" pause", batch)
        self.assertIn("pause", batch.lower())

    def test_double_click_batch_runs_android_debug_verification_script(self):
        batch = (ROOT / "verify_android_debug.bat").read_text(encoding="utf-8")

        self.assertIn("chcp 65001 >nul", batch)
        self.assertIn("scripts\\verify_android_debug.ps1", batch)
        self.assertIn("ExecutionPolicy Bypass", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("Android debug build verification passed.", batch)
        self.assertIn("if errorlevel 1", batch)
        self.assertNotIn("%EXIT_CODE%", batch)
        self.assertIn("ALPHAMATE_NO_PAUSE", batch)
        self.assertIn("if not \"%ALPHAMATE_NO_PAUSE%\"==\"1\" pause", batch)
        self.assertIn("pause", batch.lower())

    def test_oauth_debug_batch_runs_safe_oauth_apk_script(self):
        batch = (ROOT / "verify_android_oauth_debug.bat").read_text(encoding="utf-8")

        self.assertIn("scripts\\verify_android_oauth_debug.ps1", batch)
        self.assertIn("ExecutionPolicy Bypass", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("Android OAuth test APK build passed.", batch)
        self.assertIn("ALPHAMATE_NO_PAUSE", batch)
        self.assertIn("if errorlevel 1", batch)
        self.assertNotIn("%EXIT_CODE%", batch)

    def test_oauth_debug_script_loads_only_public_release_settings(self):
        script = (ROOT / "scripts" / "verify_android_oauth_debug.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $frontend ".env.release"', script)
        self.assertIn("Read-AllowedEnvFile", script)
        self.assertIn('"VITE_KAKAO_REST_API_KEY"', script)
        self.assertIn('"VITE_NAVER_CLIENT_ID"', script)
        public_allowlist = script.split("$allowedNames = @(", 1)[1].split(")\n$requiredNames", 1)[0]
        self.assertNotIn("NAVER_CLIENT_SECRET", public_allowlist)
        self.assertNotIn("KAKAO_CLIENT_SECRET", public_allowlist)
        self.assertNotIn("OPENAI_API_KEY", public_allowlist)
        self.assertIn("ca-app-pub-3940256099942544~3347511713", script)
        self.assertIn("server-only secret value", script)
        self.assertNotIn("server-only secret variable name", script)
        self.assertIn("Select-String -Path $distFiles.FullName", script)
        self.assertIn("assembleDebug", script)
        self.assertIn("app-debug.apk", script)

    def test_admob_qa_batch_runs_registered_device_qa_script(self):
        batch = (ROOT / "verify_android_admob_qa.bat").read_text(encoding="utf-8")

        self.assertIn("scripts\\verify_android_admob_qa.ps1", batch)
        self.assertIn("ExecutionPolicy Bypass", batch)
        self.assertTrue(batch.isascii())
        self.assertIn("Android AdMob QA APK build passed.", batch)
        self.assertIn("ALPHAMATE_NO_PAUSE", batch)
        self.assertIn("if errorlevel 1", batch)

    def test_admob_qa_script_uses_real_rewarded_unit_and_demo_secondary_placements(self):
        script = (ROOT / "scripts" / "verify_android_admob_qa.ps1").read_text(encoding="utf-8")

        self.assertIn('"VITE_ADMOB_ANDROID_APP_ID"', script)
        self.assertIn('"VITE_ADMOB_REWARDED_AD_UNIT_ID"', script)
        self.assertIn("real AlphaMate app and rewarded ad unit IDs", script)
        self.assertIn('$googleDemoPublisher = "3940256099942544"', script)
        self.assertIn('$placeholderPublisher = "0000000000000000"', script)
        self.assertIn('VITE_ALPHAMATE_ENV = "development"', script)
        self.assertIn('VITE_ENABLE_DEV_TOOLS = "false"', script)
        self.assertIn('VITE_QA_ADVANCED_COMPARISON = "true"', script)
        self.assertIn('"luna-terra-v1"', script)
        self.assertIn("ca-app-pub-3940256099942544/1033173712", script)
        self.assertIn("ca-app-pub-3940256099942544/6300978111", script)
        self.assertIn("clean assembleDebug --rerun-tasks", script)
        self.assertIn("alphamate-admob-qa.apk", script)
        self.assertIn("Get-FileHash -Algorithm SHA256", script)

    def test_advanced_comparison_is_off_in_the_release_template(self):
        release_env = (ROOT / "frontend" / ".env.release.example").read_text(encoding="utf-8")

        self.assertIn("VITE_QA_ADVANCED_COMPARISON=false", release_env)
        self.assertNotIn("VITE_QA_ADVANCED_COMPARISON=true", release_env)

    def test_debug_apk_scripts_use_google_demo_ads_instead_of_placeholder_publishers(self):
        expected_ids = (
            "ca-app-pub-3940256099942544~3347511713",
            "ca-app-pub-3940256099942544/5224354917",
            "ca-app-pub-3940256099942544/1033173712",
            "ca-app-pub-3940256099942544/6300978111",
        )
        for script_name in ("verify_android_debug.ps1", "verify_android_oauth_debug.ps1"):
            with self.subTest(script=script_name):
                script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8-sig")
                for ad_id in expected_ids:
                    self.assertIn(ad_id, script)
                self.assertIn('VITE_ALPHAMATE_ENV = "development"', script)
                self.assertIn('VITE_ENABLE_DEV_TOOLS = "false"', script)
                self.assertNotIn("ca-app-pub-0000000000000000", script)

    def test_release_verification_script_loads_frontend_release_env_and_builds_aab(self):
        script = (ROOT / "scripts" / "verify_android_release.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $frontend ".env.release"', script)
        self.assertIn("Load-EnvFile", script)
        self.assertIn("ALPHAMATE_FRONTEND_ENV_FILE", script)
        self.assertIn("npm.cmd run mobile:release:aab", script)
        self.assertIn("bundle\\release\\app-release.aab", script)
        self.assertIn("JAVA_HOME", script)
        self.assertIn("ANDROID_HOME", script)
        self.assertNotIn("ALPHAMATE_ANDROID_KEYSTORE_PASSWORD)", script)

    def test_release_verification_checks_release_env_before_local_tools(self):
        script = (ROOT / "scripts" / "verify_android_release.ps1").read_text(encoding="utf-8")

        release_env_check = script.find("Test-Path $frontendReleaseEnv")
        local_tool_check = script.find("Test-RequiredPath -Path $javaHome")
        self.assertGreaterEqual(release_env_check, 0)
        self.assertGreater(local_tool_check, release_env_check)
        self.assertIn("prepare_release_env_files.bat", script)


    def test_android_verification_powershell_scripts_keep_utf8_bom_for_windows_powershell(self):
        for script_name in ("verify_android_debug.ps1", "verify_android_release.ps1"):
            with self.subTest(script=script_name):
                script = (ROOT / "scripts" / script_name).read_bytes()
                self.assertTrue(script.startswith(b"\xef\xbb\xbf"))

    def test_android_verification_scripts_force_utf8_console_output(self):
        for script_name in ("verify_android_debug.ps1", "verify_android_release.ps1"):
            with self.subTest(script=script_name):
                script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8-sig")

                self.assertIn("[Console]::OutputEncoding", script)
                self.assertIn("$OutputEncoding", script)

    def test_android_verification_scripts_suppress_npm_update_notices(self):
        for script_name in ("verify_android_debug.ps1", "verify_android_release.ps1"):
            with self.subTest(script=script_name):
                script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8-sig")

                self.assertIn("$oldNpmUpdateNotifier = $env:npm_config_update_notifier", script)
                self.assertIn('$env:npm_config_update_notifier = "false"', script)
                self.assertIn("$env:npm_config_update_notifier = $oldNpmUpdateNotifier", script)

    def test_android_verification_scripts_explain_missing_local_tools(self):
        for script_name in ("verify_android_debug.ps1", "verify_android_release.ps1"):
            with self.subTest(script=script_name):
                script = (ROOT / "scripts" / script_name).read_text(encoding="utf-8")

                self.assertIn("Test-RequiredPath", script)
                self.assertIn("docs\\manual_test_guide.md", script)
                self.assertIn("로컬 JDK 폴더를 찾을 수 없습니다.", script)
                self.assertIn("로컬 Android SDK 폴더를 찾을 수 없습니다.", script)
                self.assertNotIn("Local JDK folder was not found", script)
                self.assertNotIn("Local Android SDK folder was not found", script)


if __name__ == "__main__":
    unittest.main()
