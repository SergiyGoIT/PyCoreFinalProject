import json
import pickle
import os
import re
import logging
import textwrap
from datetime import datetime, date
from typing import List, Optional, Dict, Type, TypeVar, Generic, Any
from collections import UserDict, deque, defaultdict, Counter
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from colorama import Fore, Style, init
from difflib import get_close_matches
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion

# Ініціалізація colorama
init(autoreset=True)

# ------------------------------------------------------
# Константи та глобальні налаштування
# ------------------------------------------------------
MAX_UNDO_STEPS = 10
CONTACTS_FILE = "contacts.json"
NOTES_FILE = "notes.json"

# Тимчасові файли (pickle) для сесії
SESSION_CONTACTS_FILE = "contacts_session.pkl"
SESSION_NOTES_FILE = "notes_session.pkl"

logging.basicConfig(
    filename="personal_assistant.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s: %(message)s"
)

# ------------------------------------------------------
# Утиліти для форматованого виводу
# ------------------------------------------------------
def print_border(title: str = "", width: int = 60) -> None:
    """Друкує верхню рамку з опціональним заголовком."""
    if title:
        text_len = len(title) + 2
        if text_len > width - 4:
            text_len = width - 4
        left_part = "─" * 2
        mid_part = f" {title} "
        right_len = width - 2 - len(mid_part)
        if right_len < 0:
            right_len = 0
        right_part = "─" * right_len
        print(Fore.YELLOW + left_part + mid_part + right_part + Style.RESET_ALL)
    else:
        print(Fore.YELLOW + "─" * width + Style.RESET_ALL)

def print_bottom_border(width: int = 60) -> None:
    """Друкує нижню горизонтальну межу."""
    print(Fore.YELLOW + "─" * width + Style.RESET_ALL)

def print_colored_box(header: str, lines: List[str], width: int = 60) -> None:
    """Друкує текст у кольоровій рамці з заголовком."""
    print_border(header, width)
    for line in lines:
        print(line)
    print_bottom_border(width)

