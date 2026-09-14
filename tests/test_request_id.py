from tests.storage_fixture import require_storage_boundary, storage_fixture

require_storage_boundary()

from tests.api_test_modules import api_module_state

import unittest


class RequestIdTest(unittest.TestCase):
    def setUp(self):
        self.enterContext(storage_fixture())
        self.enterContext(api_module_state())

    def test_accepts_safe_incoming_request_id(self):
        import main

        request_id = main._request_id_from_header("order-123_ABC.def")

        self.assertEqual("order-123_ABC.def", request_id)

    def test_replaces_missing_or_unsafe_request_id(self):
        import main

        missing = main._request_id_from_header("")
        unsafe = main._request_id_from_header("bad value with spaces and !")
        too_long = main._request_id_from_header("x" * 200)

        self.assertEqual(32, len(missing))
        self.assertEqual(32, len(unsafe))
        self.assertEqual(32, len(too_long))
        self.assertNotEqual(missing, unsafe)


if __name__ == "__main__":
    unittest.main()
