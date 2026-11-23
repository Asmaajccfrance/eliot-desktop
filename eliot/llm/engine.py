"""Cerveau d'ELIOT : Claude via la clé Emergent intégrée ou la clé Anthropic de l'utilisateur."""
import asyncio
import json
import re
import uuid
from datetime import datetime

from ..config import EMERGENT_LLM_KEY
from ..secrets_store import ANTHROPIC, get_secret

SYSTEM_PROMPT = """Tu es ELIOT, l'assistant IA personnel de {user} sur son ordinateur Windows, inspiré de Jarvis.
Nous sommes le {date}. Tu réponds toujours en français, avec un ton chaleureux, précis et concis.
Tes réponses peuvent être lues à voix haute : phrases courtes, pas de tableaux, peu de listes, pas de markdown lourd.
Tu sais agir sur le PC (ouvrir/activer des applications autorisées, écrire, raccourcis clavier, recherche web,
lecture de pages, rangement des dossiers autorisés) : l'utilisateur te le demande avec des phrases comme
« ouvre Firefox », « recherche ... », « range le dossier Téléchargements ».
Tu ne prétends jamais avoir effectué une action que tu n'as pas réellement faite.
Tu peux aussi consulter les e-mails Outlook/Gmail configurés et préparer des réponses (« consulte mes e-mails »),
retenir des informations (« retiens que… »), programmer des rappels (« rappelle-moi… ») et analyser un projet de code
(« analyse le projet … »). Pour ces actions, invite l'utilisateur à formuler la commande correspondante."""


class LLMError(Exception):
    pass


def extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise LLMError("Réponse du moteur IA illisible (JSON attendu).")
    try:
        return json.loads(match.group(0))
    except ValueError as exc:
        raise LLMError("Réponse du moteur IA illisible (JSON invalide).") from exc


def clean_messages(messages: list) -> list:
    out = []
    for msg in messages:
        role = "assistant" if msg.get("role") == "assistant" else "user"
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n\n" + content
        else:
            out.append({"role": role, "content": content})
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


def demo_reply(text: str) -> str:
    return ("Je suis en mode démonstration : je peux exécuter les commandes (ouvrir une application, rechercher "
            "sur Internet, ranger un dossier…) mais pas tenir une vraie conversation. Active Claude dans les "
            f"Paramètres pour que je te réponde intelligemment. Tu m'as dit : « {text[:200]} ».")


class LLMEngine:
    def __init__(self, settings, secret_getter=get_secret, memory=None):
        self.settings = settings
        self.secret = secret_getter
        self.memory = memory

    @property
    def is_demo(self) -> bool:
        return self.settings.ai_provider == "demo"

    def system_prompt(self) -> str:
        prompt = SYSTEM_PROMPT.format(user=self.settings.user_name or "l'utilisateur",
                                      date=datetime.now().strftime("%d/%m/%Y %H:%M"))
        memories = self.memory.as_prompt() if self.memory is not None else ""
        return prompt + ("\n\n" + memories if memories else "")

    def chat(self, messages: list, system: str = None, on_delta=None, max_tokens: int = 1200) -> str:
        msgs = clean_messages(messages)
        if not msgs:
            raise LLMError("Message vide.")
        system = system or self.system_prompt()
        provider = self.settings.ai_provider
        if provider == "demo":
            text = demo_reply(msgs[-1]["content"])
            if on_delta:
                on_delta(text)
            return text
        if provider == "anthropic":
            return self._anthropic(msgs, system, on_delta, max_tokens)
        return self._emergent(msgs, system, on_delta, max_tokens)

    def complete_json(self, prompt: str, system: str, max_tokens: int = 1500) -> dict:
        return extract_json(self.chat([{"role": "user", "content": prompt}], system=system, max_tokens=max_tokens))

    def _anthropic(self, msgs, system, on_delta, max_tokens) -> str:
        key = self.secret(ANTHROPIC)
        if not key:
            raise LLMError("Aucune clé Anthropic enregistrée. Ouvre Paramètres > Intelligence artificielle.")
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=90)
        out = []
        try:
            with client.messages.stream(model=self.settings.model, max_tokens=max_tokens, system=system,
                                        messages=msgs) as stream:
                for chunk in stream.text_stream:
                    out.append(chunk)
                    if on_delta:
                        on_delta(chunk)
        except anthropic.AuthenticationError as exc:
            raise LLMError("Ta clé Anthropic a été refusée. Vérifie-la dans les Paramètres.") from exc
        except anthropic.RateLimitError as exc:
            raise LLMError("Limite d'utilisation Claude atteinte, réessaie dans un instant.") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("Impossible de joindre Claude : vérifie ta connexion Internet.") from exc
        except anthropic.APIError as exc:
            raise LLMError(f"Erreur Claude : {exc}") from exc
        return "".join(out)

    def _emergent(self, msgs, system, on_delta, max_tokens) -> str:
        try:
            from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage
        except ImportError as exc:
            raise LLMError("Le module emergentintegrations est absent de cette installation.") from exc

        async def run() -> str:
            chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=uuid.uuid4().hex, system_message=system,
                           initial_messages=[{"role": "system", "content": system}] + msgs[:-1])
            chat.with_model("anthropic", self.settings.model).with_params(max_tokens=max_tokens)
            out = []
            async for event in chat.stream_message(UserMessage(text=msgs[-1]["content"])):
                if isinstance(event, TextDelta):
                    out.append(event.content)
                    if on_delta:
                        on_delta(event.content)
                elif isinstance(event, StreamDone):
                    break
            return "".join(out)

        try:
            return asyncio.run(run())
        except Exception as exc:
            message = str(exc)
            if "budget" in message.lower() or "balance" in message.lower():
                raise LLMError("Le crédit de la clé Emergent est épuisé. Recharge-le ou utilise ta clé Anthropic.") from exc
            raise LLMError(f"Erreur du moteur IA : {message[:300]}") from exc
