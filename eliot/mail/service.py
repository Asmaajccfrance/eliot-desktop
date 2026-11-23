import json

from .accounts import GmailAccount, MailError, OutlookAccount

REPLY_SYSTEM = """Tu es ELIOT et tu prépares des réponses aux e-mails de {user}.
Pour chaque e-mail, décide s'il mérite une réponse (pas les newsletters, publicités, notifications automatiques).
Rédige les réponses en français (ou dans la langue de l'e-mail), polies, concises, prêtes à envoyer, signées « {user} ».
N'invente aucun engagement, date ou chiffre : laisse [à compléter] si une information manque.
Consignes supplémentaires : {instructions}
Réponds UNIQUEMENT en JSON : {{"replies": [{{"index": 1, "needs_reply": true, "reply": "..."}}]}}"""


class MailService:
    def __init__(self, settings):
        self.settings = settings
        self.last = []
        self.drafts = {}

    def accounts(self, which: str = "") -> list:
        which = (which or "").lower()
        accounts = []
        if self.settings.outlook_enabled and which in ("", "outlook"):
            accounts.append(OutlookAccount())
        if self.settings.gmail_address and which in ("", "gmail"):
            accounts.append(GmailAccount(self.settings.gmail_address))
        if not accounts:
            raise MailError("Aucune messagerie configurée. Active Outlook ou Gmail dans Paramètres > Messagerie.")
        return accounts

    def account_for(self, mail):
        return next(a for a in self.accounts() if a.name.lower() == mail.account)

    def check(self, which: str = "", limit: int = 10) -> list:
        mails, errors = [], []
        for account in self.accounts(which):
            try:
                mails += account.unread(limit)
            except MailError as exc:
                errors.append(f"{account.name} : {exc}")
        if errors and not mails:
            raise MailError(" ".join(errors))
        self.last = sorted(mails, key=lambda m: m.date, reverse=True)[:limit]
        self.drafts = {}
        self.errors = errors
        return self.last

    def get(self, index: int):
        if not self.last:
            raise MailError("Consulte d'abord tes e-mails (« consulte mes nouveaux e-mails »).")
        if not 1 <= index <= len(self.last):
            raise MailError(f"Il n'y a que {len(self.last)} e-mails dans la liste.")
        return self.last[index - 1]

    def prepare(self, llm, instructions: str = "", limit: int = 10) -> dict:
        if not self.last:
            self.check(limit=limit)
        if not self.last:
            return {}
        if llm.is_demo:
            raise MailError("La préparation des réponses nécessite Claude (désactive le mode démonstration).")
        blocks = [f"E-mail {i} — de {m.sender} <{m.sender_addr}> — sujet : {m.subject}\n{m.body[:2500]}"
                  for i, m in enumerate(self.last, 1)]
        system = REPLY_SYSTEM.format(user=self.settings.user_name or "l'utilisateur", instructions=instructions or "aucune")
        data = llm.complete_json("\n\n---\n\n".join(blocks), system, max_tokens=3000)
        self.drafts = {}
        for item in data.get("replies", []):
            try:
                idx = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            if item.get("needs_reply") and item.get("reply") and 1 <= idx <= len(self.last):
                self.drafts[idx] = str(item["reply"]).strip()
        return self.drafts

    def send(self, index: int) -> str:
        mail = self.get(index)
        if index not in self.drafts:
            raise MailError(f"Aucune réponse préparée pour l'e-mail n°{index}.")
        self.account_for(mail).send_reply(mail, self.drafts.pop(index))
        return f"Réponse envoyée à {mail.sender} ({mail.subject})."

    def save_drafts(self) -> int:
        count = 0
        for index, text in list(self.drafts.items()):
            mail = self.get(index)
            self.account_for(mail).save_draft(mail, text)
            count += 1
        return count

    @staticmethod
    def dump(drafts: dict) -> str:
        return json.dumps(drafts, ensure_ascii=False)
