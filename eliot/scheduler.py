"""Rappels et tâches programmées (« rappelle-moi… », « chaque matin à 9h, … »)."""
import json
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .text import norm

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NUMBERS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "dix": 10, "quinze": 15,
           "vingt": 20, "trente": 30}
REMINDER_PREFIX = re.compile(r"^(?:rappelle-moi|rappelle moi|fais-moi penser|fais moi penser|previens-moi|previens moi)\b")
TASK_PREFIX = re.compile(r"^(?:programme|planifie|automatise)\b")
REC = re.compile(r"\b(?:chaque|tous les|toutes les) (?P<r>jours?|matins?|soirs?|semaines?|" + "|".join(d + "s?" for d in DAYS)
                 + r")\b|\b(?P<wd>en semaine|du lundi au vendredi|les jours ouvres|chaque jour ouvre)\b")
REL = re.compile(r"\bdans (?:(?P<quart>un quart d'heure)|(?P<demi>une demi-?heure)|(?P<n>\d+|" + "|".join(NUMBERS)
                 + r") ?(?P<u>minutes?|min|mn|heures?|h)\b)")
TIME = re.compile(r"\b(?:a|vers|pour|des) (?:(?P<midi>midi)|(?P<minuit>minuit)|(?P<h>\d{1,2}) ?(?:h|heures?|:) ?(?P<m>\d{2})?)\b")
DAY = re.compile(r"\b(?P<d>apres-demain|apres demain|demain|ce soir|ce matin|" + "|".join(DAYS) + r")(?: prochain)?\b")


class ScheduleError(ValueError):
    pass


@dataclass
class Schedule:
    id: int
    kind: str
    text: str
    next_run: str
    recurrence: str = "none"
    weekday: int = -1
    hour: int = 9
    minute: int = 0

    @property
    def when(self) -> datetime:
        return datetime.fromisoformat(self.next_run)


def _cut(orig: str, low: str, m):
    return orig[:m.start()] + orig[m.end():], low[:m.start()] + low[m.end():]


def _next_for(rec: str, weekday: int, hour: int, minute: int, after: datetime) -> datetime:
    day = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
    for _ in range(9):
        ok = (rec == "daily" or (rec == "weekdays" and day.weekday() < 5) or (rec == "weekly" and day.weekday() == weekday))
        if ok and day > after:
            return day
        day += timedelta(days=1)
    return day


