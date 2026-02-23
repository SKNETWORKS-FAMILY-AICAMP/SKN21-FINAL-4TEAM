from app.core.config import settings
k = settings.openai_api_key
print(f"Key length: {len(k)}")
print(f"First 20: {k[:20]}")
print(f"Repr last 5: {repr(k[-5:])}")