def indent_lines(lines: List[str], spaces: int = 2) -> str:
    """Додає відступ до кожного рядка."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in lines)

def format_contact(contact: "Contact") -> str:
    """Форматує відображення контакту у багаторядковий блок."""
    lines = []
    lines.append(f"{Fore.CYAN}Name:{Style.RESET_ALL} {contact.name}")
    if contact.phones:
        lines.append(f"{Fore.CYAN}Phones:{Style.RESET_ALL}")
        for phone in contact.phones:
            lines.append(f"  {phone}")
    else:
        lines.append(f"{Fore.CYAN}Phones:{Style.RESET_ALL} (немає)")

    if contact.emails:
        lines.append(f"{Fore.CYAN}Emails:{Style.RESET_ALL}")
        for email in contact.emails:
            lines.append(f"  {email}")
    else:
        lines.append(f"{Fore.CYAN}Emails:{Style.RESET_ALL} (немає)")

    if contact.birthday:
        bday_str = contact.birthday.strftime("%d.%m.%Y")
        lines.append(f"{Fore.CYAN}Birthday:{Style.RESET_ALL} {bday_str}")
        days = contact.days_to_birthday()
        age_val = contact.age()
        lines.append(f"  Days to next BDay: {days if days is not None else '-'}")
        lines.append(f"  Age: {age_val if age_val is not None else '-'}")
    else:
        lines.append(f"{Fore.CYAN}Birthday:{Style.RESET_ALL} (не вказано)")

    return "\n".join(lines)

def format_note(note: "Note") -> str:
    """Форматує відображення нотатки у багаторядковий блок."""
    lines = []
    lines.append(f"{Fore.MAGENTA}Text:{Style.RESET_ALL} {note.text}")
    if note.tags:
        lines.append(f"{Fore.MAGENTA}Tags:{Style.RESET_ALL} " + ", ".join(note.tags))
    else:
        lines.append(f"{Fore.MAGENTA}Tags:{Style.RESET_ALL} (немає)")
    created_str = note.created_at.strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"Created at: {created_str}")
    return "\n".join(lines)

def format_help_table(commands_data: List[List[str]], title: str = "Commands", width: int = 72) -> str:
    """Форматує допоміжну таблицю з командами."""
    max_cmd_len = max(len(row[0]) for row in commands_data)
    output_lines = []
    separator = "+" + "-" * (width - 2) + "+"
    header_line = f"| {title.center(width - 2)} |"
    output_lines.append(separator)
    output_lines.append(header_line)
    output_lines.append(separator)
    for cmd, desc in commands_data:
        # Спочатку обгортання для опису, щоб не вилазив за межі width
        # На кожен рядок залишимо (width - 4 - max_cmd_len - 3) символів
        # 4 символи це "|" + " " з обох боків + "|"
        # max_cmd_len — місце під команду
        # 3 символи мінімальний пробіл між командою та описом
        wrap_width = width - (max_cmd_len + 4 + 3)
        wrapped_desc = textwrap.wrap(desc, width=wrap_width) if wrap_width > 10 else [desc]
        if not wrapped_desc:
            wrapped_desc = [""]
        # Формуємо перший рядок з командою
        first_desc_line = wrapped_desc[0]
        line = f"| {Fore.CYAN}{cmd:<{max_cmd_len}}{Style.RESET_ALL} : {first_desc_line}"
        space_left = width - 2 - len(remove_ansi_escape(line))
        if space_left < 0:
            space_left = 0
        line += " " * space_left + "|"
        output_lines.append(line)

        # Якщо опис займає кілька рядків, виводимо решту з відступами
        for add_line in wrapped_desc[1:]:
            line = f"| {' ' * (max_cmd_len + 3)} {add_line}"
            space_left = width - 2 - len(remove_ansi_escape(line))
            if space_left < 0:
                space_left = 0
            line += " " * space_left + "|"
            output_lines.append(line)

    output_lines.append(separator)
    return "\n".join(output_lines)

def remove_ansi_escape(s: str) -> str:
    """Допоміжна функція, щоб прибрати ANSI-коди кольорів під час обчислення довжини."""
    return re.sub(r'\x1b\[[0-9;]*m', '', s)

# ------------------------------------------------------
# Базові класи даних
# ------------------------------------------------------
class BaseEntry(ABC):
    """Абстрактний базовий клас для записів."""
    id: int

    @abstractmethod
    def to_dict(self) -> dict:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "BaseEntry":
        pass

    @abstractmethod
    def matches(self, query: str) -> bool:
        pass

    @abstractmethod
    def update(self, **fields):
        pass

@dataclass
class Contact(BaseEntry):
    id: int
    name: str
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    birthday: Optional[date] = None

    def __post_init__(self):
        if self.birthday and isinstance(self.birthday, str):
            parsed = parse_birthday(self.birthday)
            self.birthday = parsed

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "phones": self.phones,
            "emails": self.emails,
            "birthday": self.birthday.strftime("%Y-%m-%d") if self.birthday else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Contact":
        return cls(
            id=data["id"],
            name=data["name"],
            phones=data.get("phones", []),
            emails=data.get("emails", []),
            birthday=data.get("birthday")
        )

    def matches(self, query: str) -> bool:
        q = query.lower()
        if q in self.name.lower():
            return True
        if get_close_matches(q, [self.name.lower()], n=1, cutoff=0.7):
            return True
        for p in self.phones:
            if q in p:
                return True
        for e in self.emails:
            if q in e.lower():
                return True
        if self.birthday and q in self.birthday.strftime("%d.%m.%Y"):
            return True
        return False

    def update(self, **fields):
        if "name" in fields:
            self.name = fields["name"]
        if "phones" in fields:
            self.phones = fields["phones"]
        if "emails" in fields:
            self.emails = fields["emails"]
        if "birthday" in fields:
            bday_str = fields["birthday"]
            self.birthday = parse_birthday(bday_str)

    def birthday_str(self) -> str:
        return self.birthday.strftime("%d.%m.%Y") if self.birthday else ""

    def days_to_birthday(self) -> Optional[int]:
        if not self.birthday:
            return None
        today = date.today()
        bday = self.birthday.replace(year=today.year)
        if bday < today:
            bday = bday.replace(year=today.year + 1)
        return (bday - today).days

    def age(self) -> Optional[int]:
        if not self.birthday:
            return None
        today = date.today()
        return today.year - self.birthday.year - ((today.month, today.day) < (self.birthday.month, self.birthday.day))

@dataclass
class Note(BaseEntry):
    id: int
    text: str
    tags: List[str] = field(default_factory=list)
    contact_ids: List[int] = field(default_factory=list)  # ДОДАНЕ ПОЛЕ для зв’язку
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.text.strip():
            raise ValueError("Текст нотатки не може бути порожнім.")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "tags": self.tags,
            "contact_ids": self.contact_ids,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        created_str = data.get("created_at")
        created_dt = datetime.now()
        if created_str:
            try:
                created_dt = datetime.strptime(created_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return cls(
            id=data["id"],
            text=data["text"],
            tags=data.get("tags", []),
            contact_ids=data.get("contact_ids", []),
            created_at=created_dt
        )

    def matches(self, query: str) -> bool:
        q = query.lower()
        if q in self.text.lower():
            return True
        for tag in self.tags:
            if q in tag.lower():
                return True
        return False

    def update(self, **fields):
        if "text" in fields:
            self.text = fields["text"]
        if "tags" in fields:
            self.tags = fields["tags"]
        if "contact_ids" in fields:
            self.contact_ids = fields["contact_ids"]

# ------------------------------------------------------
# Універсальні колекції
# ------------------------------------------------------
E = TypeVar("E", bound=BaseEntry)

class BaseBook(UserDict, Generic[E]):
    entry_class: Type[E] = BaseEntry
    entry_type_name: str = "entry"

    def __init__(self):
        super().__init__()
        self.undo_stack = deque(maxlen=MAX_UNDO_STEPS)
        self._max_id = 0

    def add(self, entry: E) -> int:
        if entry.id == 0:
            entry.id = self._max_id + 1
        self._max_id = max(self._max_id, entry.id)
        self.undo_stack.append(("add", entry.id, None))
        self.data[entry.id] = entry
        return entry.id

    def create_and_add(self, **kwargs) -> int:
        entry = self.entry_class(id=0, **kwargs)
        return self.add(entry)

    def find_by_id(self, id_val: int) -> E:
        if id_val not in self.data:
            raise KeyError(f"{self.entry_type_name} з ID={id_val} не знайдено.")
        return self.data[id_val]

    def find(self, query: str) -> List[E]:
        return [entry for entry in self.data.values() if entry.matches(query)]

    def edit(self, id_val: int, **changes) -> None:
        old_entry = self.find_by_id(id_val)
        old_copy = self.entry_class.from_dict(old_entry.to_dict())
        self.undo_stack.append(("edit", id_val, old_copy))
        old_entry.update(**changes)

    def delete(self, id_val: int) -> bool:
        if id_val in self.data:
            old_entry = self.data[id_val]
            self.undo_stack.append(("delete", id_val, old_entry))
            del self.data[id_val]
            return True
        return False

    def undo(self) -> str:
        if not self.undo_stack:
            return "Немає дій для скасування."
        action, id_val, old_value = self.undo_stack.pop()
        if action == "add":
            if id_val in self.data:
                del self.data[id_val]
            return f"Скасовано додавання {self.entry_type_name} з ID {id_val}."
        elif action == "delete":
            self.data[id_val] = old_value
            return f"Відновлено {self.entry_type_name} з ID {id_val}."
        elif action == "edit":
            self.data[id_val] = old_value
            return f"Скасовано редагування {self.entry_type_name} з ID {id_val}."
        return "Невідома операція для undo."

    def save(self, filename: str) -> None:
        save_dict = {str(eid): entry.to_dict() for eid, entry in self.data.items()}
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(save_dict, f, ensure_ascii=False, indent=4)

    @classmethod
    def load(cls, filename: str) -> "BaseBook":
        new_book = cls()
        if not os.path.exists(filename):
            return new_book
        try:
            with open(filename, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(Fore.YELLOW + f"Файл {filename} не знайдено або пошкоджено. Створено порожню книгу." + Style.RESET_ALL)
            return new_book
        for k, v in raw.items():
            eid = int(k)
            entry = cls.entry_class.from_dict(v)
            new_book.data[eid] = entry
            new_book._max_id = max(new_book._max_id, eid)
        return new_book

class AddressBook(BaseBook["Contact"]):
    entry_class = Contact
    entry_type_name = "контакт"

    def get_upcoming_birthdays(self, days_ahead: int = 7) -> List["Contact"]:
        today = date.today()
        results = []
        for c in self.data.values():
            if not c.birthday:
                continue
            bday_this_year = c.birthday.replace(year=today.year)
            if bday_this_year < today:
                bday_this_year = bday_this_year.replace(year=today.year + 1)
            if 0 <= (bday_this_year - today).days < days_ahead:
                results.append(c)
        return results

    def create_note_for_contact(self, nbook: "Notebook", contact_id: int,
        text: str, tags: Optional[List[str]] = None) -> int:
        """
        Створює нотатку в Notebook з прив'язкою до заданого контакту.
        Повертає ID створеної нотатки.
        """
        if contact_id not in self.data:
            raise KeyError(f"Контакт з ID={contact_id} не знайдено.")
        return nbook.create_and_add(
            text=text,
            tags=tags if tags else [],
            contact_ids=[contact_id]
        )

    def get_contact_ids(self) -> List[str]:
        return [str(contact.id) for contact in self.data.values()]
    def get_contact_names(self) -> List[str]:
        return [contact.name for contact in self.data.values()]

class Notebook(BaseBook["Note"]):
    entry_class = Note
    entry_type_name = "нотатку"

    def sort_by_date(self) -> List["Note"]:
        return sorted(self.data.values(), key=lambda x: x.created_at)

    def find_by_tag(self, tag: str) -> List["Note"]:
        tag_lower = tag.lower()
        return [note for note in self.data.values() if any(tag_lower in t.lower() for t in note.tags)]

    def find_by_date(self, date_str: str) -> List["Note"]:
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Невірний формат дати. Використовуйте YYYY-MM-DD")
        return [n for n in self.data.values() if n.created_at.date() == target]

    def find_by_contact_id(self, contact_id: int) -> List["Note"]:
        """Повертає список нотаток, прив'язаних до контакту з даним ID."""
        return [note for note in self.data.values() if contact_id in note.contact_ids]

    def get_unique_tags(self) -> List[str]:
            tags = set()
            for note in self.data.values():
                tags.update(note.tags)
            return list(tags)
    
    def get_note_ids(self) -> List[str]:
        return [str(note.id) for note in self.data.values()]
    
    def get_common_words(self, min_length: int = 3, max_suggestions: int = 10) -> List[str]:
        """
        Повертає список найпоширеніших слів із тексту нотаток.
        :param min_length: мінімальна довжина слова
        :param max_suggestions: максимальна кількість пропозицій
        :return: список слів
        """
        # Стоп-слова для виключення (можна розширити)
        stop_words = {"і", "а", "на", "в", "з", "до", "що", "як", "це", "та", "для"}
        # Збираємо всі слова
        all_words = []
        for note in self.data.values():
            # Розбиваємо текст на слова, видаляємо пунктуацію
            words = re.findall(r'\b\w+\b', note.text.lower())
            # Фільтруємо за довжиною та стоп-словами
            all_words.extend(word for word in words if len(word) >= min_length and word not in stop_words)
        
        # Рахуємо частоту слів
        word_counts = Counter(all_words)
        # Беремо найпоширеніші
        common_words = [word for word, _ in word_counts.most_common(max_suggestions)]
        return common_words
