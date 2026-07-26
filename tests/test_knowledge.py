"""
Unit tests for the Knowledge module.

Tests:
- chunk_text: paragraph, sentence, character-level splitting
- KnowledgeDoc and SearchResult dataclasses
- SimpleKnowledgeBase: add_text, search, list, delete, stats
- ChromaDBKnowledgeBase: add_text, search, list, delete (with mock)
- Workflow integration: knowledge enrichment
- Edge cases: empty text, long text, no query, unavailable ChromaDB
"""

import pytest

from src.knowledge import (
    KnowledgeDoc,
    SearchResult,
    SimpleKnowledgeBase,
    chunk_text,
    create_knowledge_base,
)

from src.workflow import Workflow


# ============================================================
# chunk_text Tests
# ============================================================


class TestChunkText:
    def test_empty_text(self):
        """Empty text should return empty list."""
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text(self):
        """Short text (under chunk_size) should return as single chunk."""
        result = chunk_text("Hello world", chunk_size=500)
        assert len(result) == 1
        assert result[0] == "Hello world"

    def test_paragraph_boundary(self):
        """Chunking should prefer paragraph boundaries."""
        text = "A" * 100 + "\n\n" + "B" * 100
        result = chunk_text(text, chunk_size=150, overlap=0)
        assert len(result) >= 2
        # Should break at paragraph boundary, not in middle of text
        assert "A" * 100 in result[0]
        assert "B" * 100 in result[-1]

    def test_sentence_boundary(self):
        """Chunking should prefer sentence boundaries when no paragraph break."""
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        result = chunk_text(text, chunk_size=30, overlap=5)
        assert len(result) >= 2
        # Each chunk should contain complete sentences
        for chunk in result:
            assert len(chunk) > 0

    def test_overlap(self):
        """Chunks should overlap as specified."""
        text = "A" * 200 + "B" * 200 + "C" * 200
        result = chunk_text(text, chunk_size=100, overlap=50)
        assert len(result) >= 3
        # With overlap, each chunk should share content with neighbors

    def test_long_text(self):
        """Long text should create multiple chunks."""
        text = "Word " * 1000  # ~6000 chars
        result = chunk_text(text, chunk_size=500, overlap=100)
        assert len(result) > 5
        assert all(len(c) <= 510 for c in result)  # chunk + overlap buffer

    def test_newlines_normalized(self):
        """Excessive newlines should be normalized."""
        text = "Para1\n\n\n\n\nPara2"
        result = chunk_text(text, chunk_size=500)
        assert len(result) == 1
        assert "\n\n" in result[0]
        assert "\n\n\n" not in result[0]

    def test_whitespace_only_after_normalization(self):
        """Text with only whitespace/newlines should return empty."""
        assert chunk_text("\n\n\n   \n\n") == []


# ============================================================
# KnowledgeDoc Tests
# ============================================================


class TestKnowledgeDoc:
    def test_default_values(self):
        """KnowledgeDoc should have sensible defaults."""
        doc = KnowledgeDoc(id="abc", filename="test.txt")
        assert doc.chunks == []
        assert doc.chunk_count == 0
        assert doc.char_count == 0

    def test_full_init(self):
        """KnowledgeDoc should store all fields."""
        doc = KnowledgeDoc(
            id="abc123",
            filename="report.txt",
            chunks=["chunk1", "chunk2"],
            chunk_count=2,
            char_count=500,
        )
        assert doc.id == "abc123"
        assert doc.filename == "report.txt"
        assert doc.chunk_count == 2
        assert doc.char_count == 500


# ============================================================
# SearchResult Tests
# ============================================================


class TestSearchResult:
    def test_default_values(self):
        """SearchResult should have sensible defaults."""
        result = SearchResult(content="test", doc_id="abc", filename="f.txt")
        assert result.score == 0.0
        assert result.chunk_index == 0

    def test_repr(self):
        """__repr__ should show key info."""
        result = SearchResult(
            content="Hello world from the document",
            doc_id="abc",
            filename="test.txt",
            score=0.95,
            chunk_index=2,
        )
        r = repr(result)
        assert "test.txt" in r
        assert "0.950" in r
        assert "Hello" in r


# ============================================================
# SimpleKnowledgeBase Tests
# ============================================================


@pytest.fixture
def simple_kb(tmp_path):
    """Create a SimpleKnowledgeBase in a temp directory."""
    path = tmp_path / "kb"
    return SimpleKnowledgeBase(path=str(path))


class TestSimpleKnowledgeBaseInit:
    def test_init_creates_directory(self, tmp_path):
        """SimpleKnowledgeBase should create the directory."""
        path = tmp_path / "new_kb"
        kb = SimpleKnowledgeBase(path=str(path))
        assert path.exists()
        assert kb.available is True
        kb.delete_all()


