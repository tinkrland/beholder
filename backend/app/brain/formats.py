"""export formats: the same honest sentences, arranged for a different
reader or moment. pure, no io, no model calls.

every sentence in a view passed the honesty guard before export, so a
format is a deterministic rearrangement, never a rewrite. new prose
would be ungrounded by construction; rearranged grounded prose is not.
the formats differ in shape, never in claims."""

from ..schemas import PitchViewOut

FORMATS = ("markdown", "demo_script", "deck_outline", "partner_one_pager")


def _section_words(key: str) -> str:
    return key.replace("_", " ")


def _sections_in_order(view: PitchViewOut) -> list[tuple[str, list[str]]]:
    """[(key, [sentence text, ...])] for sections that say something."""
    by_id = {s.id: s.text for s in view.sentences}
    return [(sec.key, [by_id[sid] for sid in sec.sentence_ids if sid in by_id]) for sec in view.sections if sec.sentence_ids]


def render_markdown(view: PitchViewOut) -> str:
    return "\n\n".join(f"## {key}\n" + "\n".join(lines) for key, lines in _sections_in_order(view))


def render_demo_script(view: PitchViewOut, label: str) -> str:
    """what to say out loud, in order, with breathing room. sentences stay
    verbatim: the script says what the view says, no more."""
    head = f"demo script for {label}\n" if label else "demo script\n"
    beats = []
    for key, lines in _sections_in_order(view):
        beats.append(f"### {_section_words(key)}\n\n" + " ".join(lines))
    return (head + "\n\n" + "\n\n".join(beats)).strip()


def render_deck_outline(view: PitchViewOut, label: str) -> str:
    """slide by slide: a title slide, one slide per section, bullets are the
    sentences. the reader skims; the claims stay whole."""
    title = f"# {label or 'project'} deck" if label else "# project deck"
    slides = [title]
    for key, lines in _sections_in_order(view):
        slides.append(f"## {_section_words(key)}\n" + "\n".join(f"- {line}" for line in lines))
    return "\n\n".join(slides)


def render_partner_one_pager(view: PitchViewOut, label: str) -> str:
    """the partner reader: what it is, what it means for them, one page.
    section labels are spoken plainly, sentences stay whole."""
    head = f"{label or 'partner'} one-pager" if label else "partner one-pager"
    blocks = []
    for key, lines in _sections_in_order(view):
        blocks.append(f"{_section_words(key).upper()}\n" + "\n".join(lines))
    return head + "\n\n" + "\n\n".join(blocks)


def render(view: PitchViewOut, format_id: str, label: str = "") -> str:
    if format_id == "markdown":
        return render_markdown(view)
    if format_id == "demo_script":
        return render_demo_script(view, label)
    if format_id == "deck_outline":
        return render_deck_outline(view, label)
    if format_id == "partner_one_pager":
        return render_partner_one_pager(view, label)
    raise ValueError(f"unknown format: {format_id}. known: {', '.join(FORMATS)}")
