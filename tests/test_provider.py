import pytest
import httpx

from auditor.providers import MockProvider, OpenAICompatibleProvider, ProviderError


def test_mock_provider_returns_configured_response_and_records_call() -> None:
    provider = MockProvider({"decompose": '{"claims": []}'})

    assert provider.complete("decompose") == '{"claims": []}'
    assert provider.calls == ["decompose"]


def test_mock_provider_uses_default_response_for_unknown_prompt() -> None:
    provider = MockProvider(default_response="fallback")

    assert provider.complete("unknown") == "fallback"


@pytest.mark.parametrize("prompt", ["", "   ", None])
def test_mock_provider_rejects_empty_prompt(prompt: str | None) -> None:
    provider = MockProvider()

    with pytest.raises(ValueError, match="non-empty"):
        provider.complete(prompt)  # type: ignore[arg-type]


def test_openai_compatible_provider_posts_chat_completion_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url == "https://example.test/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok":true}'}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(
        api_key="secret-key",
        base_url="https://example.test/v1",
        model="demo-model",
        client=client,
    )

    assert provider.complete("prompt") == '{"ok":true}'
    payload = json_loads(requests[0].content)
    assert payload == {
        "model": "demo-model",
        "messages": [{"role": "user", "content": "prompt"}],
    }
    client.close()


def test_openai_compatible_provider_hides_key_in_http_errors() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, text="invalid secret-key")
        )
    )
    provider = OpenAICompatibleProvider(
        api_key="secret-key", base_url="https://example.test/v1", client=client
    )

    with pytest.raises(ProviderError, match="HTTP 401") as error:
        provider.complete("prompt")
    assert "secret-key" not in str(error.value)
    assert "API Key" in str(error.value)
    client.close()


def test_openai_compatible_provider_includes_safe_provider_error_detail() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                404,
                json={"error": {"message": "model demo-model was not found"}},
            )
        )
    )
    provider = OpenAICompatibleProvider(
        api_key="private-token", base_url="https://example.test/v1", client=client
    )

    with pytest.raises(ProviderError, match="model demo-model was not found"):
        provider.complete("prompt")
    client.close()


def test_openai_compatible_provider_redacts_key_echoed_by_provider() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                401,
                json={"error": {"message": "invalid api key private-token"}},
            )
        )
    )
    provider = OpenAICompatibleProvider(
        api_key="private-token", base_url="https://example.test/v1", client=client
    )

    with pytest.raises(ProviderError) as error:
        provider.complete("prompt")
    assert "private-token" not in str(error.value)
    client.close()


def test_openai_compatible_provider_accepts_text_content_parts() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": [
                                    {"type": "text", "text": "part-1"},
                                    {"type": "text", "text": "part-2"},
                                ]
                            }
                        }
                    ]
                },
            )
        )
    )
    provider = OpenAICompatibleProvider(
        api_key="secret-key", base_url="https://example.test/v1", client=client
    )

    assert provider.complete("prompt") == "part-1part-2"
    client.close()


def test_openai_compatible_provider_rejects_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAICompatibleProvider()


@pytest.mark.parametrize(
    "base_url",
    [
        "http://remote.example/v1",
        "not-a-url",
        "https://user:pass@example.test/v1",
        "https://example.test/v1?token=secret",
    ],
)
def test_openai_compatible_provider_rejects_unsafe_base_urls(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        OpenAICompatibleProvider(api_key="secret-key", base_url=base_url)


def test_openai_compatible_provider_allows_local_http_service() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": "ok"}}]}
            )
        )
    )
    provider = OpenAICompatibleProvider(
        api_key="secret-key", base_url="http://127.0.0.1:11434/v1", client=client
    )

    assert provider.complete("prompt") == "ok"
    client.close()


def json_loads(payload: bytes) -> dict[str, object]:
    import json

    return json.loads(payload)
