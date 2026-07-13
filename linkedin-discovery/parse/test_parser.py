# test_parser.py — tests for clean_html() and extract().
import os
import unittest
from unittest.mock import AsyncMock, patch

from parse.parser import clean_html
from parse.extract import extract
from parse.models import Candidate


class TestParser(unittest.TestCase):

    def test_empty_and_whitespace_input(self):
        # Empty string or spaces should return empty string
        self.assertEqual(clean_html(""), "")
        self.assertEqual(clean_html("   "), "")
        self.assertEqual(clean_html("\n\n  \t  \n"), "")
        # None should be handled gracefully
        self.assertEqual(clean_html(None), "")

    def test_basic_text_extraction(self):
        html = "<html><body><p>Hello World</p></body></html>"
        self.assertEqual(clean_html(html), "Hello World")

    def test_removes_noise_tags(self):
        # We test that elements in _NOISE_BLOCK_RE and _DROP_CHROME are removed completely
        html = """
        <html>
            <head>
                <style>body { font-size: 14px; }</style>
                <script>var x = 1;</script>
            </head>
            <body>
                <nav>
                    <a href="/jobs">Jobs</a>
                </nav>
                <main>
                    <h1>John Doe</h1>
                    <code>print('hello')</code>
                    <aside>Related profiles...</aside>
                    <form>
                        <input type="text" name="q" />
                        <button type="submit">Search</button>
                    </form>
                </main>
                <footer>
                    <p>Copyright 2026</p>
                </footer>
            </body>
        </html>
        """
        cleaned = clean_html(html)

        # Expected output should only contain "John Doe"
        self.assertEqual(cleaned, "John Doe")

        # Double check none of the dropped text leaks
        self.assertNotIn("font-size", cleaned)
        self.assertNotIn("var x = 1", cleaned)
        self.assertNotIn("Jobs", cleaned)
        self.assertNotIn("print('hello')", cleaned)
        self.assertNotIn("Related profiles", cleaned)
        self.assertNotIn("Search", cleaned)
        self.assertNotIn("Copyright", cleaned)

    def test_removes_html_comments(self):
        html = "<div>Hello <!-- hidden comment --> World</div>"
        cleaned = clean_html(html)
        # html5lib treats text nodes split by comments as separate text nodes,
        # which get separator \n in BeautifulSoup get_text.
        self.assertEqual(cleaned, "Hello\nWorld")
        self.assertNotIn("hidden comment", cleaned)

    def test_whitespace_normalization(self):
        # Tabs and consecutive spaces should collapse to a single space
        html = "<div>Line  with   multiple\t\tspaces</div>"
        self.assertEqual(clean_html(html), "Line with multiple spaces")

        # Blank lines should be completely ignored
        html = """
        <div>
            Line 1
            
            
            Line 2
        </div>
        """
        self.assertEqual(clean_html(html), "Line 1\nLine 2")

    def test_fixture_jane_doe(self):
        fixture_path = os.path.join(
            os.path.dirname(__file__), "fixtures", "profile_jane_doe.html"
        )
        with open(fixture_path, "r", encoding="utf-8") as f:
            html = f.read()

        cleaned = clean_html(html)

        # Check that core info is present
        self.assertIn("Jane Doe", cleaned)
        self.assertIn("Senior Software Engineer at Acme Corp", cleaned)
        self.assertIn("Bucharest, Romania", cleaned)

        # Check that noise is removed
        self.assertNotIn("gtag", cleaned)  # script
        self.assertNotIn("artdeco-card", cleaned)  # style
        self.assertNotIn("Home My Network", cleaned)  # nav
        self.assertNotIn("LinkedIn Corporation", cleaned)  # footer
        self.assertNotIn("People also viewed", cleaned)  # aside


class TestExtract(unittest.IsolatedAsyncioTestCase):

    async def test_extract_empty(self):
        # Empty inputs should return a default empty Candidate
        result = await extract("")
        self.assertEqual(result, Candidate())
        result = await extract("    ")
        self.assertEqual(result, Candidate())

    @patch("parse.extract.has_llm", return_value=False)
    async def test_extract_no_llm_key(self, mock_has_llm):
        # If no LLM key is configured, extract should raise a RuntimeError
        with self.assertRaises(RuntimeError) as context:
            await extract("Some clean text")
        self.assertIn("No LLM key set", str(context.exception))

    @patch("parse.extract.Agent.run")
    @patch("parse.extract.has_llm", return_value=True)
    async def test_extract_success(self, mock_has_llm, mock_run):
        # Mock successful output of agent.run()
        mock_candidate = Candidate(
            name="Jane Doe",
            headline="Senior Software Engineer at Acme Corp",
            location="Bucharest, Romania",
            years_experience=6,
            skills=["Python", "Go", "PostgreSQL", "Docker", "Kubernetes"],
            current_title="Senior Software Engineer",
            current_company="Acme Corp",
            education=["University of Bucharest"],
            summary="Backend engineer with 6 years' experience."
        )
        mock_run.return_value = AsyncMock(output=mock_candidate)

        # Run extraction
        result = await extract("Some clean profile text")

        # Verify output matches mocked candidate
        self.assertEqual(result.name, "Jane Doe")
        self.assertEqual(result.years_experience, 6)
        self.assertIn("Go", result.skills)
        self.assertEqual(result.current_company, "Acme Corp")
        mock_run.assert_called_once_with("Some clean profile text")


if __name__ == "__main__":
    unittest.main()
