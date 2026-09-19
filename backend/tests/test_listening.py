from tests.conftest import create_test_song


def test_record_play_event(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    song = create_test_song(db, test_user.id, "Play Me")
    song_id = song.id
    db.close()

    response = test_client.post("/api/listening/event", headers=auth_headers, json={
        "song_id": song_id,
        "event_type": "play",
        "duration_listened": 30.0
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["play_count"] == 1


def test_record_skip_event(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    song = create_test_song(db, test_user.id, "Skip Me")
    song_id = song.id
    db.close()

    response = test_client.post("/api/listening/event", headers=auth_headers, json={
        "song_id": song_id,
        "event_type": "skip",
        "duration_listened": 5.0
    })
    assert response.status_code == 200
    assert response.json()["skip_count"] == 1


def test_record_save_event(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    song = create_test_song(db, test_user.id, "Save Me")
    song_id = song.id
    db.close()

    response = test_client.post("/api/listening/event", headers=auth_headers, json={
        "song_id": song_id,
        "event_type": "save",
        "duration_listened": 0
    })
    assert response.status_code == 200
    assert response.json()["saved"] is True


def test_record_unsave_event(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    song = create_test_song(db, test_user.id, "Unsave Me")
    song_id = song.id
    db.close()

    # Save first
    test_client.post("/api/listening/event", headers=auth_headers, json={
        "song_id": song_id, "event_type": "save", "duration_listened": 0
    })
    # Then unsave
    response = test_client.post("/api/listening/event", headers=auth_headers, json={
        "song_id": song_id, "event_type": "unsave", "duration_listened": 0
    })
    assert response.status_code == 200
    assert response.json()["saved"] is False


def test_listening_history(test_client, test_user, auth_headers, test_db):
    from tests.conftest import TestSessionLocal
    db = TestSessionLocal()
    song = create_test_song(db, test_user.id, "History Song")
    song_id = song.id
    db.close()

    test_client.post("/api/listening/event", headers=auth_headers, json={
        "song_id": song_id, "event_type": "play", "duration_listened": 30.0
    })

    response = test_client.get("/api/listening/history", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["event_type"] == "play"


def test_listening_event_nonexistent_song(test_client, test_user, auth_headers):
    response = test_client.post("/api/listening/event", headers=auth_headers, json={
        "song_id": 99999,
        "event_type": "play",
        "duration_listened": 10.0
    })
    assert response.status_code == 404


def test_listening_requires_auth(test_client):
    response = test_client.get("/api/listening/history")
    assert response.status_code in (401, 403)
