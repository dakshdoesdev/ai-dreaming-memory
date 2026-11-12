"""Collect a small, cached arXiv corpus and index it in the existing memory store."""

import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from memory_lab import Memory


HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
ATOM = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


def arxiv_id(value):
    if not isinstance(value, str):
        raise ValueError("arXiv IDs must be strings.")
    value = value.strip()
    if value.startswith("arXiv:"):
        value = value[6:]
    if "://" in value:
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme != "https" or parsed.hostname not in HOSTS:
            raise ValueError("Only HTTPS arxiv.org paper URLs are accepted.")
        value = re.sub(r"^/(?:abs|pdf|html)/", "", parsed.path)
    value = re.sub(r"\.pdf$", "", value)
    if len(value) > 80 or not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z][a-z.-]+/\d{7})(?:v[1-9]\d*)?", value):
        raise ValueError(f"Invalid arXiv ID: {value!r}")
    return value


def _safe_url(url):
    parsed = urllib.parse.urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username
            or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Collector only fetches HTTPS URLs on approved arXiv hosts.")
    return url


class ArxivRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ArxivClient:
    def __init__(self):
        self.last_request = None

    def fetch(self, url, limit=25_000_000):
        _safe_url(url)
        if self.last_request is not None:
            time.sleep(max(0, 3.1 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        request = urllib.request.Request(url, headers={
            "User-Agent": "DreamingMemoryLab/1.0 (small research corpus; cached requests)"})
        try:
            with urllib.request.build_opener(ArxivRedirect).open(request, timeout=45) as response:
                _safe_url(response.geturl())
                data = response.read(limit + 1)
                if len(data) > limit:
                    raise ValueError("arXiv response exceeds the collector size limit.")
                return data
        except urllib.error.HTTPError as exc:
            exc.close()
            raise ValueError(f"arXiv HTTP {exc.code} for {url}; retry later rather than bypassing limits.") from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError(f"arXiv request failed for {url}; retry later or use the existing cache.") from None


def parse_atom(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("arXiv returned invalid Atom XML.") from exc
    result = []
    for entry in root.findall("a:entry", ATOM):
        raw_id = entry.findtext("a:id", default="", namespaces=ATOM)
        # Atom entry URLs historically use HTTP; this is metadata, not a request.
        ident = arxiv_id(raw_id.replace("http://", "https://", 1))
        if not re.search(r"v[1-9]\d*$", ident):
            raise ValueError("arXiv metadata did not resolve to an explicit paper version.")
        text = lambda key: " ".join(entry.findtext(key, default="", namespaces=ATOM).split())
        title, abstract = text("a:title"), text("a:summary")
        if not title or not abstract:
            raise ValueError("arXiv metadata is missing a title or abstract.")
        result.append({"arxiv_id": ident, "title": title,
            "authors": [" ".join(author.findtext("a:name", default="", namespaces=ATOM).split())
                        for author in entry.findall("a:author", ATOM)],
            "abstract": abstract, "published": text("a:published"), "updated": text("a:updated"),
            "url": "https://arxiv.org/abs/" + ident,
            "license": text("x:license") or "unknown; verify paper license before redistribution"})
    if not result:
        raise ValueError("No arXiv paper matched the requested ID.")
    return result


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if not self.depth:
            if tag == "article" and "ltx_document" in attrs.get("class", "").split():
                self.depth = 1
            return
        if tag not in ("br", "hr", "img", "input", "meta", "link", "wbr", "source", "area", "embed", "param", "track", "col", "base"):
            self.depth += 1
        if tag in ("script", "style", "nav"):
            self.skip += 1
        if tag in ("p", "div", "section", "h1", "h2", "h3", "h4", "li", "tr", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if not self.depth:
            return
        if tag in ("script", "style", "nav") and self.skip:
            self.skip -= 1
        if tag in ("p", "div", "section", "h1", "h2", "h3", "h4", "li", "tr"):
            self.parts.append("\n")
        self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.skip:
            self.parts.append(data)

    def text(self):
        return "\n".join(" ".join(line.split()) for line in "".join(self.parts).splitlines() if line.strip())


class AbstractMetadata(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.authors, self.abstract = {}, [], []
        self.abstract_depth = 0
        self.license = "unknown; verify paper license before redistribution"

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            name, content = attrs.get("name", ""), attrs.get("content", "")
            if name == "citation_author":
                self.authors.append(content)
            else:
                self.meta[name] = content
        if tag == "a" and (attrs.get("title") == "Rights to this article" or attrs.get("rel") == "license"):
            self.license = attrs.get("href", self.license)
        if tag == "blockquote" and "abstract" in attrs.get("class", "").split():
            self.abstract_depth = 1
        elif self.abstract_depth:
            self.abstract_depth += 1

    def handle_endtag(self, tag):
        if self.abstract_depth:
            self.abstract_depth -= 1

    def handle_data(self, data):
        if self.abstract_depth:
            self.abstract.append(data)


def parse_abstract_metadata(data, requested_id):
    """Fallback to arXiv's citation metadata when the Atom endpoint is unavailable."""
    html = data.decode("utf-8")
    parser = AbstractMetadata()
    parser.feed(html)
    base = re.sub(r"v\d+$", "", requested_id)
    reported = parser.meta.get("citation_arxiv_id", "")
    if re.sub(r"v\d+$", "", reported) != base:
        raise ValueError("arXiv abstract page did not identify the requested paper.")
    if re.search(r"v\d+$", requested_id):
        ident = requested_id
    else:
        version = re.search(r"this version, v([1-9]\d*)", html)
        ident = base + "v" + (version.group(1) if version else "1")
    abstract = re.sub(r"^\s*Abstract:\s*", "", " ".join(" ".join(parser.abstract).split()))
    title = parser.meta.get("citation_title", "").strip()
    if not title or not abstract or not parser.authors:
        raise ValueError("arXiv abstract page lacks usable citation metadata/abstract.")
    published = parser.meta.get("citation_date", "").replace("/", "-")
    return {"arxiv_id": ident, "title": title, "authors": parser.authors,
        "abstract": abstract, "published": published,
        "updated": parser.meta.get("citation_online_date", published).replace("/", "-"),
        "url": "https://arxiv.org/abs/" + ident, "license": parser.license,
        "metadata_source": "https://arxiv.org/abs/" + requested_id}


def _full_text(client, ident, directory):
    html_path, pdf_path = directory / "paper.html", directory / "paper.pdf"
    try:
        html = html_path.read_bytes() if html_path.exists() else client.fetch("https://arxiv.org/html/" + ident, 12_000_000)
        parser = ArticleText()
        parser.feed(html.decode("utf-8"))
        text = parser.text()
        if len(text) >= 1000:
            html_path.write_bytes(html)
            return text, "https://arxiv.org/html/" + ident
    except (ValueError, UnicodeError):
        pass
    if not shutil.which("pdftotext"):
        raise ValueError("This paper has no usable HTML; install Poppler pdftotext to read its PDF.")
    pdf = pdf_path.read_bytes() if pdf_path.exists() else client.fetch("https://arxiv.org/pdf/" + ident)
    if not pdf.startswith(b"%PDF-"):
        raise ValueError("arXiv PDF response was not a PDF.")
    pdf_path.write_bytes(pdf)
    try:
        process = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"],
                                 capture_output=True, text=True, timeout=60, check=True)
    except (subprocess.SubprocessError, UnicodeError) as exc:
        raise ValueError("PDF text extraction failed; scanned papers require OCR, which is not provided.") from exc
    text = process.stdout.strip()
    if len(text) < 1000:
        raise ValueError("PDF yielded insufficient full text; refusing to substitute its abstract.")
    return text, "https://arxiv.org/pdf/" + ident


class PaperStore:
    def __init__(self, path):
        self.memory = Memory(path)
        self.db = self.memory.db
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                arxiv_id TEXT PRIMARY KEY, metadata TEXT NOT NULL,
                text TEXT NOT NULL, text_sha256 TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS paper_chunks (
                arxiv_id TEXT NOT NULL, chunk_index INTEGER NOT NULL,
                message_id INTEGER NOT NULL, text TEXT NOT NULL,
                PRIMARY KEY(arxiv_id, chunk_index));
        """)

    def close(self):
        self.memory.close()

    def upsert_paper(self, metadata, text):
        if not isinstance(metadata, dict) or not isinstance(text, str) or not text.strip():
            raise ValueError("A paper needs metadata and nonempty full text.")
        ident = arxiv_id(metadata.get("arxiv_id"))
        if not re.search(r"v[1-9]\d*$", ident):
            raise ValueError("Store an explicit arXiv version to make the corpus reproducible.")
        if not isinstance(metadata.get("title"), str) or not metadata["title"].strip():
            raise ValueError("Paper title is required.")
        digest = hashlib.sha256(text.encode()).hexdigest()
        if metadata.get("text_sha256", digest) != digest:
            raise ValueError("Paper text does not match its metadata hash.")
        metadata = dict(metadata, arxiv_id=ident, text_sha256=digest)
        for field, default in (("authors", []), ("abstract", ""), ("published", ""),
                               ("updated", ""), ("url", "https://arxiv.org/abs/" + ident),
                               ("license", "unknown"), ("text_source", "user-provided")):
            metadata.setdefault(field, default)
        with self.db:
            existing = self.db.execute("SELECT text_sha256 FROM papers WHERE arxiv_id=?", (ident,)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise ValueError("This pinned paper version already has different text; use a fresh database to change extraction.")
                return False
            self.db.execute("INSERT INTO papers VALUES (?,?,?,?)",
                            (ident, json.dumps(metadata, ensure_ascii=False), text, digest))
            # Insert directly in one transaction; Memory.add() commits each message independently.
            for index, start in enumerate(range(0, len(text), 1200)):
                chunk = f"Paper {ident}: {metadata['title'][:220]}\nChunk {index + 1}\n" + text[start:start + 1200]
                mid = self.db.execute("INSERT INTO messages(session,role,text) VALUES (?,'user',?)",
                                      ("arxiv:" + ident, chunk)).lastrowid
                self.memory.document("raw", chunk, [mid])
                self.db.execute("INSERT INTO paper_chunks VALUES (?,?,?,?)", (ident, index, mid, chunk))
        return True

    def get_papers(self):
        papers = []
        for row in self.db.execute("SELECT * FROM papers ORDER BY arxiv_id"):
            papers.append({"metadata": json.loads(row["metadata"]), "text": row["text"],
                "chunks": [dict(chunk) for chunk in self.db.execute(
                    "SELECT message_id,text,chunk_index FROM paper_chunks WHERE arxiv_id=? ORDER BY chunk_index", (row["arxiv_id"],))]})
        return papers


def collect(store, ids, cache_dir):
    """Collect explicit IDs sequentially; unversioned requests are pinned on first fetch."""
    if not ids:
        raise ValueError("Provide at least one arXiv ID.")
    requested = list(dict.fromkeys(arxiv_id(value) for value in ids))
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    client, collected = ArxivClient(), []
    for requested_id in requested:
        metadata_path = cache / (requested_id.replace("/", "_") + ".json")
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text())
            ident = arxiv_id(metadata["arxiv_id"])
        else:
            query = urllib.parse.urlencode({"id_list": requested_id, "max_results": 1})
            try:
                source = "https://export.arxiv.org/api/query?" + query
                metadata = parse_atom(client.fetch(source, 2_000_000))[0]
                metadata["metadata_source"] = source
            except ValueError:
                metadata = parse_abstract_metadata(client.fetch("https://arxiv.org/abs/" + requested_id, 2_000_000), requested_id)
            ident = metadata["arxiv_id"]
            if re.sub(r"v\d+$", "", ident) != re.sub(r"v\d+$", "", requested_id) or (
                    re.search(r"v\d+$", requested_id) and requested_id != ident):
                raise ValueError("arXiv returned a different paper/version than requested.")
        directory = cache / ident.replace("/", "_")
        directory.mkdir(parents=True, exist_ok=True)
        text_path = directory / "paper.txt"
        if text_path.exists() and "text_sha256" in metadata:
            text = text_path.read_text()
        else:
            text, metadata["text_source"] = _full_text(client, ident, directory)
            metadata["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
            text_path.write_text(text)
        store.upsert_paper(metadata, text)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
        collected.append(metadata)
    return collected
