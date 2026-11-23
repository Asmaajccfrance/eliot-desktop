"""Messagerie : Outlook installé (COM) et Gmail (IMAP/SMTP avec mot de passe d'application)."""
import email
import html
import imaplib
import re
import smtplib
import sys
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import default as default_policy
from email.utils import parseaddr, parsedate_to_datetime

from ..secrets_store import get_secret

GMAIL = "gmail_app_password"


class MailError(Exception):
    pass


@dataclass
class Mail:
    account: str
    uid: str
    sender: str
    sender_addr: str
    subject: str
    date: str
    body: str
    message_id: str = ""
    references: str = ""


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", raw)
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def clean_body(text: str) -> str:
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t\r]+", " ", text or "")).strip()[:6000]


class OutlookAccount:
    name = "Outlook"

    def _ns(self):
        if sys.platform != "win32":
            raise MailError("Outlook n'est disponible que sous Windows.")
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            return win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        except Exception as exc:
            raise MailError("Impossible d'ouvrir Outlook. Vérifie qu'Outlook (classique) est installé et configuré.") from exc

    def unread(self, limit: int) -> list:
        ns = self._ns()
        items = ns.GetDefaultFolder(6).Items.Restrict("[UnRead] = True")
        items.Sort("[ReceivedTime]", True)
        out = []
        for item in items:
            if len(out) >= limit:
                break
            try:
                out.append(Mail("outlook", item.EntryID, item.SenderName, item.SenderEmailAddress, item.Subject or "",
                                str(item.ReceivedTime)[:16], clean_body(item.Body)))
            except Exception:
                continue
        return out

    def _reply(self, mail: Mail, text: str):
        item = self._ns().GetItemFromID(mail.uid)
        reply = item.Reply()
        reply.Body = text + "\n\n" + reply.Body
        return reply

    def send_reply(self, mail: Mail, text: str) -> None:
        self._reply(mail, text).Send()

    def save_draft(self, mail: Mail, text: str) -> None:
        self._reply(mail, text).Save()


class GmailAccount:
    name = "Gmail"

    def __init__(self, address: str, password_getter=lambda: get_secret(GMAIL)):
        self.address = address
        self.password_getter = password_getter

    def _password(self) -> str:
        pwd = (self.password_getter() or "").replace(" ", "")
        if not pwd:
            raise MailError("Mot de passe d'application Gmail manquant (Paramètres > Messagerie).")
        return pwd

    def _imap(self):
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
            imap.login(self.address, self._password())
            return imap
        except imaplib.IMAP4.error as exc:
            raise MailError("Gmail a refusé la connexion : vérifie l'adresse et le mot de passe d'application.") from exc
        except OSError as exc:
            raise MailError(f"Gmail injoignable : {exc}") from exc

    def unread(self, limit: int) -> list:
        imap = self._imap()
        try:
            imap.select("INBOX", readonly=True)
            _, data = imap.uid("search", None, "UNSEEN")
            uids = (data[0] or b"").split()[-limit:][::-1]
            out = []
            for uid in uids:
                _, parts = imap.uid("fetch", uid, "(BODY.PEEK[])")
                raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
                if raw:
                    out.append(self._parse(uid.decode(), email.message_from_bytes(raw, policy=default_policy)))
            return out
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _parse(self, uid: str, msg) -> Mail:
        name, addr = parseaddr(str(msg.get("From", "")))
        part = msg.get_body(preferencelist=("plain", "html"))
        body = ""
        if part is not None:
            body = part.get_content()
            if part.get_content_type() == "text/html":
                body = html_to_text(body)
        try:
            date = parsedate_to_datetime(msg.get("Date")).strftime("%Y-%m-%d %H:%M")
        except Exception:
            date = str(msg.get("Date", ""))[:16]
        return Mail("gmail", uid, name or addr, addr, str(msg.get("Subject", "")), date, clean_body(body),
                    str(msg.get("Message-ID", "")), str(msg.get("References", "")))

    def build_reply(self, mail: Mail, text: str) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = self.address
        msg["To"] = mail.sender_addr
        subject = mail.subject or ""
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        if mail.message_id:
            msg["In-Reply-To"] = mail.message_id
            msg["References"] = (mail.references + " " + mail.message_id).strip()
        msg.set_content(text)
        return msg

    def send_reply(self, mail: Mail, text: str) -> None:
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
                smtp.login(self.address, self._password())
                smtp.send_message(self.build_reply(mail, text))
        except smtplib.SMTPException as exc:
            raise MailError(f"Envoi Gmail impossible : {exc}") from exc

    def save_draft(self, mail: Mail, text: str) -> None:
        imap = self._imap()
        try:
            _, folders = imap.list()
            drafts = next((f.decode().split(' "/" ')[-1] for f in folders or [] if b"\\Drafts" in f), '"[Gmail]/Drafts"')
            imap.append(drafts, "\\Draft", imaplib.Time2Internaldate(time.time()),
                        self.build_reply(mail, text).as_bytes())
        finally:
            try:
                imap.logout()
            except Exception:
                pass
