"""doc and prose inputs: md, txt, json parsed directly; pdf and docx parsed
locally. formats per build-spec: pasted text counts as a source too.

pdf and docx need no external service: pypdf and python-docx run anywhere
beholder runs, and page provenance survives the parse. firecrawl stays for
live url scraping, which a local parser cannot do."""

import base64
import binascii

from .firecrawl import FirecrawlClient
from .repo_walk import chunk_text

DIRECT_SUFFIXES = {".md", ".txt", ".json", ".rst"}
FIRECRAWL_SUFFIXES = {".pdf", ".docx", ".doc"}


def suffix_of(filename: str) -> str:
    name = filename.lower()
    return name[name.rfind(".") :] if "." in name else ""


def parse_direct_text(text: str, label: str, kind: str = "doc") -> list[dict]:
    """md, txt, json: parsed locally, no external service, no key needed."""
    return [dict(c, kind=kind) for c in chunk_text(text, label)]


def decode_b64(content_b64: str) -> bytes:
    try:
        return base64.b64decode(content_b64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise ValueError("content is not valid base64") from e


def parse_pdf_pages(raw: bytes) -> list[str]:
    """one page, one text. a page that extracts to nothing is kept as empty:
    the page count is the truth about the document."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return [(page.extract_text() or "") for page in reader.pages]


def parse_docx_text(raw: bytes) -> str:
    """docx is one flow of paragraphs; page breaks are not in the format.
    chunk boundaries come later, provenance is the document."""
    import io

    import docx

    doc = docx.Document(io.BytesIO(raw))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def parse_binary_document(filename: str, raw: bytes) -> list[dict]:
    """pdf and docx, parsed locally. provenance is the document itself:
    doc type, the filename as ref, the page for pdf chunks."""
    suffix = suffix_of(filename)
    if suffix == ".pdf":
        try:
            pages = parse_pdf_pages(raw)
        except Exception as e:  # noqa: ble001 - corrupt uploads are user-facing
            raise ValueError(f"could not parse {filename}: not a readable pdf") from e
        chunks = []
        for n, page_text in enumerate(pages, start=1):
            chunks.extend({**c, "kind": "doc", "page": n} for c in chunk_text(page_text, filename))
        return chunks
    if suffix in (".docx", ".doc"):
        try:
            flow = parse_docx_text(raw)
        except Exception as e:  # noqa: ble001 - corrupt uploads are user-facing
            raise ValueError(f"could not parse {filename}: not a readable docx") from e
        return [dict(c, kind="doc") for c in chunk_text(flow, filename)]
    raise ValueError(f"unsupported document: {filename}")


async def parse_document(filename: str, text: str | None = None, content_b64: str | None = None, firecrawl: FirecrawlClient | None = None) -> list[dict]:
    """returns chunks for any supported doc input. direct formats parse
    locally from text; pdf and docx parse locally from bytes. provenance
    is the document itself: doc type, the filename as ref, page when the
    format has pages."""
    suffix = suffix_of(filename)
    if text is not None:
        return parse_direct_text(text, filename)
    if suffix in DIRECT_SUFFIXES:
        raise ValueError(f"{suffix} files are sent as text, not base64")
    if suffix in FIRECRAWL_SUFFIXES:
        if content_b64 is None:
            raise ValueError(f"send {suffix} files as content_b64")
        return parse_binary_document(filename, decode_b64(content_b64))
    raise ValueError(f"unsupported document: {filename}")
