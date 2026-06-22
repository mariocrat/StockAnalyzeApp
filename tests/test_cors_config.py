import os
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


class CorsConfigTest(unittest.TestCase):
    def test_default_cors_origins_include_local_web_and_capacitor(self):
        with patched_env(ALPHAMATE_CORS_ORIGINS=None):
            from backend.core.cors import allowed_cors_origins

            origins = allowed_cors_origins()

            self.assertIn("http://127.0.0.1:5174", origins)
            self.assertIn("http://localhost:5174", origins)
            self.assertIn("capacitor://localhost", origins)
            self.assertIn("ionic://localhost", origins)

    def test_cors_origins_can_be_overridden_by_environment(self):
        with patched_env(
            ALPHAMATE_CORS_ORIGINS="https://app.example.com, capacitor://localhost, https://app.example.com",
        ):
            from backend.core.cors import allowed_cors_origins

            origins = allowed_cors_origins()

            self.assertEqual([
                "https://app.example.com",
                "capacitor://localhost",
            ], origins)


if __name__ == "__main__":
    unittest.main()
