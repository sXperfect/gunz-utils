import unittest
import sys
from gunz_utils.validation import type_checked

class TestTypeChecked(unittest.TestCase):
    def test_basic_validation(self):
        @type_checked
        def add(a: int, b: int) -> int:
            return a + b

        self.assertEqual(add(1, 2), 3)

        with self.assertRaises(TypeError) as cm:
            add(1, b="two")

        self.assertIn("Validation error in 'add'", str(cm.exception))
        self.assertIn("Argument 'b'", str(cm.exception))

    def test_optional_args(self):
        @type_checked
        def greet(name: str, age: int = 18):
            return f"Hello {name}, {age}"

        self.assertEqual(greet("Alice"), "Hello Alice, 18")
        self.assertEqual(greet("Bob", age=20), "Hello Bob, 20")

        with self.assertRaises(TypeError) as cm:
            greet("Charlie", age="unknown")

        self.assertIn("Argument 'age'", str(cm.exception))

    def test_multiple_validation_failures(self):
        @type_checked
        def multi(a: int, b: str, c: float) -> str:
            return f"{a}-{b}-{c}"

        with self.assertRaises(TypeError) as cm:
            multi("x", 123, "not a float")

        msg = str(cm.exception)
        self.assertIn("Validation error in 'multi'", msg)
        self.assertIn("got type 'str'", msg)
        self.assertIn("got type 'int'", msg)

    def test_no_args(self):
        @type_checked
        def no_args() -> int:
            return 42

        self.assertEqual(no_args(), 42)

    def test_all_optional_missing(self):
        @type_checked
        def all_optional(a: int = 1, b: str = "default") -> str:
            return f"{a}-{b}"

        self.assertEqual(all_optional(), "1-default")
        self.assertEqual(all_optional(a=5), "5-default")

    def test_error_message_format(self):
        @type_checked
        def typed_func(x: int) -> int:
            return x

        with self.assertRaises(TypeError) as cm:
            typed_func("not an int")

        msg = str(cm.exception)
        self.assertIn("Validation error in 'typed_func'", msg)
        self.assertIn("Input should be a valid integer", msg)
        self.assertIn("got type 'str'", msg)

    def test_varargs(self):
        @type_checked
        def varargs_func(*args: int) -> int:
            return sum(args)

        self.assertEqual(varargs_func(1, 2, 3), 6)

        with self.assertRaises(TypeError):
            varargs_func(1, "two", 3)

    def test_kwargs(self):
        @type_checked
        def kwargs_func(**kwargs: str) -> int:
            return len(kwargs)

        self.assertEqual(kwargs_func(a="x", b="y"), 2)

        with self.assertRaises(TypeError):
            kwargs_func(a=1, b="y")


if __name__ == "__main__":
    unittest.main()
