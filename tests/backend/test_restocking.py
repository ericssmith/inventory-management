"""
Tests for restocking API endpoints (recommendations and order submission).
"""
import pytest


class TestRestockingRecommendations:
    """Test suite for the restocking recommendations endpoint."""

    def test_get_recommendations_success(self, client):
        """Test getting recommendations for a reasonable budget."""
        response = client.get("/api/restocking/recommendations?budget=50000")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        assert "item_sku" in first
        assert "item_name" in first
        assert "category" in first
        assert "warehouse" in first
        assert "unit_cost" in first
        assert "current_demand" in first
        assert "forecasted_demand" in first
        assert "shortfall" in first
        assert "trend" in first
        assert "recommended_quantity" in first
        assert "line_cost" in first
        assert "lead_time_days" in first

    def test_recommendations_respect_budget(self, client):
        """Test that total recommended cost never exceeds the given budget."""
        response = client.get("/api/restocking/recommendations?budget=5000")
        assert response.status_code == 200

        data = response.json()
        total_cost = sum(item["line_cost"] for item in data)
        assert total_cost <= 5000 + 0.01

    def test_recommended_quantity_never_exceeds_shortfall(self, client):
        """Test that recommended_quantity never exceeds the demand shortfall."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        for item in data:
            assert item["recommended_quantity"] <= item["shortfall"]
            assert item["recommended_quantity"] > 0

    def test_recommendations_only_include_shortfall_items(self, client):
        """Test that every recommendation has forecasted_demand > current_demand."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        for item in data:
            assert item["forecasted_demand"] > item["current_demand"]

    def test_zero_budget_returns_empty(self, client):
        """Test that a zero budget returns no recommendations, not an error."""
        response = client.get("/api/restocking/recommendations?budget=0")
        assert response.status_code == 200

        data = response.json()
        assert data == []

    def test_larger_budget_yields_more_or_equal_recommendations(self, client):
        """Test that a larger budget never yields fewer recommended items."""
        small_response = client.get("/api/restocking/recommendations?budget=500")
        large_response = client.get("/api/restocking/recommendations?budget=100000")

        small_data = small_response.json()
        large_data = large_response.json()

        assert len(large_data) >= len(small_data)

    def test_recommendations_filtered_by_warehouse(self, client):
        """Test filtering recommendations by warehouse."""
        response = client.get("/api/restocking/recommendations?budget=100000&warehouse=Tokyo")
        assert response.status_code == 200

        data = response.json()
        for item in data:
            assert item["warehouse"] == "Tokyo"

    def test_recommendations_filtered_by_category(self, client):
        """Test filtering recommendations by category."""
        response = client.get("/api/restocking/recommendations?budget=100000&category=Sensors")
        assert response.status_code == 200

        data = response.json()
        for item in data:
            assert item["category"].lower() == "sensors"

    def test_recommendations_prioritize_increasing_trend(self, client):
        """Test that increasing-trend items appear before non-increasing items."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        trends = [item["trend"] for item in data]
        if "increasing" in trends and any(t != "increasing" for t in trends):
            last_increasing_index = max(i for i, t in enumerate(trends) if t == "increasing")
            first_non_increasing_index = min(i for i, t in enumerate(trends) if t != "increasing")
            assert last_increasing_index < first_non_increasing_index


class TestRestockingOrders:
    """Test suite for creating and listing restocking orders."""

    def test_create_restock_order_success(self, client):
        """Test placing a restock order with a sufficient budget."""
        response = client.post("/api/restocking/orders", json={"budget": 20000})
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert "order_number" in data
        assert data["order_number"].startswith("RSK-")
        assert isinstance(data["items"], list)
        assert len(data["items"]) > 0
        assert data["total_cost"] <= data["budget"] + 0.01
        assert data["max_lead_time_days"] > 0

    def test_create_restock_order_expected_delivery_after_order_date(self, client):
        """Test that expected_delivery is after order_date."""
        response = client.post("/api/restocking/orders", json={"budget": 20000})
        data = response.json()

        assert data["expected_delivery"] > data["order_date"]

    def test_create_restock_order_insufficient_budget_returns_400(self, client):
        """Test that a budget too small to afford anything returns 400."""
        response = client.post("/api/restocking/orders", json={"budget": 0.01})
        assert response.status_code == 400

        data = response.json()
        assert "detail" in data

    def test_create_restock_order_with_filters(self, client):
        """Test placing a restock order scoped to a warehouse."""
        response = client.post(
            "/api/restocking/orders",
            json={"budget": 50000, "warehouse": "London"}
        )
        assert response.status_code == 201

        data = response.json()
        assert data["warehouse"] == "London"
        for item in data["items"]:
            assert "sku" in item
            assert "quantity" in item
            assert "unit_cost" in item
            assert "line_cost" in item
            assert "lead_time_days" in item

    def test_get_restock_orders_includes_created_order(self, client):
        """Test that a newly created restock order appears in the list."""
        create_response = client.post("/api/restocking/orders", json={"budget": 15000})
        assert create_response.status_code == 201
        created_order_number = create_response.json()["order_number"]

        list_response = client.get("/api/restocking/orders")
        assert list_response.status_code == 200

        data = list_response.json()
        assert isinstance(data, list)
        order_numbers = [order["order_number"] for order in data]
        assert created_order_number in order_numbers
