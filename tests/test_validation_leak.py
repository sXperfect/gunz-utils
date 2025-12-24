import unittest
from gunz_utils.validation import type_checked

class TestValidationLeak(unittest.TestCase):
    def test_sensitive_data_leakage(self):
        """
        Test that sensitive data passed to a validated function is not leaked
        in the error message when validation fails.
        """
        @type_checked
        def login(username: str, age: int):
            pass

        sensitive_password = "MySecretPassword123!"

        # We pass a string where an int is expected for 'age'
        # The sensitive data is in the *wrong* argument type, which triggers ValidationError.
        with self.assertRaises(TypeError) as cm:
            login("user", age=sensitive_password) # type: ignore

        error_msg = str(cm.exception)

        # Ensure the sensitive data is NOT present in the error message
        self.assertNotIn(sensitive_password, error_msg, "Sensitive data leaked in validation error message!")

        # Ensure we still get useful info (like the type)
        self.assertIn("got type 'str'", error_msg)

if __name__ == "__main__":
    unittest.main()
