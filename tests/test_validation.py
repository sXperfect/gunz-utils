import unittest
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

if __name__ == "__main__":
    unittest.main()
