"""Tests for Graph Service and API"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.graph import EdgeType, GraphFilter
from backend.services.graph_service import (
    CATEGORY_COLORS,
    LAYER_COLORS,
    GraphService,
)


@pytest.fixture
def mock_notes():
    """Sample notes for testing"""
    return [
        {
            "id": "note-1",
            "content": "This is a verified fact about the project",
            "layer": "verified_fact",
            "category": "event",
            "confidence": 0.9,
            "created_at": "2025-12-28T10:00:00Z",
        },
        {
            "id": "note-2",
            "content": "Another fact in the same category",
            "layer": "verified_fact",
            "category": "event",
            "confidence": 0.8,
            "created_at": "2025-12-28T11:00:00Z",
        },
        {
            "id": "note-3",
            "content": "An event log entry",
            "layer": "event_log",
            "category": "person",
            "confidence": 0.7,
            "created_at": "2025-12-28T12:00:00Z",
        },
        {
            "id": "note-4",
            "content": "Identity schema entry",
            "layer": "identity_schema",
            "category": None,
            "confidence": 1.0,
            "created_at": "2025-12-28T09:00:00Z",
        },
    ]


@pytest.fixture
def graph_service():
    """Create GraphService with mocked search service"""
    mock_search = MagicMock()
    return GraphService(search_service=mock_search)


class TestGraphService:
    """Tests for GraphService"""

    def test_build_graph_empty(self, graph_service):
        """Test building graph with no notes"""
        graph_service._search_service.list_notes.return_value = []

        result = graph_service.build_graph()

        assert result.node_count == 0
        assert result.edge_count == 0
        assert result.nodes == []
        assert result.edges == []

    def test_build_graph_with_notes(self, graph_service, mock_notes):
        """Test building graph with notes"""
        graph_service._search_service.list_notes.return_value = mock_notes

        result = graph_service.build_graph(GraphFilter(limit=100))

        # Should have nodes
        assert result.node_count > 0
        assert len(result.nodes) > 0

        # Should have edges (time sequence + shared category)
        assert result.edge_count > 0

        # Check layer stats
        assert "verified_fact" in result.layer_stats
        assert "event_log" in result.layer_stats

    def test_build_nodes(self, graph_service, mock_notes):
        """Test node building"""
        nodes = graph_service._build_nodes(mock_notes)

        assert len(nodes) == 4

        # Check first node
        node1 = next(n for n in nodes if n.id == "note-1")
        assert node1.layer == "verified_fact"
        assert node1.category == "event"
        assert node1.confidence == 0.9
        assert node1.color == LAYER_COLORS["verified_fact"]
        assert 8 <= node1.size <= 20

        # Check identity schema node
        node4 = next(n for n in nodes if n.id == "note-4")
        assert node4.layer == "identity_schema"
        assert node4.color == LAYER_COLORS["identity_schema"]

    def test_build_edges_time_sequence(self, graph_service, mock_notes):
        """Test time sequence edge building"""
        edges = graph_service._build_edges(
            mock_notes, [EdgeType.TIME_SEQUENCE]
        )

        # Should have n-1 time sequence edges for n notes
        time_edges = [e for e in edges if e.edge_type == EdgeType.TIME_SEQUENCE]
        assert len(time_edges) == len(mock_notes) - 1

        # Check edge properties
        for edge in time_edges:
            assert edge.dashed is True
            assert edge.weight == 0.3

    def test_build_edges_shared_category(self, graph_service, mock_notes):
        """Test shared category edge building"""
        edges = graph_service._build_edges(
            mock_notes, [EdgeType.SHARED_CATEGORY]
        )

        # Should have edges between notes with same category
        category_edges = [e for e in edges if e.edge_type == EdgeType.SHARED_CATEGORY]
        assert len(category_edges) >= 1  # At least one edge between event category notes

        # Check edge properties
        for edge in category_edges:
            assert edge.dashed is False
            assert edge.weight == 0.7

    def test_build_edges_all_types(self, graph_service, mock_notes):
        """Test building edges with all types"""
        edges = graph_service._build_edges(
            mock_notes,
            [EdgeType.TIME_SEQUENCE, EdgeType.SHARED_CATEGORY, EdgeType.SHARED_LAYER]
        )

        # Should have multiple edge types
        edge_types = set(e.edge_type for e in edges)
        assert EdgeType.TIME_SEQUENCE in edge_types
        assert EdgeType.SHARED_CATEGORY in edge_types

    def test_filter_by_layers(self, graph_service, mock_notes):
        """Test filtering by layers"""
        # Only return verified_fact notes
        graph_service._search_service.list_notes.side_effect = lambda layer, limit: [
            n for n in mock_notes if n["layer"] == layer
        ]

        result = graph_service.build_graph(
            GraphFilter(layers=["verified_fact"], limit=100)
        )

        # Should only have verified_fact nodes
        for node in result.nodes:
            assert node.layer == "verified_fact"

    def test_filter_by_categories(self, graph_service, mock_notes):
        """Test filtering by categories"""
        graph_service._search_service.list_notes.return_value = mock_notes

        result = graph_service.build_graph(
            GraphFilter(categories=["event"], limit=100)
        )

        # Should only have event category nodes
        for node in result.nodes:
            assert node.category == "event" or node.category is None

    def test_node_label_truncation(self, graph_service):
        """Test that long content is truncated for labels"""
        long_note = {
            "id": "long-note",
            "content": "A" * 100,  # 100 character content
            "layer": "verified_fact",
            "category": "event",
            "confidence": 0.8,
            "created_at": "2025-12-28T10:00:00Z",
        }

        nodes = graph_service._build_nodes([long_note])
        assert len(nodes) == 1
        assert nodes[0].label.endswith("...")
        assert len(nodes[0].label) <= 53  # 50 + "..."

    def test_node_size_varies_with_confidence(self, graph_service):
        """Test that node size varies with confidence"""
        notes = [
            {"id": "low", "content": "Low conf", "layer": "verified_fact",
             "confidence": 0.1, "created_at": "2025-12-28T10:00:00Z"},
            {"id": "high", "content": "High conf", "layer": "verified_fact",
             "confidence": 1.0, "created_at": "2025-12-28T11:00:00Z"},
        ]

        nodes = graph_service._build_nodes(notes)
        low_node = next(n for n in nodes if n.id == "low")
        high_node = next(n for n in nodes if n.id == "high")

        assert high_node.size > low_node.size


class TestGraphAPI:
    """Tests for Graph API endpoints"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    @patch("backend.api.graph.get_graph_service")
    def test_get_graph(self, mock_get_service, client, mock_notes):
        """Test GET /api/v1/graph endpoint"""
        mock_service = MagicMock()
        mock_service.build_graph.return_value = MagicMock(
            nodes=[],
            edges=[],
            node_count=0,
            edge_count=0,
            layer_stats={},
            category_stats={},
            model_dump=lambda: {
                "nodes": [],
                "edges": [],
                "node_count": 0,
                "edge_count": 0,
                "layer_stats": {},
                "category_stats": {},
            }
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/graph")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "node_count" in data

    @patch("backend.api.graph.get_graph_service")
    def test_get_graph_with_filters(self, mock_get_service, client):
        """Test GET /api/v1/graph with filter params"""
        mock_service = MagicMock()
        mock_service.build_graph.return_value = MagicMock(
            nodes=[],
            edges=[],
            node_count=0,
            edge_count=0,
            layer_stats={},
            category_stats={},
            model_dump=lambda: {
                "nodes": [],
                "edges": [],
                "node_count": 0,
                "edge_count": 0,
                "layer_stats": {},
                "category_stats": {},
            }
        )
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/graph",
            params={
                "layers": ["verified_fact"],
                "categories": ["event"],
                "limit": 50,
            }
        )

        assert response.status_code == 200
        # Verify filter was passed
        call_args = mock_service.build_graph.call_args[0][0]
        assert "verified_fact" in call_args.layers
        assert "event" in call_args.categories
        assert call_args.limit == 50

    @patch("backend.api.graph.get_graph_service")
    def test_get_graph_stats(self, mock_get_service, client):
        """Test GET /api/v1/graph/stats endpoint"""
        mock_service = MagicMock()
        mock_service.build_graph.return_value = MagicMock(
            node_count=10,
            edge_count=15,
            layer_stats={"verified_fact": 8, "event_log": 2},
            category_stats={"event": 5, "person": 3},
        )
        mock_get_service.return_value = mock_service

        response = client.get("/api/v1/graph/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_nodes"] == 10
        assert data["total_edges"] == 15
        assert "layer_stats" in data
        assert "category_stats" in data


class TestGraphColors:
    """Tests for color constants"""

    def test_layer_colors_defined(self):
        """Test all layers have colors"""
        expected_layers = [
            "identity_schema", "constitution",
            "active_context",
            "event_log", "session",
            "verified_fact", "fact",
            "operational_knowledge",
        ]
        for layer in expected_layers:
            assert layer in LAYER_COLORS
            assert LAYER_COLORS[layer].startswith("#")

    def test_category_colors_defined(self):
        """Test all categories have colors"""
        expected_categories = ["person", "place", "event", "item", "routine"]
        for cat in expected_categories:
            assert cat in CATEGORY_COLORS
            assert CATEGORY_COLORS[cat].startswith("#")
