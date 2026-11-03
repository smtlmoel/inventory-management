"""
Tests for restocking API endpoints (recommendations, order submission, submitted orders).
"""
import re
from datetime import date, timedelta

import pytest


def get_recommendations(client, budget):
    response = client.get(f"/api/restocking/recommendations?budget={budget}")
    assert response.status_code == 200
    return response.json()


class TestRestockingRecommendations:
    """Test suite for the restocking recommendations endpoint."""

    def test_zero_budget_returns_no_items(self, client):
        """Test that a zero budget recommends nothing."""
        data = get_recommendations(client, 0)
        assert data["items"] == []
        assert data["total_cost"] == 0
        assert data["budget"] == 0

    def test_recommendation_structure(self, client):
        """Test that recommendation items have the expected fields and types."""
        max_budget = get_recommendations(client, 0)["max_budget"]
        data = get_recommendations(client, max_budget)
        assert len(data["items"]) > 0

        for item in data["items"]:
            assert isinstance(item["item_sku"], str)
            assert isinstance(item["item_name"], str)
            assert item["trend"] in ["increasing", "stable", "decreasing"]
            assert isinstance(item["unit_cost"], (int, float))
            assert isinstance(item["shortfall"], int)
            assert isinstance(item["recommended_qty"], int)
            assert isinstance(item["line_cost"], (int, float))
            assert isinstance(item["lead_time_days"], int)

    def test_max_budget_covers_every_shortfall(self, client):
        """Test that the max budget fully funds every shortfall."""
        max_budget = get_recommendations(client, 0)["max_budget"]
        assert max_budget > 0

        data = get_recommendations(client, max_budget)
        assert len(data["items"]) > 0
        for item in data["items"]:
            assert item["recommended_qty"] == item["shortfall"]
        assert abs(data["total_cost"] - max_budget) < 0.01

    def test_total_never_exceeds_budget(self, client):
        """Test that the recommended total stays within the budget."""
        max_budget = get_recommendations(client, 0)["max_budget"]

        for fraction in [0.05, 0.1, 0.25, 0.5, 0.75, 0.99]:
            budget = round(max_budget * fraction, 2)
            data = get_recommendations(client, budget)
            assert data["total_cost"] <= budget + 0.01

    def test_line_cost_calculation(self, client):
        """Test that each line cost equals quantity times unit cost."""
        max_budget = get_recommendations(client, 0)["max_budget"]
        data = get_recommendations(client, max_budget / 2)

        for item in data["items"]:
            assert abs(item["line_cost"] - item["recommended_qty"] * item["unit_cost"]) < 0.01
            assert 0 < item["recommended_qty"] <= item["shortfall"]

    def test_higher_priority_funded_first(self, client):
        """Test that the highest-priority item is funded before lower ones."""
        weights = {"increasing": 3, "stable": 2, "decreasing": 1}
        max_data = get_recommendations(client, get_recommendations(client, 0)["max_budget"])
        ranked = sorted(
            max_data["items"],
            key=lambda i: i["shortfall"] * weights[i["trend"]],
            reverse=True,
        )
        top = ranked[0]

        # Budget that affords only a handful of units of the top item
        data = get_recommendations(client, top["unit_cost"] * 3)
        assert len(data["items"]) >= 1
        assert data["items"][0]["item_sku"] == top["item_sku"]

    def test_larger_budget_never_reduces_total(self, client):
        """Test that total spend is non-decreasing as the budget grows."""
        max_budget = get_recommendations(client, 0)["max_budget"]
        totals = [
            get_recommendations(client, round(max_budget * f, 2))["total_cost"]
            for f in [0.1, 0.3, 0.6, 1.0]
        ]
        assert totals == sorted(totals)

    def test_items_without_shortfall_excluded(self, client):
        """Test that items already covered by stock are not recommended."""
        forecasts = client.get("/api/demand").json()
        covered = {
            f["item_sku"] for f in forecasts
            if f["forecasted_demand"] <= f["current_stock"]
        }
        assert covered, "fixture data should include a fully stocked item"

        max_budget = get_recommendations(client, 0)["max_budget"]
        data = get_recommendations(client, max_budget)
        assert covered.isdisjoint({i["item_sku"] for i in data["items"]})

    def test_negative_budget_rejected(self, client):
        """Test that a negative budget fails validation."""
        response = client.get("/api/restocking/recommendations?budget=-5")
        assert response.status_code == 422


