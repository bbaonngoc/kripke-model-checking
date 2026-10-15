"""Sáu biến trạng thái và guard/action của năm chức năng Smart Lock.

password_ok/password_bad là kết quả kiểm tra mật khẩu đã trừu tượng hóa.
admin_authenticated là kết quả xác thực quản trị từ môi trường mô phỏng;
không có cơ sở dữ liệu tài khoản hoặc mật khẩu thật trong mô hình này.
"""

from dataclasses import dataclass, replace
from typing import Iterator, Literal

Version = Literal["v0", "v1"]
VERSIONS = ("v0", "v1")
PHASES = ("normal", "locked_out", "resetting")
# Thứ tự cố định để BFS gán ID ổn định giữa các lần chạy.
EVENTS = (
    "password_ok", "password_bad", "open_door", "close_door", "tamper",
    "admin_reset", "reset_complete", "reset_retry", "wait",
)


@dataclass(frozen=True)
class State:
    authenticated: bool = False
    failed_attempts: int = 0
    door_open: bool = False
    alarm: bool = False
    phase: str = "normal"
    admin_authorized: bool = False

    def __post_init__(self) -> None:
        """Chỉ ràng buộc miền; không loại bỏ trạng thái vi phạm nghiệp vụ."""
        for name in ("authenticated", "door_open", "alarm", "admin_authorized"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} phải là bool")
        if type(self.failed_attempts) is not int or not 0 <= self.failed_attempts <= 3:
            raise ValueError("failed_attempts phải là số nguyên từ 0 đến 3")
        if self.phase not in PHASES:
            raise ValueError(f"phase phải thuộc {PHASES}")


INITIAL_STATE = State()


class InvalidEvent(ValueError):
    """Sự kiện bị từ chối; trạng thái bất biến của bên gọi không thay đổi."""


def labels(state: State) -> frozenset[str]:
    """L(s): AP được tính từ dữ liệu thật, không gán nhãn theo tên state."""
    propositions = {
        "authenticated": state.authenticated,
        "door_open": state.door_open,
        "alarm": state.alarm,
        "locked_out": state.phase == "locked_out",
        "attempts_eq_3": state.failed_attempts == 3,
        "resetting": state.phase == "resetting",
        "admin_authorized": state.admin_authorized,
        "idle": state == INITIAL_STATE,
    }
    return frozenset(name for name, holds in propositions.items() if holds)


def step(
    state: State,
    event: str,
    version: Version = "v1",
    *,
    admin_authenticated: bool = False,
) -> State:
    """Kiểm tra guard rồi thực hiện một action nguyên tử.

    admin_reset yêu cầu kết quả xác thực admin True một cách tường minh.
    Quyền không suy ra từ authenticated hoặc phase của state.
    """
    if version not in VERSIONS:
        raise ValueError(f"Phiên bản không hợp lệ: {version}")
    if type(admin_authenticated) is not bool:
        raise ValueError("admin_authenticated phải là bool")

    # F5: reset nội bộ có ưu tiên; không nhận input bên ngoài trong pha này.
    if state.phase == "resetting":
        if event == "reset_complete":
            return INITIAL_STATE
        if event == "reset_retry" and version == "v0":
            return state  # BUG-02: có thể chọn thử lại vô hạn.
        raise InvalidEvent(f"{event} bị từ chối khi đang resetting")

    # F1 + F2: chỉ thử mật khẩu khi chưa có phiên và cửa đang đóng.
    can_authenticate = (
        state.phase == "normal" and not state.alarm
        and not state.authenticated and not state.door_open
    )
    if event == "password_ok" and can_authenticate:
        return replace(state, authenticated=True, failed_attempts=0)
    if event == "password_bad" and can_authenticate and state.failed_attempts < 3:
        attempts = min(state.failed_attempts + 1, 3)
        return replace(
            state, authenticated=False, failed_attempts=attempts,
            phase="locked_out" if attempts == 3 else "normal",
        )

    # F3: v0 cố ý thiếu duy nhất guard authenticated khi mở cửa.
    if event == "open_door" and (
        state.phase == "normal" and not state.alarm and not state.door_open
        and (state.authenticated or version == "v0")
    ):
        return replace(state, door_open=True)
    if event == "close_door" and state.phase == "normal" and state.door_open:
        return replace(state, door_open=False, authenticated=False)

    # F4: đóng cửa và hủy xác thực cùng lúc phát hiện tamper.
    if event == "tamper":
        return replace(state, alarm=True, door_open=False, authenticated=False)

    # F5: lưu kết quả xác thực admin cho yêu cầu reset đã được chấp nhận.
    if event == "admin_reset" and admin_authenticated:
        return replace(
            state, phase="resetting", admin_authorized=True,
            authenticated=False, door_open=False,
        )
    if event == "wait":
        return state  # Chỉ tới đây khi không ở resetting.
    raise InvalidEvent(f"{event} không được phép ở trạng thái {state}")


def successors(state: State, version: Version = "v1") -> Iterator[tuple[str, State]]:
    """Sinh đúng các event có guard đúng, dùng chung action với mô phỏng.

    Cạnh admin_reset biểu diễn yêu cầu đã xác thực quản trị thành công.
    Yêu cầu với admin_authenticated=False bị step từ chối, không là cạnh.
    """
    for event in EVENTS:
        try:
            target = step(
                state, event, version,
                admin_authenticated=(event == "admin_reset"),
            )
        except InvalidEvent:
            continue
        yield event, target
