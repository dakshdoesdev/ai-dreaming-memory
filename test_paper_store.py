import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

import paper_store as papers


ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/2410.10813v2</id><title>LongMemEval: A memory benchmark</title>
<summary>A benchmark of long term agent memory.</summary><published>2024-10-14T00:00:00Z</published>
<updated>2025-03-04T00:00:00Z</updated><author><name>Di Wu</name></author>
</entry></feed>'''


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="paper-store-test-")
        self.addCleanup(self.tmp.cleanup)
        self.store = papers.PaperStore(str(Path(self.tmp.name) / "papers.db"))
        self.addCleanup(self.store.close)
        self.metadata = papers.parse_atom(ATOM)[0]

    def test_id_validation_and_pinned_metadata(self):
        self.assertEqual(papers.arxiv_id("https://arxiv.org/pdf/2410.10813v2.pdf"), "2410.10813v2")
        self.assertEqual(papers.arxiv_id("hep-th/9901001v1"), "hep-th/9901001v1")
        for value in ("../bad", "https://evil.test/abs/2410.10813", "2410.10813v0", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                papers.arxiv_id(value)
        self.assertEqual(self.metadata["authors"], ["Di Wu"])
        self.assertEqual(self.metadata["arxiv_id"], "2410.10813v2")

    def test_store_idempotent_bounded_and_persistent(self):
        text = "Memory research and reproducible tests. " * 100
        self.assertTrue(self.store.upsert_paper(self.metadata, text))
        self.assertFalse(self.store.upsert_paper(self.metadata, text))
        record = self.store.get_papers()[0]
        self.assertEqual(record["text"], text)
        self.assertEqual(record["metadata"]["text_sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertTrue(all(len(chunk["text"]) <= 1600 for chunk in record["chunks"]))
        self.assertEqual(len(record["chunks"]), self.store.memory.pending())
        self.assertTrue(self.store.memory.retrieve("research", "rag"))
        with contextlib.closing(papers.PaperStore(str(Path(self.tmp.name) / "papers.db"))) as reopened:
            self.assertEqual(reopened.get_papers(), [record])
        with self.assertRaisesRegex(ValueError, "different text"):
            self.store.upsert_paper(self.metadata, text + "changed")

    def test_transaction_rolls_back_chunks_and_paper(self):
        with patch.object(self.store.memory, "document", side_effect=sqlite3.IntegrityError("failed")):
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.upsert_paper(self.metadata, "Memory research. " * 200)
        self.assertEqual(self.store.get_papers(), [])
        self.assertEqual(self.store.memory.pending(), 0)

    def test_hash_and_unversioned_rejection(self):
        with self.assertRaisesRegex(ValueError, "hash"):
            self.store.upsert_paper(dict(self.metadata, text_sha256="bad"), "paper")
        with self.assertRaisesRegex(ValueError, "explicit"):
            self.store.upsert_paper(dict(self.metadata, arxiv_id="2410.10813"), "paper")

    def test_html_parser_excludes_page_chrome_and_scripts(self):
        parser = papers.ArticleText()
        parser.feed('<nav>Chrome</nav><article class="ltx_document"><h1>Title</h1><p>Agent <em>memory</em>.</p><script>bad()</script><p>Findings.</p></article><footer>Ignore</footer>')
        self.assertEqual(parser.text(), "Title\nAgent memory.\nFindings.")

    def test_html_void_self_closing_tags_do_not_end_article(self):
        parser = papers.ArticleText()
        parser.feed('<article class="ltx_document"><p>Before</p><img src="x"/><br/><hr/><p>After</p></article><footer>Ignore</footer>')
        self.assertEqual(parser.text(), "Before\nAfter")
        self.assertEqual(parser.depth, 0)

    def test_collection_uses_cache_and_pins_version(self):
        cache = Path(self.tmp.name) / "cache"
        text = "This is the full paper body about memory research. " * 100
        html = ('<article class="ltx_document"><p>' + text + '</p></article>').encode()
        with patch.object(papers.ArxivClient, "fetch", side_effect=[ATOM, html]) as fetch:
            result = papers.collect(self.store, ["2410.10813"], cache)
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual(result[0]["arxiv_id"], "2410.10813v2")
        with patch.object(papers.ArxivClient, "fetch", side_effect=AssertionError("network called")):
            self.assertEqual(papers.collect(self.store, ["2410.10813"], cache), result)
        target = cache / "2410.10813v2" / "paper.txt"
        target.write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "hash"):
            papers.collect(self.store, ["2410.10813"], cache)

    def test_pdf_fallback(self):
        client = Mock()
        client.fetch.side_effect = [ValueError("no html"), b"%PDF-1.7 fake"]
        process = Mock(stdout="Full extracted body. " * 100)
        with patch.object(papers.shutil, "which", return_value="/usr/bin/pdftotext"), patch.object(papers.subprocess, "run", return_value=process) as run:
            text, source = papers._full_text(client, "2410.10813v2", Path(self.tmp.name))
        self.assertIn("Full extracted body", text)
        self.assertEqual(source, "https://arxiv.org/pdf/2410.10813v2")
        self.assertEqual(run.call_args.args[0][0], "pdftotext")

    def test_abstract_metadata_fallback(self):
        html = b'''<meta name="citation_arxiv_id" content="2410.10813">
            <meta name="citation_title" content="LongMemEval">
            <meta name="citation_author" content="Di Wu">
            <meta name="citation_date" content="2024/10/14">
            <div>last revised (this version, v2)</div>
            <blockquote class="abstract mathjax"><span>Abstract:</span> Agent memory evaluation.</blockquote>
            <a title="Rights to this article" href="https://creativecommons.org/licenses/by/4.0/">license</a>'''
        meta = papers.parse_abstract_metadata(html, "2410.10813")
        self.assertEqual(meta["arxiv_id"], "2410.10813v2")
        self.assertEqual(meta["abstract"], "Agent memory evaluation.")
        self.assertEqual(meta["published"], "2024-10-14")
        self.assertIn("creativecommons", meta["license"])
        text = ("Full research body. " * 100).encode()
        with patch.object(papers.ArxivClient, "fetch", side_effect=[ValueError("API unavailable"), html,
                b'<article class="ltx_document"><p>' + text + b'</p></article>']):
            result = papers.collect(self.store, ["2410.10813"], Path(self.tmp.name) / "fallback")
        self.assertEqual(result[0]["arxiv_id"], "2410.10813v2")

    def test_pacing_size_and_host_validation(self):
        class Response(io.BytesIO):
            def geturl(self):
                return "https://arxiv.org/abs/2410.10813v2"
        opener = Mock()
        opener.open.side_effect = [Response(b"abc"), Response(b"def"), Response(b"toolarge")]
        client = papers.ArxivClient()
        with patch.object(papers.urllib.request, "build_opener", return_value=opener), patch.object(papers.time, "monotonic", return_value=10), patch.object(papers.time, "sleep") as sleep:
            self.assertEqual(client.fetch("https://arxiv.org/abs/2410.10813v2"), b"abc")
            self.assertEqual(client.fetch("https://arxiv.org/abs/2410.10813v2"), b"def")
            sleep.assert_called_with(3.1)
            with self.assertRaisesRegex(ValueError, "size limit"):
                client.fetch("https://arxiv.org/abs/2410.10813v2", limit=3)
        for url in ("http://arxiv.org/abs/a", "https://arxiv.org.evil.test/a", "https://user@arxiv.org/a"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                client.fetch(url)
        with self.assertRaises(ValueError):
            papers.ArxivRedirect().redirect_request(None, None, 302, None, {}, "https://evil.test/a")


if __name__ == "__main__":
    unittest.main()
