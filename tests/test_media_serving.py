"""st.image·st.download_button이 쓰는 /media 응답이 gzip 미들웨어를 통과하는지 검증.

streamlit 1.59.1 + starlette 1.8 이상 조합은 http.response.start를 누락해
image/*·application/zip 응답이 500이 된다(상장 ZIP 다운로드·미리보기 불가).
"""
import asyncio

import pytest
from streamlit.web.server.starlette.starlette_gzip_middleware import SelectiveGZipMiddleware


def _serve(content_type: str, body: bytes, accept_encoding: bytes) -> list:
    async def media(scope, receive, send):
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"content-type", content_type.encode())]})
        await send({"type": "http.response.body", "body": body})

    sent = []

    async def capture(message):
        sent.append(message)

    scope = {"type": "http", "path": "/media/x", "headers": [(b"accept-encoding", accept_encoding)]}
    asyncio.run(SelectiveGZipMiddleware(media)(scope, None, capture))
    return sent


@pytest.mark.parametrize("content_type", ["image/png", "image/jpeg", "application/zip", "application/pdf"])
@pytest.mark.parametrize("accept_encoding", [b"gzip", b"identity"])
def test_media_response_starts_before_body(content_type, accept_encoding):
    sent = _serve(content_type, b"x" * 2000, accept_encoding)
    assert [m["type"] for m in sent] == ["http.response.start", "http.response.body"]
