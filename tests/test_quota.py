import unittest
from src.quota import remaining_quota
class QuotaTests(unittest.TestCase):
    def test_remaining(self): self.assertEqual(remaining_quota(10, 3), 7)
    def test_exhausted(self): self.assertEqual(remaining_quota(10, 12), 0)
    def test_negative(self):
        with self.assertRaises(ValueError): remaining_quota(-1, 0)
if __name__ == "__main__": unittest.main()
