from tests.conftest import create_test_song


def test_list_songs_empty(test_client, test_user, auth_headers):
    response = test_client.get("/api/songs", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_songs_with_data(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    create_test_song(db, test_user.id, "Song One", "Artist A")
    create_test_song(db, test_user.id, "Song Two", "Artist B")
    db.close()

    response = test_client.get("/api/songs", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_songs_with_mood_filter(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    create_test_song(db, test_user.id, "Chill Song", "Artist A")
    s2 = create_test_song(db, test_user.id, "Energetic Song", "Artist B")
    s2.mood = "energetic"
    db.commit()
    db.close()

    response = test_client.get("/api/songs?mood=chill", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Chill Song"


def test_get_song_count(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    create_test_song(db, test_user.id, "Song 1")
    create_test_song(db, test_user.id, "Song 2")
    db.close()

    response = test_client.get("/api/songs/count", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["count"] == 2


def test_get_single_song(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    song = create_test_song(db, test_user.id, "My Song")
    song_id = song.id
    db.close()

    response = test_client.get(f"/api/songs/{song_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "My Song"


def test_get_nonexistent_song(test_client, test_user, auth_headers):
    response = test_client.get("/api/songs/99999", headers=auth_headers)
    assert response.status_code == 404


def test_delete_song(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    song = create_test_song(db, test_user.id, "Delete Me")
    song_id = song.id
    db.close()

    response = test_client.delete(f"/api/songs/{song_id}", headers=auth_headers)
    assert response.status_code == 204

    response = test_client.get(f"/api/songs/{song_id}", headers=auth_headers)
    assert response.status_code == 404


def test_songs_requires_auth(test_client):
    response = test_client.get("/api/songs")
    assert response.status_code in (401, 403)


def test_songs_pagination(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    for i in range(25):
        create_test_song(db, test_user.id, f"Song {i}")
    db.close()

    response = test_client.get("/api/songs?offset=0&limit=10", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 10

    response = test_client.get("/api/songs?offset=20&limit=10", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 5
