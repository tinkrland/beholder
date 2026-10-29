"""export formats: the same honest sentences arranged differently. pure
render tests with a canned view; markdown must stay byte-stable because
existing exports rest on it."""

import pytest

from app.brain import formats
from app.schemas import PitchViewOut, Section, Sentence


def _view():
    return PitchViewOut(
        id="v",
        target_id="t",
        model_version_id="m",
        lens_version=1,
        sections=[Section(key="one_liner", sentence_ids=["s1"]), Section(key="objections", sentence_ids=["s2", "s3"])],
        sentences=[
            Sentence(id="s1", text="studiogram makes product photos reproducible."),
            Sentence(id="s2", text="the scene state is byte-for-byte reproducible."),
            Sentence(id="s3", text="no diffusion touches the product."),
        ],
        cache_key="k",
    )


def test_markdown_is_the_stable_shape():
    assert formats.render(_view(), "markdown") == (
        "## one_liner\nstudiogram makes product photos reproducible.\n\n"
        "## objections\nthe scene state is byte-for-byte reproducible.\nno diffusion touches the product."
    )


def test_demo_script_speaks_the_sentences_in_order():
    body = formats.render(_view(), "demo_script", label="yc application")
    assert body.startswith("demo script for yc application")
    assert "### one liner" in body
    assert "### objections" in body
    # sentences stay verbatim, joined as spoken beats
    assert "the scene state is byte-for-byte reproducible. no diffusion touches the product." in body


def test_deck_outline_is_slide_by_slide():
    body = formats.render(_view(), "deck_outline", label="yc application")
    assert body.startswith("# yc application deck")
    assert "## one liner\n- studiogram makes product photos reproducible." in body
    assert "- no diffusion touches the product." in body


def test_partner_one_pager_shouts_section_labels():
    body = formats.render(_view(), "partner_one_pager", label="shopify")
    assert body.startswith("shopify one-pager")
    assert "ONE LINER\nstudiogram makes product photos reproducible." in body
    assert "OBJECTIONS" in body


def test_every_format_carries_every_sentence():
    """a format rearranges; it never drops a grounded sentence."""
    for f in formats.FORMATS:
        body = formats.render(_view(), f, label="l")
        for sentence in ("studiogram makes product photos reproducible.", "the scene state is byte-for-byte reproducible.", "no diffusion touches the product."):
            assert sentence in body, f


def test_unknown_format_is_rejected():
    with pytest.raises(ValueError, match="unknown format"):
        formats.render(_view(), "carrier_pigeon")
