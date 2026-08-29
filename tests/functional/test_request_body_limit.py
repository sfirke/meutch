"""Functional tests for the app-wide request body size ceiling.

`MAX_CONTENT_LENGTH` is the only backstop that bounds how many bytes the app will
read off the wire. Gunicorn sets `wsgi.input_terminated`, which means Werkzeug
hands the app an unbounded stream for a chunked request unless this ceiling is
configured.
"""

import io

from flask import request
from werkzeug.test import EnvironBuilder

from app.utils.storage import MAX_ITEM_IMAGE_COUNT, MAX_UPLOAD_FILE_SIZE_BYTES
from config import Config


class TestRequestBodyCeiling:
    """The ceiling bounds hostile bodies without rejecting legitimate uploads."""

    def test_default_clears_the_largest_legitimate_upload(self):
        """A full batch of max-size photos must still fit under the ceiling."""
        largest_upload = MAX_ITEM_IMAGE_COUNT * MAX_UPLOAD_FILE_SIZE_BYTES

        assert Config.MAX_CONTENT_LENGTH >= largest_upload

    def test_oversized_declared_body_is_rejected(self, client, app, monkeypatch):
        """A body whose Content-Length exceeds the ceiling gets a 413."""
        monkeypatch.setitem(app.config, "MAX_CONTENT_LENGTH", 1024)

        response = client.post("/login", data={"email": "a" * 4096})

        assert response.status_code == 413

    def test_body_without_content_length_is_bounded(self, app, monkeypatch):
        """A chunked body, which declares no length, is capped as it is read.

        This is the case the ceiling exists for. `request.content_length` is None,
        so nothing that inspects the header can bound the read, and gunicorn sets
        `wsgi.input_terminated`, which tells Werkzeug the stream is safe to read
        directly. Werkzeug truncates at the ceiling rather than raising, so the
        protection is that the read stops -- a worker cannot be tied up buffering
        an arbitrarily long body.
        """
        ceiling = 1024
        monkeypatch.setitem(app.config, "MAX_CONTENT_LENGTH", ceiling)

        environ = EnvironBuilder(path="/", method="POST").get_environ()
        environ.pop("CONTENT_LENGTH", None)
        environ["wsgi.input"] = io.BytesIO(b"x" * (1024 * 1024))
        environ["wsgi.input_terminated"] = True

        with app.request_context(environ):
            assert request.content_length is None

            assert len(request.get_data()) == ceiling
