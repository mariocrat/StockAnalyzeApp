import os
import tempfile
import unittest
from contextlib import contextmanager


@contextmanager
def patched_env(**values):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def write_env_file(text: str) -> str:
    env_file = tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", delete=False)
    try:
        env_file.write(text)
        return env_file.name
    finally:
        env_file.close()


class ReleaseAlignmentTest(unittest.TestCase):
    def test_rejects_when_no_release_settings_can_be_compared(self):
        backend_env = write_env_file("")
        frontend_env = write_env_file("")
        try:
            with patched_env(
                ALPHAMATE_ENV_FILE=backend_env,
                ALPHAMATE_FRONTEND_ENV_FILE=frontend_env,
                GOOGLE_PLAY_PACKAGE_NAME=None,
                KAKAO_REDIRECT_URI=None,
                NAVER_REDIRECT_URI=None,
                ADMOB_REWARDED_AD_UNIT_ID=None,
                VITE_GOOGLE_PLAY_PACKAGE_NAME=None,
                VITE_KAKAO_REDIRECT_URI=None,
                VITE_NAVER_REDIRECT_URI=None,
                VITE_ADMOB_REWARDED_AD_UNIT_ID=None,
            ):
                from backend.scripts.validate_release_alignment import (
                    format_release_alignment_report,
                    validate_release_alignment,
                )

                result = validate_release_alignment()
                report = format_release_alignment_report(result)

            self.assertFalse(result["ok"])
            self.assertIn("No comparable server/app release settings were found", result["errors"])
            self.assertIn("서버와 앱 출시 설정 파일을 먼저 채우기", report)
            self.assertIn("전체 상태: 준비 필요", report)
        finally:
            os.unlink(backend_env)
            os.unlink(frontend_env)

    def test_accepts_matching_backend_and_frontend_release_settings(self):
        backend_env = write_env_file("\n".join([
            "GOOGLE_PLAY_PACKAGE_NAME=com.mariocrat.stockanalyze",
            "KAKAO_REDIRECT_URI=https://api.alphamate.kr/api/auth/kakao/callback",
            "NAVER_REDIRECT_URI=https://api.alphamate.kr/api/auth/naver/callback",
            "ADMOB_REWARDED_AD_UNIT_ID=ca-app-pub-1234567890123456/9876543210",
        ]))
        frontend_env = write_env_file("\n".join([
            "VITE_GOOGLE_PLAY_PACKAGE_NAME=com.mariocrat.stockanalyze",
            "VITE_KAKAO_REDIRECT_URI=https://api.alphamate.kr/api/auth/kakao/callback",
            "VITE_NAVER_REDIRECT_URI=https://api.alphamate.kr/api/auth/naver/callback",
            "VITE_ADMOB_REWARDED_AD_UNIT_ID=ca-app-pub-1234567890123456/9876543210",
        ]))
        try:
            with patched_env(
                ALPHAMATE_ENV_FILE=backend_env,
                ALPHAMATE_FRONTEND_ENV_FILE=frontend_env,
                GOOGLE_PLAY_PACKAGE_NAME=None,
                KAKAO_REDIRECT_URI=None,
                NAVER_REDIRECT_URI=None,
                ADMOB_REWARDED_AD_UNIT_ID=None,
                VITE_GOOGLE_PLAY_PACKAGE_NAME=None,
                VITE_KAKAO_REDIRECT_URI=None,
                VITE_NAVER_REDIRECT_URI=None,
                VITE_ADMOB_REWARDED_AD_UNIT_ID=None,
            ):
                from backend.scripts.validate_release_alignment import (
                    format_release_alignment_report,
                    validate_release_alignment,
                )

                result = validate_release_alignment()
                report = format_release_alignment_report(result)

            self.assertTrue(result["ok"])
            self.assertEqual([], result["errors"])
            self.assertIn("전체 상태: 준비됨", report)
            self.assertIn("서버와 앱의 출시 설정이 서로 맞습니다", report)
        finally:
            os.unlink(backend_env)
            os.unlink(frontend_env)

    def test_rejects_mismatched_backend_and_frontend_release_settings(self):
        backend_env = write_env_file("\n".join([
            "GOOGLE_PLAY_PACKAGE_NAME=com.mariocrat.stockanalyze",
            "KAKAO_REDIRECT_URI=https://api.alphamate.kr/api/auth/kakao/callback",
            "NAVER_REDIRECT_URI=https://api.alphamate.kr/api/auth/naver/callback",
            "ADMOB_REWARDED_AD_UNIT_ID=ca-app-pub-1234567890123456/9876543210",
        ]))
        frontend_env = write_env_file("\n".join([
            "VITE_GOOGLE_PLAY_PACKAGE_NAME=com.other.app",
            "VITE_KAKAO_REDIRECT_URI=https://app.alphamate.kr/oauth/kakao",
            "VITE_NAVER_REDIRECT_URI=https://app.alphamate.kr/oauth/naver",
            "VITE_ADMOB_REWARDED_AD_UNIT_ID=ca-app-pub-1234567890123456/0000000000",
        ]))
        try:
            with patched_env(
                ALPHAMATE_ENV_FILE=backend_env,
                ALPHAMATE_FRONTEND_ENV_FILE=frontend_env,
                GOOGLE_PLAY_PACKAGE_NAME=None,
                KAKAO_REDIRECT_URI=None,
                NAVER_REDIRECT_URI=None,
                ADMOB_REWARDED_AD_UNIT_ID=None,
                VITE_GOOGLE_PLAY_PACKAGE_NAME=None,
                VITE_KAKAO_REDIRECT_URI=None,
                VITE_NAVER_REDIRECT_URI=None,
                VITE_ADMOB_REWARDED_AD_UNIT_ID=None,
            ):
                from backend.scripts.validate_release_alignment import (
                    format_release_alignment_report,
                    validate_release_alignment,
                )

                result = validate_release_alignment()
                report = format_release_alignment_report(result)

            self.assertFalse(result["ok"])
            self.assertIn(
                "GOOGLE_PLAY_PACKAGE_NAME must match VITE_GOOGLE_PLAY_PACKAGE_NAME",
                result["errors"],
            )
            self.assertIn(
                "KAKAO_REDIRECT_URI must match VITE_KAKAO_REDIRECT_URI",
                result["errors"],
            )
            self.assertIn(
                "NAVER_REDIRECT_URI must match VITE_NAVER_REDIRECT_URI",
                result["errors"],
            )
            self.assertIn(
                "ADMOB_REWARDED_AD_UNIT_ID must match VITE_ADMOB_REWARDED_AD_UNIT_ID",
                result["errors"],
            )
            self.assertIn("서버 설정과 앱 설정을 같은 값으로 맞추기", report)
            self.assertIn("확인할 항목", report)
            self.assertNotIn("com.other.app", report)
            self.assertNotIn("https://app.alphamate.kr/oauth/kakao", report)
        finally:
            os.unlink(backend_env)
            os.unlink(frontend_env)


if __name__ == "__main__":
    unittest.main()
