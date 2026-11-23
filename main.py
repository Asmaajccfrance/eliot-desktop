import sys


def selftest() -> int:
    from eliot.config import Settings, data_dir
    from eliot.llm.engine import LLMEngine
    out = data_dir() / "autotest.txt"
    try:
        reply = LLMEngine(Settings.load()).chat([{"role": "user", "content": "Réponds uniquement : prêt"}])
        out.write_text(f"OK : {reply}", encoding="utf-8")
        return 0
    except Exception as exc:
        out.write_text(f"ECHEC : {exc}", encoding="utf-8")
        return 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from eliot.app import run
    run()
