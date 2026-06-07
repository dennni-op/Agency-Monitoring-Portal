import os
import time
from datetime import datetime

from dotenv import load_dotenv

from app.client_registry import get_client
from app.database import get_session_factory
from app.models import ApiCheck, init_db

load_dotenv()


def classify_result(latency_ms: float, response_text: str, max_latency_ms: int):
    if not response_text or not response_text.strip():
        return False, "empty response"
    if latency_ms > max_latency_ms:
        return False, f"latency exceeded threshold ({latency_ms:.0f}ms > {max_latency_ms}ms)"
    return True, None


def save_check(session_factory, provider, model, latency, success, error=None):
    db = session_factory()
    try:
        check = ApiCheck(
            provider=provider,
            model=model,
            latency_ms=latency,
            success=success,
            error_message=error,
        )
        db.add(check)
        db.commit()
    finally:
        db.close()


def _check_openai(model: str):
    import openai

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    start = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say OK"}],
    )
    latency = (time.time() - start) * 1000
    text = response.choices[0].message.content or ""
    return latency, text


def _check_google(model: str):
    from google import genai

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    start = time.time()
    response = client.models.generate_content(model=model, contents='Say "OK"')
    latency = (time.time() - start) * 1000
    text = getattr(response, "text", None) or ""
    return latency, text


def _check_anthropic(model: str):
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    start = time.time()
    response = client.messages.create(
        model=model,
        max_tokens=5,
        messages=[{"role": "user", "content": "Say OK"}],
    )
    latency = (time.time() - start) * 1000
    text = " ".join(
        block.text for block in response.content if hasattr(block, "text") and block.text
    )
    return latency, text


def run_client_monitor(client_slug: str):
    client = get_client(client_slug)
    session_factory, engine = get_session_factory(client.db_env_var)
    init_db(engine)

    provider_handlers = {
        "openai": _check_openai,
        "google": _check_google,
        "anthropic": _check_anthropic,
    }

    print("=" * 60)
    print(f"Running checks for client: {client.name} ({client.slug})")
    print(f"Time: {datetime.utcnow().isoformat()} UTC")
    print("=" * 60)

    for provider in client.providers:
        handler = provider_handlers.get(provider.provider)
        if handler is None:
            save_check(session_factory, provider.provider, provider.model, None, False, "unsupported provider")
            print(f"Skipped unsupported provider: {provider.provider}")
            continue

        try:
            latency, response_text = handler(provider.model)
            is_success, error = classify_result(latency, response_text, client.max_success_latency_ms)
            if is_success:
                save_check(session_factory, provider.provider, provider.model, latency, True)
                print(f"SUCCESS {provider.provider}/{provider.model}: {latency:.0f}ms")
            else:
                save_check(session_factory, provider.provider, provider.model, None, False, error)
                print(f"FAILED {provider.provider}/{provider.model}: {error}")
        except Exception as e:
            save_check(session_factory, provider.provider, provider.model, None, False, str(e))
            print(f"FAILED {provider.provider}/{provider.model}: {e}")


if __name__ == "__main__":
    slug = os.getenv("CLIENT_SLUG", "acme")
    run_client_monitor(slug)
