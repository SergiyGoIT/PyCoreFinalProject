<img src="https://github.com/user-attachments/assets/78a413ef-dc33-4582-af11-59a274d49f65" alt="Логотип команди" width="200">

# PyCoreFinalProject
**PyCore Final Team Project**  
**Персональний Помічник**

Ласкаво просимо до проєкту "Персональний Помічник" — консольної програми, яка допомагає зберігати та управляти контактами й нотатками. Цей додаток створено для зручного ведення адресної книги, організації текстових записів із тегами та зв’язками між контактами і нотатками.

## Мета проєкту
Створити систему для:
- Зберігання контактів (імена, номери телефонів, email, дні народження).
- Управління нотатками (додавання, пошук, редагування, видалення, теги).
- Збереження даних на диску з можливістю перезапуску без втрати інформації.
- Додаткових функцій, як-от скасування дій (undo) і сортування нотаток.

---

## Встановлення

### Вимоги
- **Python 3.8** або новіша версія.
- **Операційна система**: Windows, macOS, Linux.
- **Залежності**:
  - `colorama` — для кольорового виведення в консолі.
  - `prompt_toolkit` — для автодоповнення команд.

### Інструкція
1. **Клонування репозиторію**:
   ```bash
   git clone https://github.com/SergiyGoIT/PyCoreFinalProject.git
   cd PyCoreFinalProject
   ```

2. **Встановлення залежностей**:
   ```bash
   pip install -r requirements.txt
   ```
   Якщо `requirements.txt` ще немає, встановіть бібліотеки вручну:
   ```bash
   pip install colorama prompt_toolkit
   ```

3. **Запуск програми**:
   ```bash
   python main.py
   ```

---

## Використання

Після запуску програми з’явиться консольний інтерфейс із підказкою `>>>`. Ви можете вводити команди для роботи з контактами та нотатками. Наберіть `help` для перегляду всіх доступних команд.

### Основні команди
- **Контакти**:
  - `add-contact [Іван +380991234567 ivan@example.com]` — додати контакт (можна інтерактивно).
  - `list-contacts` — показати всі контакти.
  - `search-contact Іван` — знайти контакти за запитом.
  - `edit-contact 1 phones=+380991234567` — редагувати контакт.
  - `delete-contact 1` — видалити контакт.
  - `birthdays days=7` — показати найближчі дні народження.
  - `undo-contact` — скасувати останню дію з контактами.

- **Нотатки**:
  - `add-note "Зустріч із клієнтом" #робота` — додати нотатку з тегом.
  - `list-notes` — показати всі нотатки.
  - `search-note клієнт` — знайти нотатки за текстом або контактами.
  - `edit-note 1 text="Нова зустріч"` — редагувати нотатку.
  - `delete-note 1` — видалити нотатку.
  - `search-tag робота` — знайти нотатки за тегом.
  - `sort-by-date` — відсортувати нотатки за датою.
  - `undo-note` — скасувати останню дію з нотатками.

### Приклад використання
```
>>> add-contact
Enter full name: Іван Петренко
Enter phone (optional, format +380XXXXXXXXX): +380991234567
Enter emails (optional, separated by space): ivan@example.com
Enter birthday (optional, DD.MM.YYYY): 15.05.1990
Create a note for this contact? [Y/n]: y
Enter note text: Зустріч із Іваном
Enter #tags (optional): #робота
Contact added (ID=1)
New note for contact (ID=1, note ID=1)
```

```
>>> birthdays
Найближчі ДН протягом 7 днів:
Contact ID=1
Name: Іван Петренко
...
```

---

## Основні функції

### 1. Управління контактами
- Додавання контактів із валідацією:
  - Телефон: формат `+380XXXXXXXXX` або `0XXXXXXXXX`.
  - Email: наявність `@` і домену.
- Пошук за іменем, телефоном, email або днем народження.
- Редагування та видалення контактів із обробкою пов’язаних нотаток.
- Виведення списку контактів із найближчими днями народження (налаштовується параметром `days`).

### 2. Управління нотатками
- Додавання нотаток із текстом, тегами та прив’язкою до контактів.
- Пошук за текстом, тегами, датою чи пов’язаними контактами.
- Редагування (текст, теги, зв’язки) та видалення нотаток.
- Сортування за датою створення.

### 3. Збереження даних
- Контакти зберігаються у `contacts.json`.
- Нотатки — у `notes.json`.
- Дані зберігаються автоматично при виході (`exit` або `close`).

---

## Додаткові можливості
- **Теги для нотаток**: Додавайте теги через `#тег` (наприклад, `#робота`, `#важливо`).
- **Пошук і сортування за тегами**: Використовуйте `search-tag` і `list-tags` для роботи з тегами.
- **Інтелектуальний аналіз**: Програма пропонує схожі команди, якщо введено неправильну (наприклад, "add-contat" → "add-contact").
- **Скасування дій**: Команди `undo-contact` і `undo-note` повертають останні зміни (до 10 дій).
- **Зв’язок контактів і нотаток**: Додавайте нотатки до контактів одразу після їх створення.

---

## Структура проєкту
```
PersonalAssistant/
│
├── main.py           # Точка входу, логіка CLI та команди
├── contacts.json     # Файл із контактами
├── notes.json        # Файл із нотатками
├── personal_assistant.log # Лог помилок
├── requirements.txt  # Залежності (colorama, prompt_toolkit)
├── README.md         # Документація
└── .gitignore        # Ігнорування файлів (logs, *.pyc тощо)
```

**Примітка**: У фінальній версії весь код поки що в одному файлі `main.py`. Для кращої структури рекомендується розділити на модулі (наприклад, `contacts.py`, `notes.py`).

---

## Відомі проблеми
- Якщо файли `contacts.json` або `notes.json` пошкоджені, програма створює нові порожні файли, але не попереджає про втрату даних.
- Валідація телефону підтримує лише український формат (`+380XXXXXXXXX`).
- Інтелектуальний аналіз обмежений пропозицією схожих команд і не розпізнає природну мову (наприклад, "додай контакт Іван").

---

## Розробники
- **Sergiy Shyshko** — тім лід, координатор проєкту.
- **[Ім’я скрам-майстра]** — скрам-майстер, організація процесу.
- **[Ім’я ментора]** — ментор проєкту, технічний консультант.
- **[Ім’я розробника 1]** — розробка логіки контактів.
- **[Ім’я розробника 2]** — розробка логіки нотаток.
- **[Ім’я розробника 3]** — збереження даних і тестування.

---

## Як внести вклад
1. Створіть форк репозиторію.
2. Додайте зміни у новій гілці:
   ```bash
   git checkout -b feature/назва-зміни
   ```
3. Закомітьте зміни та створіть pull request:
   ```bash
   git commit -m "Опис змін"
   git push origin feature/назва-зміни
   ```
4. Опишіть зміни в pull request.
