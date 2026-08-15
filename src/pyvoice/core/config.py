import keyring

SERVICE_NAME = "PyVoiceAI_Gemini"
API_KEY_NAME = "gemini_api_key"

def load_api_key() -> str:
    """Завантажує збережений API ключ із зашифрованого сховища Windows Keyring"""
    try:
        return keyring.get_password(SERVICE_NAME, API_KEY_NAME) or ""
    except Exception:
        return ""

def save_api_key(api_key: str) -> None:
    """Зберігає API ключ у зашифроване сховище Windows Keyring (Credential Manager)"""
    api_key = api_key.strip()
    if api_key:
        try:
            keyring.set_password(SERVICE_NAME, API_KEY_NAME, api_key)
        except Exception:
            pass