def parse_schedule(orig: str, low: str, now: datetime = None) -> dict:
    now = now or datetime.now()
    kind = "reminder" if REMINDER_PREFIX.match(low) else "task"
    m = REMINDER_PREFIX.match(low) or TASK_PREFIX.match(low)
    if m:
        orig, low = orig[m.end():], low[m.end():]
    rec, weekday, when, hour, minute, default_hour = "none", -1, None, None, 0, None

    m = REC.search(low)
    if m:
        if m.group("wd"):
            rec = "weekdays"
        else:
            word = m.group("r").rstrip("s")
            if word in DAYS:
                rec, weekday = "weekly", DAYS.index(word)
            else:
                rec = "weekly" if word == "semaine" else "daily"
                weekday = now.weekday() if word == "semaine" else -1
                default_hour = {"matin": 9, "soir": 19}.get(word)
        orig, low = _cut(orig, low, m)

    m = REL.search(low)
    if m:
        if m.group("quart"):
            delta = timedelta(minutes=15)
        elif m.group("demi"):
            delta = timedelta(minutes=30)
        else:
            n = int(m.group("n")) if m.group("n").isdigit() else NUMBERS[m.group("n")]
            delta = timedelta(hours=n) if m.group("u").startswith("h") else timedelta(minutes=n)
        when = now + delta
        orig, low = _cut(orig, low, m)

    m = TIME.search(low)
    if m:
        hour = 12 if m.group("midi") else 0 if m.group("minuit") else int(m.group("h"))
        minute = int(m.group("m") or 0) if m.group("h") else 0
        if hour > 23 or minute > 59:
            raise ScheduleError("Cette heure n'existe pas.")
        orig, low = _cut(orig, low, m)

    m = DAY.search(low)
    day_offset = None
    if m and when is None and rec == "none":
        d = m.group("d").replace(" ", "-")
        if d in ("ce-soir", "ce-matin"):
            day_offset = 0
            default_hour = 19 if d == "ce-soir" else 9
        elif d == "demain":
            day_offset = 1
        elif d == "apres-demain":
            day_offset = 2
        else:
            day_offset = (DAYS.index(d) - now.weekday()) % 7 or 7
        orig, low = _cut(orig, low, m)

    if hour is None:
        hour = default_hour
    if when is None:
        if rec != "none":
            when = _next_for(rec, weekday, hour if hour is not None else 9, minute, now)
            hour = hour if hour is not None else 9
        elif hour is not None or day_offset is not None:
            hour = hour if hour is not None else 9
            when = (now + timedelta(days=day_offset or 0)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            if when <= now and day_offset is None:
                when += timedelta(days=1)
        else:
            raise ScheduleError("Je n'ai pas compris quand. Exemple : « rappelle-moi d'appeler Paul demain à 15h ».")
    text = re.sub(r"^[\s,:;.-]*(?:de |d'|que |qu'|a |pour )?", "", orig, flags=re.I)
    text = re.sub(r"[\s,;:.-]+$", "", re.sub(r"\s{2,}", " ", text)).strip(" ,")
    if not text:
        raise ScheduleError("Que dois-je te rappeler ou faire ?")
    return {"kind": kind, "text": text, "when": when, "recurrence": rec, "weekday": weekday,
            "hour": when.hour if hour is None else hour, "minute": when.minute if hour is None else minute}


def describe(s: Schedule) -> str:
    at = f"{s.hour} h {s.minute:02d}"
    if s.recurrence == "daily":
        when = f"tous les jours à {at}"
    elif s.recurrence == "weekdays":
        when = f"du lundi au vendredi à {at}"
    elif s.recurrence == "weekly":
        when = f"chaque {DAYS[s.weekday]} à {at}"
    else:
        when = "le " + s.when.strftime("%d/%m à %H h %M")
    label = "Rappel" if s.kind == "reminder" else "Tâche"
    return f"n°{s.id} · {label} {when} : {s.text}"


class Scheduler:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.items = []
        if self.path.exists():
            try:
                self.items = [Schedule(**i) for i in json.loads(self.path.read_text(encoding="utf-8"))]
            except (ValueError, TypeError, OSError):
                self.items = []

    def save(self) -> None:
        self.path.write_text(json.dumps([asdict(i) for i in self.items], indent=1, ensure_ascii=False), encoding="utf-8")

    def add(self, kind, text, when, recurrence="none", weekday=-1, hour=None, minute=None) -> Schedule:
        with self._lock:
            sid = max([i.id for i in self.items] + [0]) + 1
            item = Schedule(sid, kind, text, when.isoformat(timespec="seconds"), recurrence, weekday,
                            when.hour if hour is None else hour, when.minute if minute is None else minute)
            self.items.append(item)
            self.save()
            return item

    def remove(self, sid: int) -> bool:
        with self._lock:
            before = len(self.items)
            self.items = [i for i in self.items if i.id != sid]
            self.save()
            return len(self.items) < before

    def pop_due(self, now: datetime = None) -> list:
        now = now or datetime.now()
        due = []
        with self._lock:
            for item in list(self.items):
                if item.when <= now:
                    due.append(Schedule(**asdict(item)))
                    if item.recurrence == "none":
                        self.items.remove(item)
                    else:
                        item.next_run = _next_for(item.recurrence, item.weekday, item.hour, item.minute,
                                                  max(now, item.when)).isoformat(timespec="seconds")
            if due:
                self.save()
        return due

    def postpone(self, item: Schedule, minutes: int = 2) -> None:
        self.add(item.kind, item.text, datetime.now() + timedelta(minutes=minutes))


def parse_text(raw: str, now=None) -> dict:
    from .commands.router import clean
    orig, low = clean(raw)
    return parse_schedule(orig, low, now)