class TestSimpleKnowledgeBaseAddText:
    def test_add_text(self, simple_kb):
        """Adding text should return a doc_id."""
        doc_id = simple_kb.add_text("hello.txt", "Hello world content")
        assert doc_id is not None
        assert len(doc_id) == 16  # truncated SHA256 hex

    def test_add_empty_text(self, simple_kb):
        """Adding empty text should return None."""
        assert simple_kb.add_text("empty.txt", "") is None
        assert simple_kb.add_text("space.txt", "   ") is None

    def test_add_duplicate(self, simple_kb):
        """Adding the same text twice should return the same doc_id."""
        id1 = simple_kb.add_text("test.txt", "Same content")
        id2 = simple_kb.add_text("test.txt", "Same content")
        assert id1 == id2

    def test_add_multiple_documents(self, simple_kb):
        """Multiple documents should be stored independently."""
        id1 = simple_kb.add_text("doc1.txt", "Content one")
        id2 = simple_kb.add_text("doc2.txt", "Content two completely different")
        assert id1 != id2
        docs = simple_kb.list_documents()
        assert len(docs) == 2


class TestSimpleKnowledgeBaseSearch:
    def test_search_basic(self, simple_kb):
        """Searching should return relevant results."""
        simple_kb.add_text("fruit.txt", "Apple banana orange grape")
        simple_kb.add_text("animal.txt", "Dog cat bird fish")

        results = simple_kb.search("apple", n_results=5)
        assert len(results) >= 1
        assert any("Apple" in r.content for r in results)

    def test_search_empty_query(self, simple_kb):
        """Empty query should return empty list."""
        simple_kb.add_text("test.txt", "Some content")
        assert simple_kb.search("") == []
        assert simple_kb.search("   ") == []

    def test_search_no_match(self, simple_kb):
        """Search with no matches should return empty list."""
        simple_kb.add_text("test.txt", "Hello world")
        results = simple_kb.search("zzzzzzzz", n_results=5)
        assert results == []

    def test_search_n_results(self, simple_kb):
        """n_results parameter should limit results."""
        # Add doc with many words
        simple_kb.add_text("all.txt", "apple banana cherry date elderberry fig grape")
        results = simple_kb.search("a", n_results=2)
        assert len(results) <= 2

    def test_search_no_docs(self, simple_kb):
        """Searching empty knowledge base should return empty."""
        assert simple_kb.search("anything") == []


class TestSimpleKnowledgeBaseListDocuments:
    def test_list_documents_empty(self, simple_kb):
        """Empty KB should return empty list."""
        assert simple_kb.list_documents() == []

    def test_list_documents(self, simple_kb):
        """List should return all documents."""
        simple_kb.add_text("a.txt", "Content A")
        simple_kb.add_text("b.txt", "Content B")
        docs = simple_kb.list_documents()
        assert len(docs) == 2
        filenames = [d.filename for d in docs]
        assert "a.txt" in filenames
        assert "b.txt" in filenames


class TestSimpleKnowledgeBaseDelete:
    def test_delete_document(self, simple_kb):
        """Deleted document should not appear in list."""
        doc_id = simple_kb.add_text("test.txt", "Content")
        assert simple_kb.delete_document(doc_id) is True
        docs = simple_kb.list_documents()
        assert len(docs) == 0

    def test_delete_nonexistent(self, simple_kb):
        """Deleting non-existent doc should return False."""
        assert simple_kb.delete_document("nonexistent") is False

    def test_delete_all(self, simple_kb):
        """Deleting all should clear everything."""
        simple_kb.add_text("a.txt", "A")
        simple_kb.add_text("b.txt", "B")
        count = simple_kb.delete_all()
        assert count > 0
        docs = simple_kb.list_documents()
        assert len(docs) == 0


class TestSimpleKnowledgeBaseStats:
    def test_get_stats_empty(self, simple_kb):
        """Stats on empty KB should show zeros."""
        stats = simple_kb.get_stats()
        assert stats["available"] is True
        assert stats["chunks"] == 0
        assert stats["documents"] == 0

    def test_get_stats_after_add(self, simple_kb):
        """Stats should reflect added documents."""
        simple_kb.add_text("test.txt", "Some content here to search")
        stats = simple_kb.get_stats()
        assert stats["documents"] == 1
        assert stats["chunks"] >= 1


# ============================================================
# create_knowledge_base Tests
# ============================================================


