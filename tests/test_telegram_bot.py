import unittest

import telegram_bot


class TelegramBotHelperTests(unittest.TestCase):
    def test_split_message_respects_limit(self):
        text = "line-1\n" + ("A" * 80) + "\nline-3"
        chunks = telegram_bot.split_message(text, max_len=25)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 25 for chunk in chunks))
        self.assertTrue(chunks[0].startswith("line-1"))
        self.assertTrue(chunks[-1].endswith("line-3"))

    def test_format_document_overview_uses_fields_and_preview(self):
        overview = telegram_bot.format_document_overview(
            language="Русский",
            filename="demo.pdf",
            chunk_count=12,
            key_fields={
                "customer_name": "КГУ Demo",
                "total_amount": "12 500 000 тенге",
            },
            preview="Текст " * 200,
        )

        self.assertIn("Что удалось распознать", overview)
        self.assertIn("demo.pdf", overview)
        self.assertIn("КГУ Demo", overview)
        self.assertIn("12 500 000 тенге", overview)
        self.assertIn("Короткий предпросмотр", overview)
        self.assertIn("...", overview)


if __name__ == "__main__":
    unittest.main()
