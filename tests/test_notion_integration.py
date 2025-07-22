import os
import unittest
from datetime import date
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RUN_NOTION = os.getenv("RUN_NOTION_TESTS") == "1"
NOTION_TEST_DATABASE_ID = os.getenv("NOTION_TEST_DATABASE_ID")

if RUN_NOTION:
    from src.notion_integration import client, create_journal_entry


@unittest.skipUnless(RUN_NOTION, "Set RUN_NOTION_TESTS=1 to enable Notion API tests.")
class NotionIntegrationTests(unittest.TestCase):
    def test_basic_connection(self):
        db = client.databases.retrieve(NOTION_TEST_DATABASE_ID)
        self.assertEqual(db["object"], "database")

    def test_push_dummy_entry(self):
        today = date.today()
        page = create_journal_entry(
            keyword="Dummy Test Entry",
            journal_date=today,
            structured="structured text",
        )
        self.assertEqual(page["object"], "page")
        # Clean up: archive the page so DB stays tidy
        client.pages.update(page["id"], archived=True)
