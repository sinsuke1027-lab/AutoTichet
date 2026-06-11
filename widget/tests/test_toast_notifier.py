from unittest.mock import patch, MagicMock


def _mock_notification():
    notif = MagicMock()
    notif.set_audio = MagicMock()
    notif.show = MagicMock()
    return notif


def test_notify_success_calls_show():
    from widget.services.toast_notifier import notify_success
    mock_notif = _mock_notification()
    with patch("widget.services.toast_notifier._WINOTIFY_AVAILABLE", True), \
         patch("widget.services.toast_notifier.Notification", return_value=mock_notif) as mock_cls:
        notify_success("テストタスク", launch_url="https://example.com/tasks/1")
    mock_cls.assert_called_once()
    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["title"] == "✅ 起票しました"
    assert call_kwargs["msg"] == "テストタスク"
    assert call_kwargs["launch"] == "https://example.com/tasks/1"
    mock_notif.show.assert_called_once()


def test_notify_success_silent_when_winotify_unavailable():
    from widget.services.toast_notifier import notify_success
    with patch("widget.services.toast_notifier._WINOTIFY_AVAILABLE", False):
        notify_success("テストタスク")  # 例外が出ないこと


def test_notify_success_empty_launch_url():
    from widget.services.toast_notifier import notify_success
    mock_notif = _mock_notification()
    with patch("widget.services.toast_notifier._WINOTIFY_AVAILABLE", True), \
         patch("widget.services.toast_notifier.Notification", return_value=mock_notif) as mock_cls:
        notify_success("タスク名")
    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["launch"] == ""
