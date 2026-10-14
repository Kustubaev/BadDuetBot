import tempfile
import unittest
from pathlib import Path

from bot import INTERACTIONS, SUBSTANCES, load_interactions, pair_key


class InteractionDataTests(unittest.TestCase):
    def test_test_dataset_has_all_pairs(self) -> None:
        self.assertEqual(len(SUBSTANCES), 7)
        self.assertEqual(len(INTERACTIONS), 21)

    def test_pair_order_does_not_matter(self) -> None:
        self.assertEqual(pair_key("Варфарин", "Витамин К"), pair_key("Витамин К", "Варфарин"))

    def test_duplicate_pair_is_rejected(self) -> None:
        contents = (
            "substance_1,substance_2,reaction,explanation\n"
            "А,Б,Нейтрально,Текст\n"
            "Б,А,Нейтрально,Текст\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.csv"
            path.write_text(contents, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_interactions(path)


if __name__ == "__main__":
    unittest.main()
