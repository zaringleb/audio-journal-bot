import unittest

from src.text_utils import chunk_text


class ChunkTextTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(chunk_text(""), [])

    def test_chunking_length(self):
        # Create a long repetitive text ~5,000 characters
        word = "hello"
        text = (word + " ") * 1000  # 6*1000=6000 chars approx (including spaces)
        chunks = chunk_text(text, max_chars=2000)
        # Expect 3 or 4 chunks depending on boundaries
        self.assertTrue(2 < len(chunks) <= 4)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 2000)

    def test_no_word_split(self):
        long_word = "a" * 1990 + " " + "b" * 20
        chunks = chunk_text(long_word, max_chars=2000)
        # Each chunk must be <= limit
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 2000)
        # Reconstruct text matches original
        self.assertEqual("".join(chunks), long_word)


if __name__ == "__main__":
    unittest.main() 