import base64
import json

from PySide6.QtGui import QColor, QImage


def picture(tmp_path, name, width, height):
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor("green"))
    path = str(tmp_path / name)
    image.save(path)
    return path


def jpeg_size(data):
    image = QImage()
    image.loadFromData(base64.b64decode(data), "JPG")
    return image.width(), image.height()


def test_a_large_picture_goes_back_small(hou, tmp_path, qt_app):
    from houdinimcp.tools import capture
    path = picture(tmp_path, "view.png", 3840, 2160)
    result = capture._inline({"filepath": path})
    assert [item["path"] for item in result["inline"]] == [path]
    assert jpeg_size(result["inline"][0]["jpeg"]) == (1280, 720)


def test_every_picture_of_a_quad_and_no_more_than_the_limit(hou, tmp_path, qt_app):
    from houdinimcp.tools import capture
    paths = [picture(tmp_path, f"v{i}.png", 200, 100) for i in range(capture.MAX_INLINE + 2)]
    result = capture._inline({"images": [{"filepath": p} for p in paths],
                              "filepath": paths[-1]})
    assert len(result["inline"]) == capture.MAX_INLINE
    assert result["not_inline"] == paths[capture.MAX_INLINE:]
    assert jpeg_size(result["inline"][0]["jpeg"]) == (200, 100)


def test_the_bridge_gives_the_model_the_picture(tmp_path, qt_app):
    from bridge.tools import capture
    path = picture(tmp_path, "v.jpg", 40, 20)
    data = base64.b64encode(open(path, "rb").read()).decode()
    result = {"inline": [{"path": "C:/Temp/v.jpg", "jpeg": data}], "frame": 1}
    images = capture.pictures(result)
    assert "inline" not in result and json.dumps(result)
    content = images[0].to_image_content()
    assert content.mime_type == "image/jpeg"
    assert base64.b64decode(content.data) == open(path, "rb").read()


def test_capture_sends_pictures_before_the_json(monkeypatch, tmp_path, qt_app):
    from bridge.tools import capture
    path = picture(tmp_path, "v.jpg", 40, 20)
    data = base64.b64encode(open(path, "rb").read()).decode()
    monkeypatch.setattr(capture, "call", lambda *a, **k: {
        "inline": [{"path": "X", "jpeg": data}], "window_state": {}})
    out = capture.tool(mode="viewport")
    assert len(out) == 2 and isinstance(out[1], str) and "jpeg" not in out[1]
