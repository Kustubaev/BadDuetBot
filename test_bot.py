import tempfile
import unittest
from pathlib import Path

from bot import INTERACTIONS, SUBSTANCES, first_choices, load_interactions, pair_key, second_choices


class InteractionDataTests(unittest.TestCase):
    def test_dataset_size(self) -> None:
        self.assertEqual(len(SUBSTANCES), 8)
        self.assertEqual(len(INTERACTIONS), 9)

    def test_first_choices_are_unique_from_both_columns(self) -> None:
        self.assertEqual(first_choices(INTERACTIONS), SUBSTANCES)
        self.assertEqual(len(SUBSTANCES), len(set(SUBSTANCES)))
        self.assertIn("Варфарин", SUBSTANCES)
        self.assertIn("Витамин К", SUBSTANCES)

    def test_second_choices_use_both_columns(self) -> None:
        self.assertEqual(second_choices("Варфарин", INTERACTIONS), ["Витамин К"])
        self.assertEqual(second_choices("Витамин К", INTERACTIONS), ["Варфарин"])
        self.assertEqual(
            second_choices("Карбонат магния", INTERACTIONS),
            ["Аторвастатин", "Питавастатин", "Розувастатин", "Эзетимиб"],
        )

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