# ------------------------------------------------------
# Допоміжні функції
# ------------------------------------------------------
def parse_birthday(bday: str) -> date:
    """Парсить рядок дати народження у форматі ДД.ММ.РРРР або РРРР-ММ-ДД і повертає date()."""
    fmt_candidates = ["%d.%m.%Y", "%Y-%m-%d"]
    for fmt in fmt_candidates:
        try:
            parsed = datetime.strptime(bday, fmt).date()
            return parsed
        except ValueError:
            continue
    raise ValueError("Дата народження в неправильному форматі.")

def validate_birthday_format(bday: str) -> bool:
    """Лише перевіряє, чи рядок відповідає одному з форматів дати (не перевіряє адекватність)."""
    for fmt in ["%d.%m.%Y", "%Y-%m-%d"]:
        try:
            datetime.strptime(bday, fmt)
            return True
        except ValueError:
            continue
    return False

def validate_phone(phone: str) -> str:
    """Перевірка правильності номера телефону формату +380XXXXXXXXX чи 0XXXXXXXXX."""
    if re.fullmatch(r"\+380\d{9}", phone):
        return phone
    elif re.fullmatch(r"0\d{9}", phone):
        return "+38" + phone
    return ""

def validate_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))

def normalize_name(name: str) -> str:
    return " ".join(part.capitalize() for part in name.strip().split())

# ------------------------------------------------------
# Логіка збереження в .pkl для сесій
# ------------------------------------------------------
def save_all(abook: AddressBook, nbook: Notebook):
    """
    Зберігаємо **поточний** стан (in-memory) у pickle-файли SESSION_CONTACTS_FILE і SESSION_NOTES_FILE.
    Якщо програма аварійно завершиться, при наступному запуску можна буде відновити.
    """
    with open(SESSION_CONTACTS_FILE, "wb") as f:
        # Збережемо у pickle словник (dict) + _max_id
        data = {
            "raw": {str(eid): abook.data[eid].to_dict() for eid in abook.data},
            "max_id": abook._max_id
        }
        pickle.dump(data, f)

    with open(SESSION_NOTES_FILE, "wb") as f:
        data = {
            "raw": {str(eid): nbook.data[eid].to_dict() for eid in nbook.data},
            "max_id": nbook._max_id
        }
        pickle.dump(data, f)

def session_files_exist() -> bool:
    return os.path.exists(SESSION_CONTACTS_FILE) or os.path.exists(SESSION_NOTES_FILE)

def remove_session_files():
    """Видаляємо тимчасові pkl-файли."""
    if os.path.exists(SESSION_CONTACTS_FILE):
        os.remove(SESSION_CONTACTS_FILE)
    if os.path.exists(SESSION_NOTES_FILE):
        os.remove(SESSION_NOTES_FILE)

def load_from_session_files() -> tuple[AddressBook, Notebook]:
    """
    Завантажуємо AddressBook та Notebook з pickle-файлів.
    Якщо вони відсутні/пошкоджені, повертаємо порожні.
    """
    abook = AddressBook()
    nbook = Notebook()

    if os.path.exists(SESSION_CONTACTS_FILE):
        try:
            with open(SESSION_CONTACTS_FILE, "rb") as f:
                data = pickle.load(f)
                raw = data["raw"]
                max_id = data["max_id"]
                for k, v in raw.items():
                    entry = abook.entry_class.from_dict(v)
                    abook.data[int(k)] = entry
                abook._max_id = max_id
        except:
            pass

    if os.path.exists(SESSION_NOTES_FILE):
        try:
            with open(SESSION_NOTES_FILE, "rb") as f:
                data = pickle.load(f)
                raw = data["raw"]
                max_id = data["max_id"]
                for k, v in raw.items():
                    entry = nbook.entry_class.from_dict(v)
                    nbook.data[int(k)] = entry
                nbook._max_id = max_id
        except:
            pass

    return abook, nbook

def commit_session_to_json(abook: AddressBook, nbook: Notebook):
    """
    Фінальний крок: зберігаємо поточні дані (in-memory) у JSON (contacts.json, notes.json),
    а потім видаляємо тимчасові .pkl.
    """
    abook.save(CONTACTS_FILE)
    nbook.save(NOTES_FILE)
    remove_session_files()

