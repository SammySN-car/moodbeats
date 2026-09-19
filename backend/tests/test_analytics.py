def test_stats_empty(test_client, test_user, auth_headers):
    response = test_client.get("/api/analytics/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_songs"] == 0


def test_mood_distribution_empty(test_client, test_user, auth_headers):
    response = test_client.get("/api/analytics/mood-distribution", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_analytics_requires_auth(test_client):
    response = test_client.get("/api/analytics/stats")
    assert response.status_code in (401, 403)