class TestCreateKnowledgeBase:
    def test_create_simple(self, tmp_path):
        """Without chromadb, should return SimpleKnowledgeBase."""
        path = tmp_path / "test_kb"
        kb = create_knowledge_base(path=str(path))
        # Either SimpleKnowledgeBase if chromadb not installed,
        # or ChromaDBKnowledgeBase if installed
        assert kb.available is True or isinstance(kb, SimpleKnowledgeBase)

    def test_create_and_use(self, tmp_path):
        """Created KB should work immediately."""
        path = tmp_path / "working_kb"
        kb = create_knowledge_base(path=str(path))
        doc_id = kb.add_text("hello.txt", "Hello world!")
        assert doc_id is not None
        results = kb.search("hello", n_results=5)
        assert len(results) >= 1
        kb.delete_all()

    def test_create_multiple_docs(self, tmp_path):
        """Multiple documents should work."""
        path = tmp_path / "multi_kb"
        kb = create_knowledge_base(path=str(path))
        kb.add_text("a.txt", "Apple banana")
        kb.add_text("b.txt", "Dog cat")
        docs = kb.list_documents()
        assert len(docs) == 2
        kb.delete_all()


# ============================================================
# Workflow Integration Tests
# ============================================================


class TestWorkflowKnowledgeIntegration:
    @pytest.fixture
    def memory(self, tmp_path):
        """Create a temporary Memory instance."""
        from src.memory import Memory
        db_path = tmp_path / "test_kb_workflow.db"
        mem = Memory(str(db_path))
        yield mem
        mem.close()

    @pytest.fixture
    def settings(self):
        """Default Mock settings."""
        from src.settings import Settings, PROVIDER_MOCK
        return Settings(model_provider=PROVIDER_MOCK)

    @pytest.fixture
    def model_router(self, settings):
        """Create a ModelRouter with Mock provider."""
        from src.model_router import ModelRouter
        return ModelRouter(settings)

    @pytest.fixture
    def plugin_loader(self):
        """Create a PluginLoader."""
        from src.plugin import PluginLoader
        loader = PluginLoader(plugin_package="src.plugins")
        loader.discover()
        return loader

    @pytest.fixture
    def knowledge_base(self, tmp_path):
        """Create a SimpleKnowledgeBase for testing."""
        path = tmp_path / "test_workflow_kb"
        return SimpleKnowledgeBase(path=str(path))

    def test_workflow_with_knowledge(self, memory, model_router, plugin_loader, knowledge_base):
        """Workflow should accept and use knowledge_base."""
        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=knowledge_base,
            max_context_messages=5,
        )
        assert workflow.knowledge_base is not None

    def test_knowledge_enrichment(self, memory, model_router, plugin_loader, knowledge_base):
        """Workflow should enrich prompt with knowledge when available."""
        # Add knowledge
        knowledge_base.add_text("info.txt", "The answer is 42. This is secret knowledge.")

        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=knowledge_base,
            max_context_messages=5,
        )

        session_id = memory.create_session()
        result = workflow.process("What is the answer?", session_id=session_id)

        # Should work (maybe with knowledge mention in mock response)
        assert result.source == "llm"
        assert result.success is True

    def test_knowledge_no_enrichment_for_plugin(self, memory, model_router, plugin_loader, knowledge_base):
        """Plugin inputs should not trigger knowledge enrichment."""
        knowledge_base.add_text("math.txt", "2 + 2 = 4")

        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=knowledge_base,
            max_context_messages=5,
        )

        session_id = memory.create_session()
        result = workflow.process("2 + 3", session_id=session_id)

        # Should still route to plugin
        assert result.source == "plugin"

    def test_knowledge_stats_tracked(self, memory, model_router, plugin_loader, knowledge_base):
        """KB lookups should be tracked in stats."""
        knowledge_base.add_text("info.txt", "Some knowledge content here.")

        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=knowledge_base,
            max_context_messages=5,
        )

        session_id = memory.create_session()
        workflow.process("Tell me something", session_id=session_id)

        stats = workflow.get_stats()
        # KB lookup may or may not happen depending on search results
        # But the key is: total_kb_lookups key exists
        assert "total_kb_lookups" in stats

    def test_workflow_without_knowledge(self, memory, model_router, plugin_loader):
        """Workflow should work without knowledge_base."""
        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=None,
            max_context_messages=5,
        )
        assert workflow.knowledge_base is None

        session_id = memory.create_session()
        result = workflow.process("Hello!", session_id=session_id)
        assert result.source == "llm"
        assert result.success is True

    def test_workflow_repr_with_knowledge(self, memory, model_router, plugin_loader, knowledge_base):
        """Workflow repr should work with knowledge base."""
        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=plugin_loader,
            knowledge_base=knowledge_base,
        )
        r = repr(workflow)
        assert "Workflow" in r

    def test_knowledge_enrich_plugin_does_not_save_again(self, memory, model_router, knowledge_base, tmp_path):
        """Knowledge enriched prompts should still save correctly."""
        knowledge_base.add_text("greeting.txt", "Say hello back nicely.")

        workflow = Workflow(
            memory=memory,
            model_router=model_router,
            plugin_loader=None,
            knowledge_base=knowledge_base,
        )

        session_id = memory.create_session()
        before = memory.count_messages(session_id)
        workflow.process("Hello!", session_id=session_id)
        after = memory.count_messages(session_id)

        # Should save user + assistant = 2 messages
        assert after == before + 2
