import asyncio
import csv
import html
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv


DATA_FILE = Path(__file__).with_name("interactions.csv")
REACTIONS = {
    "Есть потенциальная польза": "🌿",
    "Нейтрально": "🙂",
    "Есть риск": "🔴",
    "Нет данных": "🔎",
}


@dataclass(frozen=True)
class Interaction:
    first: str
    second: str
    reaction: str
    explanation: str


def pair_key(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first.strip(), second.strip())))


def load_interactions(path: Path) -> dict[tuple[str, str], Interaction]:
    interactions: dict[tuple[str, str], Interaction] = {}
    required_columns = {"substance_1", "substance_2", "reaction", "explanation"}

    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise ValueError("CSV должен содержать: substance_1, substance_2, reaction, explanation")

        for row_number, row in enumerate(reader, start=2):
            first = (row["substance_1"] or "").strip()
            second = (row["substance_2"] or "").strip()
            reaction = (row["reaction"] or "").strip()
            explanation = (row["explanation"] or "").strip()
            key = pair_key(first, second)

            if not first or not second or not explanation:
                raise ValueError(f"Строка {row_number}: заполните вещества и пояснение")
            if first == second:
                raise ValueError(f"Строка {row_number}: вещество не может сочетаться само с собой")
            if reaction not in REACTIONS:
                raise ValueError(f"Строка {row_number}: неизвестный тип реакции: {reaction}")
            if key in interactions:
                raise ValueError(f"Строка {row_number}: повтор пары {first} / {second}")

            interactions[key] = Interaction(first, second, reaction, explanation)

    if not interactions:
        raise ValueError("CSV не содержит ни одной пары")
    return interactions


def first_choices(interactions: dict[tuple[str, str], Interaction]) -> list[str]:
    """Первое вещество: берём обе колонки, убираем дубликаты."""
    return sorted({substance for pair in interactions for substance in pair})


def second_choices(first: str, interactions: dict[tuple[str, str], Interaction]) -> list[str]:
    """Второе вещество: все вещества из обеих колонок, с которыми у выбранного есть реакция."""
    return sorted({
        substance
        for pair in interactions
        if first in pair
        for substance in pair
        if substance != first
    })


INTERACTIONS = load_interactions(DATA_FILE)
SUBSTANCES = first_choices(INTERACTIONS)
SELECTED_FIRST: dict[int, str] = {}


def first_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=substance, callback_data=f"first:{index}")
        for index, substance in enumerate(SUBSTANCES)
    ]
    return keyboard_rows(buttons)


def second_keyboard(first: str) -> InlineKeyboardMarkup:
    candidates = second_choices(first, INTERACTIONS)
    buttons = [
        InlineKeyboardButton(text=substance, callback_data=f"second:{index}")
        for index, substance in enumerate(candidates)
    ]
    return keyboard_rows(
        buttons,
        footer=InlineKeyboardButton(text="↩️ Изменить первое вещество", callback_data="restart"),
    )


def keyboard_rows(
    buttons: list[InlineKeyboardButton],
    footer: InlineKeyboardButton | None = None,
) -> InlineKeyboardMarkup:
    rows = [buttons[index:index + 2] for index in range(0, len(buttons), 2)]
    if footer:
        rows.append([footer])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Проверить другую пару", callback_data="restart")
    ]])


async def show_first_choice(message: Message) -> None:
    await message.answer(
        "<b>Привет! 👋</b>\n"
        "Я помогу посмотреть информацию о сочетании двух веществ.\n\n"
        "🧪 <i>Сейчас это демо-версия с тестовыми данными.</i>\n"
        "Выберите первое вещество ⤵️",
        reply_markup=first_keyboard(),
    )


dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message) -> None:
    SELECTED_FIRST.pop(message.chat.id, None)
    await show_first_choice(message)


@dp.callback_query(F.data == "restart")
async def restart(callback: CallbackQuery) -> None:
    SELECTED_FIRST.pop(callback.message.chat.id, None)
    await callback.answer()
    await callback.message.edit_text(
        "<b>Давайте начнём заново 🔄</b>\n\n"
        "Выберите первое вещество ⤵️",
        reply_markup=first_keyboard(),
    )


@dp.callback_query(F.data.startswith("first:"))
async def choose_first(callback: CallbackQuery) -> None:
    index = int(callback.data.split(":", maxsplit=1)[1])
    if index not in range(len(SUBSTANCES)):
        await callback.answer("Кнопка устарела. Начните заново.", show_alert=True)
        return
    first = SUBSTANCES[index]
    SELECTED_FIRST[callback.message.chat.id] = first
    await callback.answer()
    await callback.message.edit_text(
        f"<b>Первое вещество выбрано ✅</b>\n{html.escape(first)}\n\n"
        "Теперь выберите второе вещество ⤵️",
        reply_markup=second_keyboard(first),
    )


@dp.callback_query(F.data.startswith("second:"))
async def choose_second(callback: CallbackQuery) -> None:
    first = SELECTED_FIRST.get(callback.message.chat.id)
    if not first:
        await callback.answer("Сначала выберите первое вещество.", show_alert=True)
        return

    candidates = second_choices(first, INTERACTIONS)
    index = int(callback.data.split(":", maxsplit=1)[1])
    if index not in range(len(candidates)):
        await callback.answer("Кнопка устарела. Начните заново.", show_alert=True)
        return

    second = candidates[index]
    interaction = INTERACTIONS[pair_key(first, second)]
    status = f"{REACTIONS[interaction.reaction]} <b>{html.escape(interaction.reaction)}</b>"
    text = (
        "<b>🔎 Результат проверки</b>\n\n"
        f"<b>{html.escape(first)} + {html.escape(second)}</b>\n"
        "━━━━━━━━━━━━━━━━\n"
        f"{status}\n\n"
        f"{html.escape(interaction.explanation)}\n\n"
        "💡 <i>Это демонстрационный ответ. Не меняйте лечение самостоятельно — обсудите важные вопросы с врачом.</i>"
    )
    SELECTED_FIRST.pop(callback.message.chat.id, None)
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=restart_keyboard())


async def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("В .env не задана переменная BOT_TOKEN")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