class TestRestockingOrders:
    """Test suite for submitting restocking orders."""

    def submit_recommended(self, client, budget_fraction=0.5):
        max_budget = get_recommendations(client, 0)["max_budget"]
        budget = round(max_budget * budget_fraction, 2)
        recs = get_recommendations(client, budget)
        payload = {
            "budget": budget,
            "items": [
                {"item_sku": i["item_sku"], "quantity": i["recommended_qty"]}
                for i in recs["items"]
            ],
        }
        return client.post("/api/restocking/orders", json=payload), recs

    def test_submit_order_success(self, client):
        """Test that a valid order is created with status 201."""
        response, recs = self.submit_recommended(client)
        assert response.status_code == 201

        order = response.json()
        assert order["order_number"].startswith("RST-")
        assert order["status"] == "Submitted"
        assert len(order["items"]) == len(recs["items"])
        assert abs(order["total_cost"] - recs["total_cost"]) < 0.01

    def test_lead_time_is_max_across_items(self, client):
        """Test that order lead time is the longest item lead time."""
        response, recs = self.submit_recommended(client, budget_fraction=1.0)
        order = response.json()

        expected = max(i["lead_time_days"] for i in recs["items"])
        assert len(recs["items"]) > 1
        assert order["lead_time_days"] == expected

    def test_expected_delivery_matches_lead_time(self, client):
        """Test that expected delivery is today plus the lead time."""
        response, _ = self.submit_recommended(client)
        order = response.json()

        expected = date.today() + timedelta(days=order["lead_time_days"])
        assert order["expected_delivery"] == expected.isoformat()
        assert re.match(r"\d{4}-\d{2}-\d{2}T", order["submitted_at"])

    def test_submitted_order_appears_in_list(self, client):
        """Test that a submitted order is returned by the submitted orders endpoint."""
        response, _ = self.submit_recommended(client)
        order = response.json()

        listing = client.get("/api/orders/submitted")
        assert listing.status_code == 200
        ids = [o["id"] for o in listing.json()]
        assert order["id"] in ids

    def test_submitted_orders_empty_initially(self, client):
        """Test that no submitted orders exist before any submission."""
        response = client.get("/api/orders/submitted")
        assert response.status_code == 200
        assert response.json() == []

    def test_submitted_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        first, _ = self.submit_recommended(client, 0.3)
        second, _ = self.submit_recommended(client, 0.6)

        listing = client.get("/api/orders/submitted").json()
        assert [o["id"] for o in listing] == [second.json()["id"], first.json()["id"]]

    def test_submitted_route_not_shadowed_by_order_id(self, client):
        """Test that /orders/submitted is not treated as an order id."""
        response = client.get("/api/orders/submitted")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_reject_over_budget(self, client):
        """Test that an order exceeding the budget is rejected."""
        sku = client.get("/api/demand").json()[0]["item_sku"]
        response = client.post(
            "/api/restocking/orders",
            json={"budget": 1, "items": [{"item_sku": sku, "quantity": 100}]},
        )
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()
        assert client.get("/api/orders/submitted").json() == []

    def test_reject_unknown_sku(self, client):
        """Test that an unknown SKU is rejected."""
        response = client.post(
            "/api/restocking/orders",
            json={"budget": 1000000, "items": [{"item_sku": "NOPE-999", "quantity": 1}]},
        )
        assert response.status_code == 400
        assert "unknown" in response.json()["detail"].lower()

    def test_reject_empty_items(self, client):
        """Test that an order with no items is rejected."""
        response = client.post("/api/restocking/orders", json={"budget": 1000, "items": []})
        assert response.status_code == 400

    def test_reject_duplicate_skus(self, client):
        """Test that repeated SKUs in one order are rejected."""
        sku = client.get("/api/demand").json()[0]["item_sku"]
        response = client.post(
            "/api/restocking/orders",
            json={
                "budget": 1000000,
                "items": [
                    {"item_sku": sku, "quantity": 1},
                    {"item_sku": sku, "quantity": 1},
                ],
            },
        )
        assert response.status_code == 400

    @pytest.mark.parametrize("quantity", [0, -3])
    def test_reject_non_positive_quantity(self, client, quantity):
        """Test that zero or negative quantities fail validation."""
        sku = client.get("/api/demand").json()[0]["item_sku"]
        response = client.post(
            "/api/restocking/orders",
            json={"budget": 1000000, "items": [{"item_sku": sku, "quantity": quantity}]},
        )
        assert response.status_code == 422

    def test_reject_negative_budget(self, client):
        """Test that a negative budget fails validation."""
        sku = client.get("/api/demand").json()[0]["item_sku"]
        response = client.post(
            "/api/restocking/orders",
            json={"budget": -1, "items": [{"item_sku": sku, "quantity": 1}]},
        )
        assert response.status_code == 422
