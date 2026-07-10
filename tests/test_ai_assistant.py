"""AI assistant: reply parsing, LaTeX-fragment import, provider request
shaping, and end-to-end insertion into the visual editor."""
import os

import pytest

from khervedoc import ai_providers as providers
from khervedoc.ai_assistant import (
    document_body_latex, extract_latex, prose_only,
)
from khervedoc.importers import import_body_fragment
from khervedoc.model import (
    Document, DocMeta, List as ListNode, MathBlock, Paragraph, Section,
    Text, Title,
)


# ----------------------------- reply parsing -----------------------------

def test_prose_only_strips_code_fence():
    reply = "Here is a section.\n\n```latex\n\\section{Intro}\n```"
    assert prose_only(reply) == "Here is a section."


def test_prose_only_handles_truncated_block():
    # A cut-off block (no closing fence) must still not leak LaTeX.
    reply = "Sure!\n\n```latex\n\\section{Intro}\nSome text that got cut"
    assert prose_only(reply) == "Sure!"


def test_extract_latex_insert_mode():
    assert extract_latex("x ```latex\n\\section{A}\n``` y") == (
        "insert", "\\section{A}")
    assert extract_latex("```tex\nhi\n```") == ("insert", "hi")
    assert extract_latex("no code here") == ("insert", "")


def test_extract_latex_joins_multiple_insert_blocks():
    reply = "```latex\n\\section{A}\n```\nand\n```latex\ntext\n```"
    assert extract_latex(reply) == ("insert", "\\section{A}\n\ntext")


def test_extract_latex_rewrite_sentinel():
    reply = ("Reordered.\n\n```latex\n% REWRITE\n"
             "\\section{B}\n\n\\section{A}\n```")
    mode, latex = extract_latex(reply)
    assert mode == "rewrite"
    # the sentinel line is stripped; the full new body remains
    assert latex.startswith("\\section{B}")
    assert "% REWRITE" not in latex


def test_extract_latex_rewrite_sentinel_variants():
    for line in ("% REWRITE", "%rewrite", "% REPLACE", "% replace-all",
                 "%  Replace All  the body"):
        mode, _ = extract_latex(f"```latex\n{line}\n\\section{{X}}\n```")
        assert mode == "rewrite", line


# --------------------------- fragment importer ---------------------------

def test_import_body_fragment_sections_and_paragraphs():
    blocks = import_body_fragment(
        "\\section{Introduction}\n\nHello world.\n\nSecond paragraph.")
    assert isinstance(blocks[0], Section)
    assert blocks[0].children[0].text == "Introduction"
    assert isinstance(blocks[1], Paragraph)
    assert any(isinstance(b, Paragraph) for b in blocks[1:])


def test_import_body_fragment_math_and_list():
    blocks = import_body_fragment(
        "\\[ E = mc^2 \\]\n\n"
        "\\begin{itemize}\n\\item one\n\\item two\n\\end{itemize}")
    assert any(isinstance(b, MathBlock) for b in blocks)
    lists = [b for b in blocks if isinstance(b, ListNode)]
    assert lists and len(lists[0].items) == 2


def test_import_body_fragment_ignores_preamble_wrapper():
    # A model that ignores "body only" and returns a full document should
    # still yield just the body blocks, not the preamble.
    src = (r"\documentclass{article}" "\n"
           r"\begin{document}" "\n"
           r"\section{X}" "\n" r"body" "\n"
           r"\end{document}")
    blocks = import_body_fragment(src)
    assert isinstance(blocks[0], Section)
    assert blocks[0].children[0].text == "X"


def test_import_body_fragment_empty():
    assert import_body_fragment("") == []
    assert import_body_fragment("   \n  ") == []


# --------------------------- document context ----------------------------

def test_document_body_latex_empty():
    doc = Document(children=[], meta=DocMeta())
    assert "empty" in document_body_latex(doc)


def test_document_body_latex_serializes_body():
    doc = Document(meta=DocMeta(), children=[
        Title(children=[Text(text="My Paper")]),
        Section(children=[Text(text="Methods")]),
        Paragraph(children=[Text(text="We did science.")]),
    ])
    body = document_body_latex(doc)
    # body-only: the section and prose are present; no preamble/title macros
    assert "\\section{Methods}" in body
    assert "We did science." in body
    assert "\\documentclass" not in body
    assert "\\title" not in body


# ------------------------- provider request shaping ----------------------

class _FakeResp:
    def __init__(self, payload):
        import json
        self._data = json.dumps(payload).encode()
    def read(self):
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def _capture(monkeypatch, payload):
    """Patch urlopen; return a dict that captures the outgoing Request."""
    seen = {}

    def fake_urlopen(req, timeout=0):
        import json
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data.decode()) if req.data else None
        return _FakeResp(payload)

    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_urlopen)
    return seen


