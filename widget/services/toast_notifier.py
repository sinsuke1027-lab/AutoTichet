from __future__ import annotations

import logging

_WINOTIFY_AVAILABLE = False
try:
    from winotify import Notification, audio  # type: ignore[import]
    _WINOTIFY_AVAILABLE = True
except ImportError:
    pass


def notify_overdue(titles: list[str], launch_url: str = "") -> None:
    """期限切れタスクのトースト通知を表示する。"""
    if not titles:
        return
    if not _WINOTIFY_AVAILABLE:
        logging.warning("winotify が見つかりません。トースト通知をスキップします。")
        return

    count = len(titles)
    body = "\n".join(f"・{t}" for t in titles[:5])
    if count > 5:
        body += f"\n…他 {count - 5} 件"

    try:
        toast = Notification(
            app_id="AutoTicket",
            title=f"期限切れタスクが {count} 件あります",
            msg=body,
            duration="short",
            launch=launch_url,
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        logging.debug("notify_overdue: sent %d tasks", count)
    except Exception as exc:
        logging.error("notify_overdue error: %s", exc)


def notify_today(titles: list[str], launch_url: str = "") -> None:
    """今日締め切りのタスクのトースト通知を表示する。"""
    if not titles:
        return
    if not _WINOTIFY_AVAILABLE:
        logging.warning("winotify が見つかりません。トースト通知をスキップします。")
        return

    count = len(titles)
    body = "\n".join(f"・{t}" for t in titles[:5])
    if count > 5:
        body += f"\n…他 {count - 5} 件"

    try:
        toast = Notification(
            app_id="AutoTicket",
            title=f"今日締め切りのタスクが {count} 件あります",
            msg=body,
            duration="short",
            launch=launch_url,
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        logging.debug("notify_today: sent %d tasks", count)
    except Exception as exc:
        logging.error("notify_today error: %s", exc)


def notify_success(title: str, launch_url: str = "") -> None:
    """起票成功のトースト通知を表示する。"""
    if not _WINOTIFY_AVAILABLE:
        logging.warning("winotify が見つかりません。トースト通知をスキップします。")
        return
    try:
        toast = Notification(
            app_id="AutoTicket",
            title="✅ 起票しました",
            msg=title,
            duration="short",
            launch=launch_url,
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        logging.debug("notify_success: %s", title)
    except Exception as exc:
        logging.error("notify_success error: %s", exc)
