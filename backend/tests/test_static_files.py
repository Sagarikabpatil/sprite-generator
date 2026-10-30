def test_generated_directories_are_not_publicly_mounted(isolated_client):
    client, _, folders = isolated_client
    image = folders["GENERATED_FOLDER"] / "private.png"
    image.write_bytes(b"private")

    assert client.get("/generated/private.png").status_code == 404
    assert client.get("/generated_videos/private.mp4").status_code == 404
    assert client.get("/assets").status_code == 401
