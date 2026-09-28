import unittest
from typing import Annotated

from pydantic import AfterValidator

from gunz_utils import type_checked


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
        # The sensitive data is in the *wrong* argument type, which
        # triggers ValidationError.
        with self.assertRaises(TypeError) as cm:
            login("user", age=sensitive_password)  # type: ignore

        error_msg = str(cm.exception)

        # Ensure the sensitive data is NOT present in the error message
        self.assertNotIn(
            sensitive_password,
            error_msg,
            "Sensitive data leaked in validation error message!",
        )

        # Ensure we still get useful info (like the type)
        self.assertIn("got type 'str'", error_msg)

    def test_custom_validator_message_cannot_leak_secret(self):
        secret = "validator-secret-should-never-appear"

        def reject(value: str) -> str:
            raise ValueError(f"rejected secret: {value}")

        @type_checked
        def consume(value: Annotated[str, AfterValidator(reject)]) -> None:
            return None

        with self.assertRaises(TypeError) as cm:
            consume(secret)

        message = str(cm.exception)
        self.assertNotIn(secret, message)
        self.assertNotIn("rejected secret", message)
        self.assertIn("validation failed", message)


if __name__ == "__main__":
    unittest.main()
