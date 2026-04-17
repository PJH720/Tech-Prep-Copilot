import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
API_KEY = os.getenv("VITE_GOOGLE_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")

print(f"API 키 확인: {'설정됨 (' + API_KEY[:8] + '...)' if API_KEY else '❌ 키 없음 — .env 확인 필요'}")

client = genai.Client(api_key=API_KEY)

models_to_try = [
    "gemini-2.0-flash-lite",   # 현재 백엔드 설정
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]

for model_name in models_to_try:
    print(f"\n[{model_name}] 호출 시도 중...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents="Reply with just: OK"
        )
        print(f"  성공: {response.text.strip()}")
    except Exception as e:
        print(f"  실패: {str(e)[:200]}")
