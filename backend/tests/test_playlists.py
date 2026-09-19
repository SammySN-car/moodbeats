def test_list_playlists_empty(test_client, test_user, auth_headers):
    response = test_client.get("/api/playlists", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_playlists_requires_auth(test_client):
    response = test_client.get("/api/playlists")
    assert response.status_code in (401, 403)
