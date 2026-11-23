"""Clés API stockées dans le Gestionnaire d'identification Windows (keyring)."""
SERVICE = "ELIOT"
ANTHROPIC = "anthropic_api_key"
OPENAI = "openai_api_key"

_memory: dict = {}


def get_secret(name: str):
    try:
        import keyring
        value = keyring.get_password(SERVICE, name)
        if value:
            return value
    except Exception:
        pass
    return _memory.get(name)


def set_secret(name: str, value: str) -> bool:
    value = (value or "").strip()
    try:
        import keyring
        if value:
            keyring.set_password(SERVICE, name, value)
        else:
            try:
                keyring.delete_password(SERVICE, name)
            except Exception:
                pass
        return True
    except Exception:
        if value:
            _memory[name] = value
        else:
            _memory.pop(name, None)
        return False
