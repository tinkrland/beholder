"""doc and prose inputs: md, txt, json parsed directly; pdf and docx through
firecrawl. formats per build-spec: pasted text counts as a source too."""

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


MIME_BY_SUFFIX = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".doc": "application/msword"}


async def parse_document(filename: str, text: str | None = None, content_b64: str | None = None, firecrawl: FirecrawlClient | None = None) -> list[dict]:
    """returns chunks for any supported doc input. direct formats parse
    locally; pdf and docx go through firecrawl as a data uri. provenance is
    the document itself: doc type, the filename as ref."""
    suffix = suffix_of(filename)
    if text is not None:
        return parse_direct_text(text, filename)
    if suffix in DIRECT_SUFFIXES:
        raise ValueError(f"{suffix} files are sent as text, not base64")
    if suffix in FIRECRAWL_SUFFIXES:
        if content_b64 is None:
            raise ValueError(f"send {suffix} files as content_b64")
        raw = decode_b64(content_b64)
        client = firecrawl or FirecrawlClient()
        uri = f"data:{MIME_BY_SUFFIX[suffix]};base64,{base64.b64encode(raw).decode()}"
        markdown = await client.scrape_markdown(uri)
        return [dict(c, kind="doc") for c in chunk_text(markdown, filename)]
    raise ValueError(f"unsupported document: {filename}")
