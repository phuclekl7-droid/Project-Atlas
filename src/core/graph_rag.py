"""
GraphRAG (Feature #13).
Builds a lightweight knowledge graph on top of existing Knowledge Base documents.

Provides:
- Entity extraction from document chunks
- Relationship discovery between entities
- Graph traversal for context enrichment
- Simple JSON-based graph storage (no external DB needed)

The graph is stored as:
- Nodes: extracted entities (concepts, people, terms)
- Edges: relationships between entities (co-occurs, related-to)
- Weights: frequency of co-occurrence

Usage:
    graph = GraphRAG()
    graph.add_document("doc_1", "Python is a programming language for AI")
    graph.add_document("doc_2", "Machine Learning uses Python extensively")
    related = graph.get_related_concepts("Python", depth=2)
"""

import json
import os
import re
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.core import setup_logger

logger = setup_logger("graph_rag")


@dataclass
class GraphNode:
    """A node in the knowledge graph."""
    id: str = ""
    label: str = ""
    type: str = "concept"  # concept, person, technology, etc.
    frequency: int = 1
    first_seen: float = 0.0
    documents: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge between two nodes."""
    source: str = ""
    target: str = ""
    weight: float = 1.0
    relation: str = "co-occurs"
    documents: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """Result from a graph search."""
    node: GraphNode = field(default_factory=GraphNode)
    path: list[str] = field(default_factory=list)
    score: float = 0.0


# Common English stop words and filler
_STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "not",
    "no", "nor", "this", "that", "these", "those", "it", "its", "they",
    "them", "their", "we", "us", "our", "you", "your", "he", "she", "him",
    "her", "his", "who", "whom", "which", "what", "when", "where", "why",
    "how", "all", "each", "every", "both", "few", "more", "most", "some",
    "any", "none", "such", "only", "own", "same", "so", "than", "too",
    "very", "just", "about", "up", "down", "out", "over", "off", "under",
    "again", "further", "once", "here", "there", "then", "also", "if",
    "because", "while", "since", "until", "after", "before", "between",
    "through", "during", "above", "below", "into", "onto", "upon",
    "using", "based", "well", "other", "new", "many", "much", "like",
}


def _extract_entities(text: str) -> list[tuple[str, str]]:
    """
    Extract entities from text with type classification.

    Returns list of (entity_name, entity_type) tuples.
    """
    entities = []

    # Pattern 1: Capitalized multi-word phrases (Proper Nouns)
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
        phrase = match.group(0)
        if phrase.lower() not in _STOP_WORDS and len(phrase) > 3:
            entities.append((phrase, "concept"))

    # Pattern 2: Single capitalized words (potential entities)
    for match in re.finditer(r'\b([A-Z][a-z]{3,})\b', text):
        word = match.group(0)
        if word.lower() not in _STOP_WORDS:
            entities.append((word, "concept"))

    # Pattern 3: Technical terms (lowercase but specific patterns)
    tech_patterns = [
        (r'\b([a-z]+(?:\.[a-z]+)+)\b', "technology"),  # e.g., "tensorflow"
        (r'\b([A-Z]{2,})\b', "acronym"),  # e.g., "API", "LLM"
    ]
    for pattern, etype in tech_patterns:
        for match in re.finditer(pattern, text):
            word = match.group(0)
            if word.lower() not in _STOP_WORDS:
                entities.append((word, etype))

    # Deduplicate and clean
    seen = set()
    result = []
    for name, etype in entities:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            result.append((name, etype))

    return result


class GraphRAG:
    """
    Lightweight knowledge graph for RAG (Retrieval-Augmented Generation).

    Builds a graph of entities and their relationships from document content,
    enabling graph-based context enrichment alongside vector search.

    Usage:
        graph = GraphRAG(path="data/graph")

        # Add document content
        graph.add_document("doc_1", "Python is widely used for Machine Learning")
        graph.add_document("doc_2", "Deep Learning is a subset of Machine Learning")

        # Search
        results = graph.search("Python")
        related = graph.get_related_concepts("Machine Learning")

        # Export
        stats = graph.get_stats()
    """

    def __init__(self, path: str = "data/graph"):
        self.path = str(path)
        Path(self.path).mkdir(parents=True, exist_ok=True)

        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[tuple[str, str], GraphEdge] = {}
        self._lock = threading.Lock()

        self._load()
        logger.info(f"GraphRAG initialized: {self.path}")

    def _db_path(self, name: str) -> Path:
        return Path(self.path) / name

    def _load(self):
        """Load the graph from disk."""
        nodes_file = self._db_path("nodes.json")
        edges_file = self._db_path("edges.json")

        try:
            if nodes_file.exists():
                data = json.loads(nodes_file.read_text(encoding="utf-8"))
                for n in data:
                    self._nodes[n["id"]] = GraphNode(**n)
        except Exception as e:
            logger.warning(f"Failed to load graph nodes: {e}")

        try:
            if edges_file.exists():
                data = json.loads(edges_file.read_text(encoding="utf-8"))
                for e in data:
                    key = (e["source"], e["target"])
                    self._edges[key] = GraphEdge(**e)
        except Exception as e:
            logger.warning(f"Failed to load graph edges: {e}")

    def _save(self):
        """Save the graph to disk."""
        try:
            nodes_data = [{k: v for k, v in n.__dict__.items()} for n in self._nodes.values()]
            self._db_path("nodes.json").write_text(
                json.dumps(nodes_data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed to save nodes: {e}")

        try:
            edges_data = [{k: v for k, v in e.__dict__.items()} for e in self._edges.values()]
            self._db_path("edges.json").write_text(
                json.dumps(edges_data, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"Failed to save edges: {e}")

    # ── Document Processing ──

    def add_document(self, doc_id: str, text: str) -> int:
        """
        Extract entities and relationships from a document.

        Args:
            doc_id: Document identifier
            text: Document text content

        Returns:
            Number of entities extracted
        """
        entities = _extract_entities(text)
        if not entities:
            return 0

        with self._lock:
            # Add nodes
            for name, etype in entities:
                node_id = name.lower().replace(" ", "_")
                now = time.time()

                if node_id in self._nodes:
                    node = self._nodes[node_id]
                    node.frequency += 1
                    if doc_id not in node.documents:
                        node.documents.append(doc_id)
                else:
                    self._nodes[node_id] = GraphNode(
                        id=node_id,
                        label=name,
                        type=etype,
                        frequency=1,
                        first_seen=now,
                        documents=[doc_id],
                    )

            # Add edges between co-occurring entities
            unique_names = list(set(e[0] for e in entities))
            for i in range(len(unique_names)):
                for j in range(i + 1, len(unique_names)):
                    src = unique_names[i].lower().replace(" ", "_")
                    tgt = unique_names[j].lower().replace(" ", "_")

                    # Sort for undirected edge
                    key = (min(src, tgt), max(src, tgt))

                    if key in self._edges:
                        edge = self._edges[key]
                        edge.weight += 1.0
                        if doc_id not in edge.documents:
                            edge.documents.append(doc_id)
                    else:
                        self._edges[key] = GraphEdge(
                            source=key[0],
                            target=key[1],
                            weight=1.0,
                            documents=[doc_id],
                        )

            self._save()

        return len(unique_names)

    def add_text_batch(self, doc_id_prefix: str, chunks: list[str]) -> int:
        """Process multiple text chunks from the same document."""
        total = 0
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id_prefix}_chunk_{i}"
            total += self.add_document(chunk_id, chunk)
        return total

    # ── Search ──

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """
        Search the graph for nodes related to a query.

        Args:
            query: Search text
            max_results: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []

        for node in self._nodes.values():
            score = 0.0

            # Direct label match
            if query_lower in node.label.lower():
                score += 5.0
            elif query_lower in node.id:
                score += 3.0

            # Word overlap
            node_words = set(node.label.lower().split())
            overlap = len(query_words & node_words)
            score += overlap * 2.0

            # Frequency bonus
            score += node.frequency * 0.1

            if score > 0:
                scored.append((score, node))

        scored.sort(key=lambda x: -x[0])

        results = []
        for score, node in scored[:max_results]:
            results.append(SearchResult(
                node=node,
                path=[node.label],
                score=score,
            ))

        return results

    def get_related_concepts(
        self,
        concept: str,
        depth: int = 1,
        min_weight: float = 0.5,
    ) -> list[tuple[str, float]]:
        """
        Find concepts related to a given concept via graph traversal.

        Args:
            concept: The concept to start from
            depth: How many hops to traverse
            min_weight: Minimum edge weight filter

        Returns:
            List of (related_concept_label, combined_weight) tuples
        """
        concept_id = concept.lower().replace(" ", "_")
        if concept_id not in self._nodes:
            return []

        visited = {concept_id}
        related = []
        queue = [(concept_id, 0, 1.0)]

        while queue:
            current_id, current_depth, current_weight = queue.pop(0)

            if current_depth >= depth:
                continue

            # Find all edges involving this node
            for (src, tgt), edge in self._edges.items():
                if edge.weight < min_weight:
                    continue

                neighbor = None
                if src == current_id:
                    neighbor = tgt
                elif tgt == current_id:
                    neighbor = src

                if neighbor and neighbor not in visited:
                    visited.add(neighbor)
                    if neighbor in self._nodes:
                        combined = current_weight * edge.weight
                        related.append((self._nodes[neighbor].label, combined))
                        queue.append((neighbor, current_depth + 1, combined))

        related.sort(key=lambda x: -x[1])
        return related[:10]

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a specific node by ID."""
        return self._nodes.get(node_id)

    def get_neighbors(self, node_id: str) -> list[tuple[GraphNode, GraphEdge]]:
        """Get all neighbors of a node with their connecting edges."""
        neighbors = []
        for (src, tgt), edge in self._edges.items():
            if src == node_id and tgt in self._nodes:
                neighbors.append((self._nodes[tgt], edge))
            elif tgt == node_id and src in self._nodes:
                neighbors.append((self._nodes[src], edge))
        return sorted(neighbors, key=lambda x: -x[1].weight)

    # ── Statistics ──

    def get_stats(self) -> dict:
        """Get graph statistics."""
        with self._lock:
            return {
                "nodes": len(self._nodes),
                "edges": len(self._edges),
                "node_types": dict(Counter(n.type for n in self._nodes.values())),
                "avg_edge_weight": round(
                    sum(e.weight for e in self._edges.values()) / max(len(self._edges), 1), 2
                ),
                "path": self.path,
            }

    def clear(self) -> int:
        """Clear all graph data. Returns total nodes + edges removed."""
        with self._lock:
            count = len(self._nodes) + len(self._edges)
            self._nodes.clear()
            self._edges.clear()
            self._save()
            return count
