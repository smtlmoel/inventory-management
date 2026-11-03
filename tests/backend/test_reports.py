"""
Tests for reports API endpoints.
"""
import pytest


class TestQuarterlyReports:
    """Test suite for /api/reports/quarterly."""

    def test_returns_quarters_with_required_fields(self, client):
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        required_fields = [
            "quarter",
            "total_orders",
            "total_revenue",
            "delivered_orders",
            "avg_order_value",
            "fulfillment_rate",
        ]
        for row in data:
            for field in required_fields:
                assert field in row, f"Missing field: {field}"

    def test_quarters_sorted_chronologically(self, client):
        data = client.get("/api/reports/quarterly").json()
        keys = [(q["quarter"].split("-")[1], q["quarter"]) for q in data]
        assert keys == sorted(keys)

    def test_totals_match_orders_endpoint(self, client):
        quarterly = client.get("/api/reports/quarterly").json()
        orders = client.get("/api/orders").json()
        assert sum(q["total_orders"] for q in quarterly) == len(orders)

    def test_fulfillment_rate_and_average_are_consistent(self, client):
        for q in client.get("/api/reports/quarterly").json():
            expected_rate = round(q["delivered_orders"] / q["total_orders"] * 100, 1)
            expected_avg = round(q["total_revenue"] / q["total_orders"], 2)
            assert q["fulfillment_rate"] == expected_rate
            assert q["avg_order_value"] == pytest.approx(expected_avg)

    def test_warehouse_filter(self, client):
        orders = client.get("/api/orders?warehouse=Tokyo").json()
        data = client.get("/api/reports/quarterly?warehouse=Tokyo").json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_category_filter(self, client):
        orders = client.get("/api/orders?category=Sensors").json()
        data = client.get("/api/reports/quarterly?category=Sensors").json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_status_filter(self, client):
        orders = client.get("/api/orders?status=Delivered").json()
        data = client.get("/api/reports/quarterly?status=Delivered").json()
        assert sum(q["total_orders"] for q in data) == len(orders)
        assert all(q["fulfillment_rate"] == 100.0 for q in data)

    def test_quarter_filter_limits_result(self, client):
        data = client.get("/api/reports/quarterly?month=Q1-2025").json()
        assert all(q["quarter"] == "Q1-2025" for q in data)

    def test_all_values_behave_like_no_filter(self, client):
        unfiltered = client.get("/api/reports/quarterly").json()
        with_all = client.get(
            "/api/reports/quarterly?warehouse=all&category=all&status=all&month=all"
        ).json()
        assert unfiltered == with_all

    def test_empty_result_returns_empty_list(self, client):
        response = client.get("/api/reports/quarterly?warehouse=Nowhere")
        assert response.status_code == 200
        assert response.json() == []


class TestMonthlyTrends:
    """Test suite for /api/reports/monthly-trends."""

    def test_returns_months_with_required_fields(self, client):
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for row in data:
            for field in ["month", "order_count", "revenue", "delivered_count"]:
                assert field in row, f"Missing field: {field}"

    def test_months_sorted_ascending(self, client):
        months = [m["month"] for m in client.get("/api/reports/monthly-trends").json()]
        assert months == sorted(months)

    def test_totals_match_orders_endpoint(self, client):
        trends = client.get("/api/reports/monthly-trends").json()
        orders = client.get("/api/orders").json()
        assert sum(m["order_count"] for m in trends) == len(orders)
        assert sum(m["revenue"] for m in trends) == pytest.approx(
            sum(o["total_value"] for o in orders)
        )

    def test_warehouse_filter(self, client):
        orders = client.get("/api/orders?warehouse=London").json()
        data = client.get("/api/reports/monthly-trends?warehouse=London").json()
        assert sum(m["order_count"] for m in data) == len(orders)

    def test_status_filter(self, client):
        orders = client.get("/api/orders?status=Backordered").json()
        data = client.get("/api/reports/monthly-trends?status=Backordered").json()
        assert sum(m["order_count"] for m in data) == len(orders)

    def test_direct_month_filter(self, client):
        data = client.get("/api/reports/monthly-trends?month=2025-01").json()
        assert all(m["month"] == "2025-01" for m in data)

    def test_empty_result_returns_empty_list(self, client):
        response = client.get("/api/reports/monthly-trends?category=Nothing")
        assert response.status_code == 200
        assert response.json() == []