# ------------------------------------------------------
# Перевірка існування сесійних файлів / завантаження основних
# ------------------------------------------------------
def restore_or_load() -> tuple[AddressBook, Notebook]:
    """
    Якщо існують session.pkl — запитуємо у користувача, чи відновлювати.
    Якщо так => вантажимо з pickle.
    Якщо ні => видаляємо pickle-файли (якщо були) і вантажимо з JSON.
    """
    if session_files_exist():
        print(Fore.YELLOW + "Виявлено незавершену сесію! Відновити? (Y/n)" + Style.RESET_ALL)
        ans = input().strip().lower()
        if ans in ("y", "yes", ""):
            # Відновити
            abook, nbook = load_from_session_files()
            print(Fore.GREEN + "Сесію відновлено." + Style.RESET_ALL)
            return abook, nbook
        else:
            # Відмовитися
            remove_session_files()
    # Якщо pickle-сесій немає або користувач відмовився => беремо JSON
    abook = AddressBook.load(CONTACTS_FILE)
    nbook = Notebook.load(NOTES_FILE)
    return abook, nbook

# ------------------------------------------------------
# Декоратор для обробки помилок
# ------------------------------------------------------
def input_error(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyError as e:
            logging.error(f"KeyError in {func.__name__}: {e}")
            print(Fore.RED + str(e) + Style.RESET_ALL)
        except ValueError as e:
            logging.error(f"ValueError in {func.__name__}: {e}")
            print(Fore.RED + str(e) + Style.RESET_ALL)
        except IndexError:
            logging.error(f"IndexError in {func.__name__}: Недостатньо аргументів.")
            print(Fore.RED + "Неправильний формат команди або недостатньо аргументів." + Style.RESET_ALL)
        except Exception as e:
            logging.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            print(Fore.RED + f"Сталася несподівана помилка: {e}" + Style.RESET_ALL)
    return wrapper

# ------------------------------------------------------
# Функції-утиліти CLI
# ------------------------------------------------------
def parse_contact_input(tokens: List[str]) -> Dict[str, Any]:
    """
    Якщо дані передано у вигляді одного рядка,
    розділяємо токени: всі токени, що не є телефоном або email, формують ім'я.
    """
    phone = None
    emails = []
    name_parts = []
    birthday = None

    for token in tokens:
        # Спочатку перевіряємо, чи телефон
        possible_phone = validate_phone(token)
        if not phone and possible_phone:
            phone = possible_phone
            continue
        # чи емейл
        if validate_email(token):
            emails.append(token)
            continue
        # чи день народження
        if validate_birthday_format(token):
            birthday = token
            continue
        # інакше припускаємо, що це частина імені
        name_parts.append(token)

    name = " ".join(name_parts).strip()
    result = {"name": normalize_name(name)}
    if phone:
        result["phones"] = [phone]
    if emails:
        result["emails"] = emails
    if birthday:
        result["birthday"] = birthday
    return result

def save_all(abook: AddressBook, nbook: "Notebook"):
    """Зберігаємо поточний стан обох книжок."""
    abook.save(CONTACTS_FILE)
    nbook.save(NOTES_FILE)

# ------------------------------------------------------
# Реалізація команд
# ------------------------------------------------------
@input_error
def add_contact(args: List[str], abook: AddressBook, nbook: Notebook):
    """
    add-contact:
      - inline: add-contact John 0XXXXXXXXX john@e.com ...
      - або інтерактивно, якщо не передали args
    """
    if args:
        # inline
        data = parse_contact_input(args)
        if not (data.get("phones") or data.get("emails") or data.get("birthday")):
            raise ValueError("Неможливо створити контакт без жодної валідної інформації: телефону, email або дати народження.")
    else:
        # інтерактивно
        while True:
            name = input("Enter contact name: ").strip()
            if name:
                name = normalize_name(name)
                break
            print(Fore.RED + "Ім'я не може бути порожнім." + Style.RESET_ALL)

        phones = []
        while True:
            phone = input("Enter phone (optional, +380XXXXXXXXX або 0XXXXXXXXX): ").strip()
            if not phone:
                break
            norm = validate_phone(phone)
            if norm:
                phones = [norm if isinstance(norm, str) else str(norm)]
                break
            print(Fore.RED + "Телефон має бути у форматі +380XXXXXXXXX або 0XXXXXXXXX." + Style.RESET_ALL)

        emails = []
        while True:
            emails_str = input("Enter emails (optional, розділені пробілом): ").strip()
            if not emails_str:
                break
            emails = emails_str.split()
            if all(validate_email(e) for e in emails):
                break
            print(Fore.RED + "Некоректний email. Спробуйте ще раз." + Style.RESET_ALL)

        birthday = None
        while True:
            bday_input = input("Enter birthday (optional, DD.MM.YYYY або YYYY-MM-DD): ").strip()
            if not bday_input:
                break
            if validate_birthday_format(bday_input):
                parsed = parse_birthday(bday_input)
                # Перевірка на майбутнє
                if parsed > date.today():
                    confirm = input(Fore.YELLOW +
                                    f"Дата {parsed} більше за поточну. Підтвердити? [Y/n]: " +
                                    Style.RESET_ALL).strip().lower()
                    if confirm not in ("n", "no"):
                        birthday = bday_input
                        break
                    else:
                        # повторне коло
                        continue
                else:
                    birthday = bday_input
                    break
            else:
                print(Fore.RED + "Неправильний формат дати. Спробуйте ще раз." + Style.RESET_ALL)

        data = {"name": name}
        if phones:
            data["phones"] = phones
        if emails:
            data["emails"] = emails
        if birthday:
            data["birthday"] = birthday

    new_id = abook.create_and_add(**data)
    contact_obj = abook.find_by_id(new_id)
    block = format_contact(contact_obj)
    print_colored_box(f"Contact added (ID={new_id})", block.split("\n"))

    # Пропонуємо одразу створити нотатку
    choice = input("Create a note for this contact? [Y/n]: ").strip().lower()
    if choice in ("", "y", "yes"):
        note_text = input("Enter note text: ").strip()
        if not note_text:
            print(Fore.YELLOW + "Порожній текст. Пропускаємо створення нотатки." + Style.RESET_ALL)
        else:
            tags_input = input("Enter #tags (optional, через пробіл): ").strip()
            tags = [t.lstrip('#') for t in tags_input.split()] if tags_input else []
            note_id = abook.create_note_for_contact(nbook, new_id, note_text, tags=tags)
            note_obj = nbook.find_by_id(note_id)
            note_block = format_note(note_obj)
            # Для наочності додамо ім'я контакту в блок
            note_lines = note_block.split("\n")
            note_lines.insert(1, f"{Fore.MAGENTA}Linked contact:{Style.RESET_ALL} {contact_obj.name}")
            note_block = "\n".join(note_lines)
            print_colored_box(
                f"New note for contact (ID={new_id}, note ID={note_id})",
                note_block.split("\n")
            )

    # Збереження
    save_all(abook, nbook)

@input_error
def list_contacts(args: List[str], abook: AddressBook):
    """list-contacts: виводимо всі контакти."""
    if not abook.data:
        print(Fore.YELLOW + "У книзі немає контактів." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Усього контактів: {len(abook.data)}" + Style.RESET_ALL)
    for c in abook.data.values():
        block = format_contact(c)
        print_colored_box(f"Contact ID={c.id}", block.split("\n"))

@input_error
def search_contact(args: List[str], abook: AddressBook):
    if args:
        query = " ".join(args)
    else:
        query = input("Введіть пошуковий запит (name, phone, email, etc.): ").strip()
        if not query:
            raise ValueError("Запит не може бути порожнім.")
    results = abook.find(query)
    if not results:
        print(Fore.CYAN + "Нічого не знайдено." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Знайдено {len(results)} результат(ів) за '{query}':" + Style.RESET_ALL)
    for c in results:
        block = format_contact(c)
        print_colored_box(f"Contact ID={c.id}", block.split("\n"))

@input_error
def edit_contact(args: List[str], abook: AddressBook, nbook: Notebook):
    if not args:
        # інтерактив
        id_val = int(input("Enter contact ID to edit: ").strip())
        c = abook.find_by_id(id_val)
        new_name = input("Enter new name (ENTER=skip): ").strip()
        if new_name:
            c.name = normalize_name(new_name)

        new_phones = []
        while True:
            p = input("Enter phone (ENTER=skip, 'stop'=кінець): ").strip()
            if not p or p.lower() == "stop":
                break
            valid = validate_phone(p)
            if valid:
                new_phones.append(valid)
            else:
                print(Fore.RED + "Невірний формат телефону!" + Style.RESET_ALL)
        if new_phones:
            c.phones = new_phones

        new_emails = []
        while True:
            e = input("Enter email (ENTER=skip, 'stop'=кінець): ").strip()
            if not e or e.lower() == "stop":
                break
            if validate_email(e):
                new_emails.append(e)
            else:
                print(Fore.RED + "Невірний формат email!" + Style.RESET_ALL)
        if new_emails:
            c.emails = new_emails

        b = input("Enter birthday (ENTER=skip): ").strip()
        if b:
            if validate_birthday_format(b):
                c.birthday = parse_birthday(b)
            else:
                print(Fore.RED + "Невірний формат дати. Пропускаємо." + Style.RESET_ALL)
    else:
        # inline
        id_val = int(args[0])
        tokens = args[1:]
        changes = parse_contact_input(tokens)
        abook.edit(id_val, **changes)

    print(Fore.GREEN + "Контакт відредаговано." + Style.RESET_ALL)
    save_all(abook, nbook)

@input_error
def delete_contact(args: List[str], abook: AddressBook, nbook: Notebook):
    if args:
            identifier = " ".join(args).strip()
    else:
        identifier = input("Введіть ID чи ім'я контакту для видалення: ").strip()
        if not identifier:
            raise ValueError("Ідентифікатор не може бути порожнім.")
    if identifier.isdigit():
        id_val = int(identifier)
        try:
            contact = abook.find_by_id(id_val)
        except KeyError:
            print(Fore.RED + f"Контакт ID={id_val} не знайдено." + Style.RESET_ALL)
            return
    else:
        matches = abook.find(identifier)
        if not matches:
            print(Fore.RED + f"Контакт з іменем '{identifier}' не знайдено." + Style.RESET_ALL)
            return
        elif len(matches) > 1:
            print(Fore.YELLOW + f"Знайдено кілька контактів за ім'ям '{identifier}':" + Style.RESET_ALL)
            for c in matches:
                print(f"  ID={c.id}: {c.name}")
            id_val = input("Уточніть ID для видалення: ").strip()
            if not id_val.isdigit():
                print(Fore.RED + "Невірний формат ID. Операція скасована." + Style.RESET_ALL)
                return
            id_val = int(id_val)
            try:
                contact = abook.find_by_id(id_val)
            except KeyError:
                print(Fore.RED + f"Контакт ID={id_val} не знайдено." + Style.RESET_ALL)
                return
        else:
            contact = matches[0]
            id_val = contact.id

    # Перевірка нотаток
    linked_notes = nbook.find_by_contact_id(id_val)
    if linked_notes:
        note_ids = [note.id for note in linked_notes]
        print(Fore.YELLOW + f"Увага: Контакт '{contact.name}' пов'язаний з нотатками {note_ids}." + Style.RESET_ALL)
        choice = input("Видалити пов'язані нотатки (D) чи залишити їх без цього контакту (K)? [D/K]: ").strip().lower()
        if choice not in ('d', 'k', ''):
            print(Fore.RED + "Невідома відповідь. Операція скасована." + Style.RESET_ALL)
            return
        if choice == 'd':
            # Видаляємо всі пов'язані нотатки
            for note in linked_notes:
                nbook.delete(note.id)
            print(Fore.MAGENTA + f"Видалено {len(linked_notes)} нотаток, пов'язаних з контактом ID={id_val}." + Style.RESET_ALL)
        else:
            # За замовчуванням - від'єднати контакт (видалити його ID зі списку contact_ids)
            for note in linked_notes:
                if id_val in note.contact_ids:
                    note.contact_ids.remove(id_val)
            print(Fore.MAGENTA + f"Контакт видалено з {len(linked_notes)} нотаток (нотатки збережено)." + Style.RESET_ALL)

    if abook.delete(id_val):
        print(Fore.GREEN + f"Контакт ID={id_val} видалено." + Style.RESET_ALL)
    else:
        print(Fore.RED + f"Контакт ID={id_val} не знайдено." + Style.RESET_ALL)
    # збереження
    save_all(abook, nbook)

@input_error
def upcoming_birthdays(args: List[str], abook: AddressBook):
    """birthdays [days=7] — контакти з ДН протягом вказаної кількості днів."""
    days = 7
    if args and args[0].startswith("days="):
        days = int(args[0].split("=", 1)[1])
    else:
        days_input = input("Введіть кількість днів для пошуку ДН (за замовчуванням 7): ").strip()
        days = int(days_input) if days_input.isdigit() else 7
    results = abook.get_upcoming_birthdays(days_ahead=days)
    if not results:
        print(Fore.CYAN + f"Немає Дня народження протягом {days} днів." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Найближчі Дні народження протягом {days} днів:" + Style.RESET_ALL)
    for c in results:
        block = format_contact(c)
        print_colored_box(f"Contact ID={c.id}", block.split("\n"))

@input_error
def undo_contact(args: List[str], abook: AddressBook, nbook: Notebook):
    """undo-contact — скасування останньої дії з контактами."""
    msg = abook.undo()
    print(msg)
    save_all(abook, nbook)

# ------------------------------------------------------
# Команди для роботи з нотатками
# ------------------------------------------------------
@input_error
def add_note(args: List[str], nb: Notebook, abook: AddressBook):
    """
    add-note [дані в один рядок] або інтерактивно.
    Приклад: add-note Привіт, світ! #tag1 #tag2
    """
    if args:
        # inline
        text_parts = [arg for arg in args if not arg.startswith('#')]
        tags = [arg.lstrip('#') for arg in args if arg.startswith('#')]
        text = " ".join(text_parts).strip()
        if not text:
            raise ValueError("Текст нотатки не може бути порожнім.")
        data = {"text": text, "tags": tags, "contact_ids": []}
    else:
        # інтерактивно
        text = input("Enter text: ").strip()
        if not text:
            raise ValueError("Текст нотатки не може бути порожнім.")
        tags_input = input("Enter #tag (optional): ").strip()
        tags = [t.lstrip('#') for t in tags_input.split()] if tags_input else []
        data = {"text": text, "tags": tags, "contact_ids": []}

    new_id = nb.create_and_add(**data)
    note_obj = nb.find_by_id(new_id)
    block = format_note(note_obj)
    print_colored_box(f"Note added (ID={new_id})", block.split("\n"))

    # збереження
    save_all(abook, nb)

@input_error
def list_notes(args: List[str], nb: Notebook, abook: AddressBook = None):
    """list-notes — виводить усі нотатки, показує прив’язані контакти."""
    if not nb.data:
        print(Fore.YELLOW + "Нотаток ще немає." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Усього нотаток: {len(nb.data)}" + Style.RESET_ALL)

    for note in nb.data.values():
        block = format_note(note)
        # Якщо є abook і є contact_ids, покажемо імена контактів
        if abook and note.contact_ids:
            contact_names = []
            for cid in note.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={note.id}", block.split("\n"))

@input_error
def search_note(args: List[str], nb: Notebook, abook: AddressBook):
    if args:
        query = " ".join(args).lower()
    else:
        query = input("Введіть запит для пошуку (текст, тег або ім'я контакту): ").strip().lower()
        if not query:
            raise ValueError("Запит не може бути порожнім.")
    results = []

    # 1. Пошук за текстом і тегами
    text_matches = nb.find(query)
    results.extend(text_matches)

    # 2. Якщо є abook, шукаємо контакти за query
    contact_matches = abook.find(query)
    for contact in contact_matches:
        # додаємо нотатки, прив'язані до цього контакту
        for note in nb.find_by_contact_id(contact.id):
            results.append(note)

    # Усуваємо дублікати
    unique_results = {}
    for note in results:
        unique_results[note.id] = note
    results = list(unique_results.values())

    if not results:
        print(Fore.CYAN + "Нічого не знайдено." + Style.RESET_ALL)
        return

    print(Fore.GREEN + f"Знайдено {len(results)} нотаток за запитом '{query}':" + Style.RESET_ALL)
    for n in results:
        block = format_note(n)
        if n.contact_ids:
            contact_names = []
            for cid in n.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={n.id}", block.split("\n"))

@input_error
def edit_note(args: List[str], nb: Notebook, abook: AddressBook):
    if args:
        id_val = int(args[0])
        changes = {}
        for chunk in args[1:]:
            if "=" in chunk:
                key, val = chunk.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == "tags":
                    changes[key] = [x.strip().lstrip('#') for x in val.split(",")]
                elif key == "contact_ids":
                    changes[key] = [int(x) for x in re.split(r"[,;\s]+", val) if x.isdigit()]
                else:
                    changes[key] = val
    else:
        id_val = input("Введіть ID нотатки для редагування: ").strip()
        if not id_val.isdigit():
            raise ValueError("ID має бути числом.")
        id_val = int(id_val)
        note = nb.find_by_id(id_val)
        print(Fore.CYAN + f"Поточний текст нотатки: {note.text}" + Style.RESET_ALL)
        new_text = input("Введіть новий текст нотатки (ENTER to skip): ").strip()
        print(Fore.CYAN + f"Поточні теги: {', '.join(note.tags)}" + Style.RESET_ALL)
        new_tags = input("Введіть нові теги (через пробіл, ENTER для пропуску): ").strip()
        print(Fore.CYAN + f"Поточні ID контактів: {note.contact_ids}" + Style.RESET_ALL)
        new_contact_ids = input("Введіть нові ID контактів (через кому, ENTER для пропуску): ").strip()

        changes = {}
        if new_text:
            changes["text"] = new_text
        if new_tags:
            changes["tags"] = [t.lstrip('#') for t in new_tags.split()]
        if new_contact_ids:
            changes["contact_ids"] = [int(x) for x in new_contact_ids.split(",") if x.strip().isdigit()]

    nb.edit(id_val, **changes)
    print(Fore.GREEN + f"Нотатка ID={id_val} оновлена." + Style.RESET_ALL)

    save_all(abook, nb)

@input_error
def delete_note(args: List[str], nb: Notebook, abook: AddressBook):
    if args:
        id_val = int(args[0])
    else:
        id_input = input("Введіть ID нотатки для видалення: ").strip()
        if not id_input.isdigit():
            raise ValueError("ID має бути числом.")
        id_val = int(id_input)
    if nb.delete(id_val):
        print(Fore.GREEN + f"Нотатку ID={id_val} видалено." + Style.RESET_ALL)
    else:
        print(Fore.RED + f"Нотатку ID={id_val} не знайдено." + Style.RESET_ALL)
    save_all(abook, nb)

@input_error
def pin_note(args: List[str], nb: Notebook, abook: AddressBook):
    if args:
        id_val = int(args[0])
    else:
        id_input = input("Введіть ID нотатки для закріплення: ").strip()
        if not id_input.isdigit():
            raise ValueError("ID має бути числом.")
        id_val = int(id_input)
    note = nb.find_by_id(id_val)
    if "📌" not in note.tags:
        note.tags.append("📌")
    print(Fore.GREEN + f"Note ID={id_val} pinned." + Style.RESET_ALL)
    save_all(abook, nb)

@input_error
def list_pinned_notes(args: List[str], nb: Notebook, abook: AddressBook):
    pinned = nb.find_by_tag("📌")
    if not pinned:
        print(Fore.CYAN + "Немає закріплених нотаток." + Style.RESET_ALL)
        return
    for n in pinned:
        lines = [
            f"Text: {n.text}",
            f"Tags: {', '.join(n.tags)}"
        ]
        print_colored_box(f"Note ID={n.id}", lines)

@input_error
def sort_notes_by_date(args: List[str], nb: Notebook, abook: AddressBook):
    """sort-by-date — сортує нотатки за датою створення."""
    sorted_list = nb.sort_by_date()
    for note in sorted_list:
        block = format_note(note)
        if note.contact_ids:
            contact_names = []
            for cid in note.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={note.id}", block.split("\n"))

@input_error
def search_note_by_tag(args: List[str], nb: Notebook, abook: AddressBook = None):
    """search-tag <tag> — пошук нотаток за тегом."""
    if args:
        tag = args[0]
    else:
        tag = input("Введіть тег для пошуку (без #): ").strip()
        if not tag:
            raise ValueError("Тег не може бути порожнім.")
    results = nb.find_by_tag(tag)
    if not results:
        print(Fore.CYAN + f"Немає нотаток з тегом '{tag}'." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Знайдено {len(results)} нотаток з тегом '{tag}':" + Style.RESET_ALL)
    for n in results:
        block = format_note(n)
        if n.contact_ids:
            contact_names = []
            for cid in n.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={n.id}", block.split("\n"))

@input_error
def search_note_by_date(args: List[str], nb: Notebook, abook: AddressBook = None):
    if args:
        date_str = args[0]
    else:
        date_str = input("Введіть дату для пошуку (YYYY-MM-DD): ").strip()
        if not date_str:
            raise ValueError("Дата не може бути порожньою.")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")  # Валідація формату
    except ValueError:
        raise ValueError("Невірний формат дати. Використовуйте YYYY-MM-DD.")
    results = nb.find_by_date(date_str)
    if not results:
        print(Fore.CYAN + f"Немає нотаток за датою {date_str}." + Style.RESET_ALL)
        return
    print(Fore.GREEN + f"Знайдено {len(results)} нотаток за {date_str}:" + Style.RESET_ALL)
    for n in results:
        block = format_note(n)
        if n.contact_ids:
            contact_names = []
            for cid in n.contact_ids:
                try:
                    c = abook.find_by_id(cid)
                    contact_names.append(c.name)
                except KeyError:
                    pass
            if contact_names:
                lines = block.split("\n")
                lines.insert(1, f"{Fore.MAGENTA}Contacts:{Style.RESET_ALL} " + ", ".join(contact_names))
                block = "\n".join(lines)
        print_colored_box(f"Note ID={n.id}", block.split("\n"))

@input_error
def undo_note(args: List[str], nb: Notebook, abook: AddressBook):
    """undo-note — скасування останньої дії з нотатками."""
    msg = nb.undo()
    print(msg)
    save_all(abook, nb)

@input_error
def list_tags(args: List[str], nb: Notebook):
    """
    list-tags [<filter>] — виводить усі унікальні теги з нотаток.
    Можливий фільтр: "date" або "desc" (сортування за датою),
    або підрядок (для пошуку).
    """
    tag_dict = defaultdict(list)

    for note in nb.data.values():
        for tag in note.tags:
            tag_dict[tag].append(note.created_at)

    if not tag_dict:
        print(Fore.CYAN + "Жодного тегу не знайдено." + Style.RESET_ALL)
        return

    filter_value = args[0] if args else None
    result = list(tag_dict.keys())

    if filter_value and filter_value.lower() not in ("date", "desc"):
        # фільтр за частиною слова
        result = [tag for tag in result if filter_value.lower() in tag.lower()]
    elif filter_value == "date":
        # сортуємо за найстаршою датою, де цей тег з’явився
        result.sort(key=lambda t: min(tag_dict[t]))
    elif filter_value == "desc":
        # за найстаршою датою у зворотному порядку
        result.sort(key=lambda t: min(tag_dict[t]), reverse=True)

    print(Fore.GREEN + "Унікальні теги:" + Style.RESET_ALL)
    for tag in result:
        count = len(tag_dict[tag])
        print(f"• {tag} ({count} нот.)")

@input_error
def delete_note_by_text(args: List[str], nb: Notebook, abook: AddressBook):
    """delete-note-text <query> — видаляє всі нотатки, що містять заданий текст."""
    if args:
        query = " ".join(args).lower()
    else:
        query = input("Введіть текст для пошуку та видалення: ").strip().lower()
        if not query:
            raise ValueError("Запит не може бути порожнім.")
    notes_to_delete = [note for note in nb.data.values() if query in note.text.lower()]
    if not notes_to_delete:
        print(Fore.CYAN + f"Нотаток із текстом '{query}' не знайдено." + Style.RESET_ALL)
        return
    deleted_count = 0
    for note in notes_to_delete:
        if nb.delete(note.id):
            deleted_count += 1
    print(Fore.GREEN + f"Видалено {deleted_count} нотаток із текстом '{query}'." + Style.RESET_ALL)
    save_all(abook, nb)
    
# ------------------------------------------------------
# Багаторівневий Completer
# ------------------------------------------------------
class MultiLevelCompleter(Completer):
    def __init__(self, commands, subcommands_map, abook: AddressBook, nbook: Notebook):
        super().__init__()
        self.commands = commands
        self.subcommands_map = subcommands_map
        self.abook = abook
        self.nbook = nbook

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        tokens = text.split()

        if len(tokens) == 0:
            for cmd in self.commands:
                yield Completion(cmd, start_position=0)
            return

        if len(tokens) == 1:
            partial_cmd = tokens[0].lower()
            for cmd in self.commands:
                if cmd.startswith(partial_cmd):
                    yield Completion(cmd, start_position=-len(partial_cmd))
            return

        command = tokens[0].lower()
        current_arg = tokens[-1].lower() if len(tokens) > 1 else ""

        if command in self.subcommands_map:
            if command in ["edit-note", "delete-note", "pin-note"]:
                # Пропонуємо ID нотаток
                ids = self.nbook.get_note_ids()
                for id_str in ids:
                    if current_arg in id_str:
                        yield Completion(id_str, start_position=-len(current_arg))

            elif command == "search-note":
                # Пропонуємо теги та імена контактів
                suggestions = []
                suggestions.extend(self.nbook.get_unique_tags())
                suggestions.extend(self.abook.get_contact_names())
                for suggestion in suggestions:
                    if current_arg in suggestion.lower():
                        yield Completion(suggestion, start_position=-len(current_arg))

            elif command == "search-date":
                # Пропонуємо шаблон дати
                date_template = "YYYY-MM-DD"
                if date_template.lower().startswith(current_arg):
                    yield Completion(date_template, start_position=-len(current_arg))

            elif command == "search-tag":
                # Пропонуємо теги
                tags = self.nbook.get_unique_tags()
                for tag in tags:
                    if current_arg in tag.lower():
                        yield Completion(tag, start_position=-len(current_arg))

            elif command == "delete-note-text":
                # Пропонуємо найпоширеніші слова з нотаток
                words = self.nbook.get_common_words()
                for word in words:
                    if current_arg in word.lower():
                        yield Completion(word, start_position=-len(current_arg))

            else:
                possible_args = self.subcommands_map[command]
                for arg in possible_args:
                    if current_arg in arg.lower():
                        yield Completion(arg, start_position=-len(current_arg))

# ------------------------------------------------------
# Головна функція
# ------------------------------------------------------
def main():
    # Спробуємо відновити сесію або завантажити основні JSON
    abook, nbook = restore_or_load()

    COMMANDS = {
        # Контакти
        "add-contact": (lambda args: add_contact(args, abook, nbook)),
        "list-contacts": (lambda args: list_contacts(args, abook)),
        "search-contact": (lambda args: search_contact(args, abook)),
        "edit-contact": (lambda args: edit_contact(args, abook, nbook)),
        "delete-contact": (lambda args: delete_contact(args, abook, nbook)),
        "birthdays": (lambda args: upcoming_birthdays(args, abook)),
        "undo-contact": (lambda args: undo_contact(args, abook, nbook)),

        # Нотатки
        "add-note": (lambda args: add_note(args, nbook, abook)),
        "list-notes": (lambda args: list_notes(args, nbook, abook)),
        "search-note": (lambda args: search_note(args, nbook, abook)),
        "edit-note": (lambda args: edit_note(args, nbook, abook)),
        "delete-note": (lambda args: delete_note(args, nbook, abook)),
        "sort-by-date": (lambda args: sort_notes_by_date(args, nbook, abook)),
        "search-tag": (lambda args: search_note_by_tag(args, nbook, abook)),
        "search-date": (lambda args: search_note_by_date(args, nbook, abook)),
        "undo-note": (lambda args: undo_note(args, nbook, abook)),
        "list-tags": (lambda args: list_tags(args, nbook)),

        # Додаткові
        "delete-note-text": (lambda args: delete_note_by_text(args, nbook, abook)),
        "pin-note": (lambda args: pin_note(args, nbook, abook)),
        "list-pinned": (lambda args: list_pinned_notes(args, nbook, abook)),
    }

    # Дані для help
    help_data_contacts = [
        ["add-contact", "Додати контакт (inline/інтерактивно) з можливістю одразу створити нотатку"],
        ["list-contacts", "Список всіх контактів"],
        ["search-contact", "Пошук контакту (inline/інтерактивно)"],
        ["edit-contact", "Редагувати контакт (inline/інтерактивно)"],
        ["delete-contact", "Видалити контакт (inline/інтерактивно)"],
        ["birthdays", "Контакти з Днями народження у найближчі (за замовчуванням 7) днів: birthdays days=7"],
        ["undo-contact", "Скасувати останню дію з контактами"]
    ]

    help_data_notes = [
        ["add-note", "Додати нотатку (inline/інтерактивно)"],
        ["list-notes", "Список усіх нотаток (з відображенням прив'язаних контактів)"],
        ["search-note", "Пошук нотатки (inline/інтерактив) за текстом/тегами, а також за контактами"],
        ["edit-note", "Редагувати нотатку (inline/інтерактив): edit-note <id> text=... tags=... contact_ids=..."],
        ["delete-note", "Видалити нотатку за ID."],
        ["sort-by-date", "Сортувати нотатки за датою створення"],
        ["search-tag", "Пошук нотаток за тегом (inline/інтерактив)"],
        ["search-date", "Пошук нотаток за датою (YYYY-MM-DD)"],
        ["undo-note", "Скасувати останню дію з нотатками"],
        ["list-tags", "Список усіх тегів (з фільтром або без)"],
        ["delete-note-text", "Видалити всі нотатки, що містять заданий текст"],
        ["pin-note", "Закріпити нотатку (додає тег 📌)"],
        ["list-pinned", "Показати всі закріплені нотатки"]
    ]

    help_data_general = [
        ["help", "Вивести список команд"],
        ["exit / close", "Вийти з програми (зберегти дані)"]
    ]

    # Список команд для автодоповнення
    all_commands = list(COMMANDS.keys()) + ["help", "exit", "close"]

    # Словник зі списком можливих "ключів" для автодоповнення другого рівня
    subcommands_map = {
        "add-contact": ["name=", "phones=", "emails=", "birthday="],
        "list-contacts": [],
        "search-contact": ["<query>"],
        "edit-contact": ["<id>", "phones=", "emails=", "birthday="],
        "delete-contact": ["<id>"],
        "birthdays": ["days=7", "days=30"],
        "undo-contact": [],
        "add-note": ["<text>", "#tag"],
        "list-notes": [],
        "search-note": ["<query>", "<tag>", "<contact_name>"],
        "edit-note": ["<id>", "text=", "tags=", "contact_ids="],
        "delete-note": ["<id>"],
        "sort-by-date": [],
        "search-tag": ["<tag>"],
        "search-date": ["YYYY-MM-DD"],
        "undo-note": [],
        "list-tags": ["date", "desc", "<filter>"],
        "delete-note-text": ["<query>"],
        "pin-note": ["<id>"],
        "list-pinned": []
    }

    custom_completer = MultiLevelCompleter(all_commands, subcommands_map, abook, nbook)
    session = PromptSession(">>> ", completer=custom_completer)

    print(Fore.GREEN + "Вітаю! Це ваш персональний помічник." + Style.RESET_ALL)
    print("Наберіть 'help' для списку команд.")

    while True:
        user_input = session.prompt().strip()
        if not user_input:
            continue
        parts = user_input.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1].split() if len(parts) > 1 else []

        if command in ["exit", "close"]:
            print(Fore.YELLOW + "До побачення! Зберігаю дані..." + Style.RESET_ALL)
            # Зберігаємо дані перед виходом
            commit_session_to_json(abook, nbook)
            print(Fore.YELLOW + "Готово! До побачення." + Style.RESET_ALL)
            break
        elif command == "help":
            print(format_help_table(help_data_contacts, "Contact Management"))
            print()
            print(format_help_table(help_data_notes, "Note Management"))
            print()
            print(format_help_table(help_data_general, "General"))
        elif command in COMMANDS:
            func = COMMANDS[command]
            func(args)
        else:
            suggestions = get_close_matches(command, all_commands, n=1)
            if suggestions:
                print(Fore.CYAN + f"Команду не знайдено. Можливо, ви мали на увазі: {suggestions[0]}?" + Style.RESET_ALL)
            else:
                print(Fore.RED + "Невідома команда. Наберіть 'help' для списку команд." + Style.RESET_ALL)

if __name__ == "__main__":
    main()