def test_chat_claude_splits_system_and_sets_key(monkeypatch):
    seen = _capture(monkeypatch, {"content": [{"type": "text",
                                               "text": "hi there"}]})
    out = providers.chat(
        "Claude", "claude-opus-4-8",
        [{"role": "system", "content": "SYS"},
         {"role": "user", "content": "hello"}],
        api_key="sk-ant-xyz")
    assert out == "hi there"
    assert seen["url"].endswith("/v1/messages")
    assert seen["body"]["system"] == "SYS"
    assert seen["body"]["messages"] == [{"role": "user", "content": "hello"}]
    # system message must not appear in the Anthropic messages array
    assert all(m["role"] != "system" for m in seen["body"]["messages"])
    assert seen["headers"].get("X-api-key") == "sk-ant-xyz"


def test_chat_openai_like_uses_bearer_and_chat_completions(monkeypatch):
    seen = _capture(monkeypatch,
                    {"choices": [{"message": {"content": "reply"}}]})
    out = providers.chat("ChatGPT", "gpt-4o",
                         [{"role": "user", "content": "hi"}],
                         api_key="sk-123")
    assert out == "reply"
    assert seen["url"].endswith("/v1/chat/completions")
    assert seen["headers"].get("Authorization") == "Bearer sk-123"


def test_chat_ollama_needs_no_key_and_hits_local(monkeypatch):
    seen = _capture(monkeypatch, {"message": {"content": "local reply"}})
    out = providers.chat("Ollama", "llama3",
                         [{"role": "user", "content": "hi"}])
    assert out == "local reply"
    assert "localhost:11434" in seen["url"]
    assert seen["url"].endswith("/api/chat")


def test_list_models_shapes(monkeypatch):
    seen = _capture(monkeypatch, {"data": [{"id": "b"}, {"id": "a"}]})
    models = providers.list_models("ChatGPT", api_key="k")
    assert models == ["a", "b"]                     # sorted
    assert seen["url"].endswith("/v1/models")

    _capture(monkeypatch, {"models": [{"name": "m2"}, {"name": "m1"}]})
    assert providers.list_models("Ollama") == ["m1", "m2"]


def test_custom_base_url_overrides_default(monkeypatch):
    seen = _capture(monkeypatch,
                    {"choices": [{"message": {"content": "ok"}}]})
    providers.chat("Local", "x", [{"role": "user", "content": "hi"}],
                   base_url="http://localhost:9999")
    assert seen["url"].startswith("http://localhost:9999/")


# --------------------- end-to-end: insert into editor --------------------

@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_insert_blocks_writes_generated_latex(qapp):
    from khervedoc.editor import DocumentEditor
    ed = DocumentEditor()
    ed.set_document(Document(children=[], meta=DocMeta()))
    blocks = import_body_fragment(
        "\\section{Results}\n\nWe found something.")
    ed.insert_blocks(blocks)
    out = ed.get_document()
    kinds = [type(b).__name__ for b in out.children]
    assert "Section" in kinds
    texts = [b.children[0].text for b in out.children
             if isinstance(b, Section)]
    assert "Results" in texts


def test_insert_blocks_appends_after_existing(qapp):
    from khervedoc.editor import DocumentEditor
    ed = DocumentEditor()
    ed.set_document(Document(
        meta=DocMeta(),
        children=[Paragraph(children=[Text(text="Existing.")])]))
    ed.insert_blocks(import_body_fragment("\\section{New}"))
    out = ed.get_document()
    assert any(isinstance(b, Section) and b.children[0].text == "New"
               for b in out.children)
    # the original paragraph survives
    assert any(isinstance(b, Paragraph) and
               b.children and b.children[0].text == "Existing."
               for b in out.children)


def _section_names(doc):
    return [b.children[0].text for b in doc.children
            if isinstance(b, Section) and b.children]


def test_replace_body_reorders_and_deletes(qapp):
    # The core of what the AI could not do before: move/reorder/dedupe.
    from khervedoc.editor import DocumentEditor
    ed = DocumentEditor()
    ed.set_document(Document(meta=DocMeta(), children=[
        Section(children=[Text(text="Conclusion")]),
        Section(children=[Text(text="Availability")]),
        Section(children=[Text(text="Conclusion")]),   # duplicate
    ]))
    # Rewrite: single Conclusion, placed before Availability.
    ed.replace_body(import_body_fragment(
        "\\section{Conclusion}\n\n\\section{Availability}"))
    assert _section_names(ed.get_document()) == ["Conclusion", "Availability"]


def test_replace_body_preserves_title_and_author(qapp):
    from khervedoc.editor import DocumentEditor
    from khervedoc.model import Author
    ed = DocumentEditor()
    ed.set_document(Document(meta=DocMeta(), children=[
        Title(children=[Text(text="My Paper")]),
        Author(children=[Text(text="Jane Doe")]),
        Section(children=[Text(text="Old")]),
    ]))
    ed.replace_body(import_body_fragment("\\section{New}"))
    out = ed.get_document()
    assert any(isinstance(b, Title) and b.children[0].text == "My Paper"
               for b in out.children)
    assert any(isinstance(b, Author) and b.children[0].text == "Jane Doe"
               for b in out.children)
    assert _section_names(out) == ["New"]           # body replaced
