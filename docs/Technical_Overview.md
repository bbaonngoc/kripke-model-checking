# Tổng quan kỹ thuật Smart Lock

Tài liệu mô tả mô hình và thuật toán đang chạy trong repository. Mỗi phiên
bản v0/v1 dùng một mô hình tích hợp cho năm chức năng; không có mô hình riêng
cho từng chức năng hoặc bộ trạng thái riêng dành cho SMT. Các tài liệu tham
khảo được liệt kê trong [README, mục 7.1](../README.md#71-tài-liệu-tham-khảo).

## 1. Trạng thái, input và guard/action

Nguồn: [model.py](../smartlock/model.py), các hàm `State`, `labels`, `step`,
`successors`. `State` là frozen dataclass; action dùng `replace` để tạo object
mới. Equality/hash xét đủ sáu trường, dùng được làm khóa khi BFS khử trùng.

| Biến | Miền | Ý nghĩa |
|---|---|---|
| authenticated | bool | Phiên người dùng đã xác thực |
| failed_attempts | int 0..3 | Số lần sai kể từ xác thực thành công/reset gần nhất |
| door_open | bool | Cửa đang mở |
| alarm | bool | Báo động đang bật |
| phase | normal / locked_out / resetting | Pha vận hành |
| admin_authorized | bool | Bằng chứng quyền của lần reset đã được chấp nhận |

Initial: `(False, 0, False, False, 'normal', False)`.
`admin_authenticated` là input Boolean của sự kiện, không phải biến thứ bảy.
`password_ok/password_bad` và quyền admin biểu diễn kết quả xác thực đã được
trừu tượng hóa; chưa có tài khoản, mật khẩu hoặc cơ chế mật mã thật.

| Sự kiện | Guard và action chính của v1 |
|---|---|
| password_ok | normal, không alarm, chưa xác thực, cửa đóng; tạo phiên, xóa bộ đếm |
| password_bad | Cùng điều kiện trên, bộ đếm dưới 3; tăng trước, khóa khi giá trị mới bằng 3 |
| open_door | normal, không alarm, cửa đóng, authenticated; mở cửa |
| close_door | normal, cửa mở; đóng cửa và hủy phiên |
| tamper | Ngoài resetting; bật alarm, đóng cửa, hủy phiên; giữ bộ đếm/pha |
| admin_reset | Ngoài resetting và admin_authenticated=True; chuyển resetting, lưu quyền, đóng cửa/hủy phiên |
| reset_complete | Đang resetting; trả toàn bộ về initial |
| wait | Ngoài resetting; self-loop hợp lệ |
| reset_retry | Chỉ v0 trong resetting; self-loop cố ý gây lỗi liveness |

Hai lần sai đầu chưa khóa. `wait` không xóa chuỗi sai; `password_ok` hoặc
`reset_complete` xóa chuỗi sai. Reset giữ alarm/bộ đếm cho tới khi hoàn tất.
Quyền admin không suy ra từ phiên người dùng thường. Guard sai gây
`InvalidEvent`; sự từ chối không trở thành cạnh self-loop của Kripke.

`labels` tính tám AP từ dữ liệu: authenticated, door_open, alarm,
locked_out (từ phase), attempts_eq_3 (từ bộ đếm), resetting (từ phase),
admin_authorized (từ trường quyền), idle (bằng toàn bộ initial).
Hai AP của P2/P4 độc lập; không gán nhãn để làm thuộc tính đúng sẵn.
Constructor chỉ kiểm miền, không cấm trạng thái vi phạm nghiệp vụ.

## 2. Kripke và BFS

Nguồn: [kripke.py](../smartlock/kripke.py), `build_model`, `load_g2_model`,
`make_trace`, `replay_trace`; lớp `KripkeStructure` từ
[module toolkit](../toolkit/softsec-toolkit/ch1_models/kripke.py).

`K=(S,S0,R,L)`: S là states reachable, S0 chỉ chứa initial, R là tập cặp
nguồn/đích, L là AP. Danh sách `transitions` lưu thêm event trên mỗi cạnh.
Nhiều event cùng nguồn/đích được gộp trong R nhưng vẫn giữ riêng trong
danh sách event transitions. Thứ tự EVENTS cố định giúp ID tái lập.

```text
queue = [initial]; seen = {initial}
while queue chưa rỗng:
    lấy state ở đầu queue
    for event, target do successors(state) sinh bằng step:
        nếu target mới: lưu ID, parent/depth; thêm cuối queue
        ghi cạnh (state, event, target), kể cả khi target đã biết
```

Không liệt kê tích miền 192 tổ hợp, không lọc trước trạng thái xấu.
v0 có 21 states: 11 normal, 2 locked_out, 8 resetting; v1 có 18: 8, 2, 8.
Ba states thêm ở v0 là cửa mở chưa xác thực với bộ đếm 0, 1, 2.
Reset_retry thêm cạnh lặp, không thêm state. ID phải đi cùng phiên bản:
s5 v0 là resetting, s5 v1 là cửa mở đã xác thực.

`load_g2_model` đọc JSON, dựng lại bằng đúng BFS và so toàn bộ snapshot;
không ghi đè snapshot sai để ép kết quả. `structural_checks` kiểm 11 điều
kiện, gồm reachable, total, labels, tính xác định và cạnh khớp step.
Ngoài reset có wait; trong reset v1 chỉ có reset_complete. Không tự thêm
self-loop tại mọi state vì làm thay đổi nghĩa liveness.

## 3. Đặc tả và CTL model checking

Năm công thức đầy đủ ở [README, mục 3](../README.md#3-năm-đặc-tả-ctl) và
`FORMULAS` trong [ctl.py](../smartlock/ctl.py). Chuỗi công thức phục vụ trình
bày; thuật toán chỉ xử lý đúng năm thuộc tính, không có parser tổng quát.

AG yêu cầu điều kiện luôn đúng trên mọi đường, kể cả state hiện tại.
AF yêu cầu trên mọi đường cuối cùng đạt đích, cho phép ngay ở hiện tại.
P1-P4 là safety: một tiền tố hữu hạn tới bad-state đủ bác bỏ. `bad_state`
đọc AP thật, còn `check_ctl` quét toàn bộ phần reachable:

```text
bad_P1 = door_open AND (NOT authenticated OR locked_out)
bad_P2 = locked_out AND NOT attempts_eq_3
bad_P3 = alarm AND door_open
bad_P4 = resetting AND NOT admin_authorized
```

P2 là một chiều; tự nó không bảo đảm lần sai thứ ba chuyển pha. Tests
kiểm cả bộ đếm và pha sau từng lần nhập để xác nhận yêu cầu đó.

P5 dùng `af_idle_fixed_point`: bắt đầu Z từ tập idle; mỗi vòng thêm state
có **mọi** kế tiếp thuộc Z cũ; dừng khi không đổi. Sau đó mọi resetting
reachable phải thuộc Z. Đây là least fixed-point trên graph total;
deadlock bị từ chối thay vì được coi là reset hoàn tất.
v0 có lịch sử kích thước `[1]`; v1 `[1,9]` gồm idle và tám resetting.
P5 không yêu cầu mọi state normal đều thuộc AF idle.

`_liveness_trace` tìm prefix tới resetting ngoài AF, theo cạnh vẫn ngoài AF
cho tới khi lặp state. `validate_counterexample` replay rồi kiểm chu trình
khép kín, không rỗng và không có idle kể từ reset_step. Idle trong prefix
trước reset được phép. Một đường có thể hoàn tất reset chưa đủ cho AF:
chỉ một nhánh lặp mãi đã bác bỏ lượng từ “mọi đường”. Không dùng Z3 cho P5.

## 4. BMC, Z3 và completeness threshold

Nguồn: [bmc.py](../smartlock/bmc.py), `transition_constraint`, `encode_path`,
`check_bound`, `check_safety_bmc`; [run.py](../run.py) điều phối `--verify`.
BMC của bài chạy trên graph hữu hạn đã BFS, không tự trích logic từ mọi
chương trình Python. `x_i` mã hóa ID state G2, `e_i` mã hóa event; k bước
có k+1 state và k event.

```text
I: x_0 = id(s0)
Domains: state ID thuộc S; event ID thuộc EVENTS
T(x_i,e_i,x_(i+1)): OR các bộ source/event/target có thật trong G2
Query_Pj(k): I AND domains AND các T AND OR(i=0..k) bad_Pj(x_i)
```

Không thêm safety làm giả định đúng trong T. `check_bound` tạo Solver,
thêm constraints/bad, gọi `check` thật, rồi chỉ gọi `model` khi SAT.
Bad-set rỗng vẫn thêm `BoolVal(False)` và thực sự gọi solver.
SAT được giải mã về state/event; `make_trace` bổ sung sáu giá trị và quyền,
`replay_trace` kiểm lại bằng `step` và cạnh G2. Sau đó validator kiểm đúng
predicate vi phạm; một đường hợp lệ chưa chắc là counterexample hợp lệ.

SAT là có đường vi phạm encoding; UNSAT là không có trong bound đã mã hóa;
UNKNOWN là solver chưa quyết định. ERROR là lỗi ứng dụng, tách khỏi
`solver_status`. SAT nhưng replay hỏng vẫn giữ solver_status=SAT và status=ERROR.
Header `:status unknown` trong SMT-LIB không phải kết quả `check()`.

`reachable_depths` tính lại khoảng cách ngắn nhất. Cả hai graph có
`D=max shortest_distance(initial,s)=5`. Mọi bad-state reachable có đường
ngắn nhất không quá D. Graph total cho phép kéo dài tiền tố ngắn hơn D;
query kiểm bad tại mọi vị trí nên UNSAT tới D đủ cho P1-P4 hiện tại.
Không áp dụng cận reachability này để kết luận P5 hoặc hệ thống bất kỳ.

`check_safety_bmc` thử k=0 tăng từng 1, dừng tại SAT/UNKNOWN/ERROR hoặc D.
Chỉ gọi phản ví dụ ngắn nhất khi tất cả bound nhỏ hơn thực sự UNSAT.
Bound nhỏ hơn D chỉ cho `BOUNDED_NO_COUNTEREXAMPLE`, không suy ra HOLDS.
Mỗi query lưu bound, trạng thái, SMT-LIB và trace; timeout là 10.000 ms.

## 5. Hai lỗi và bằng chứng v0/v1

| Đại lượng | v0 | v1 |
|---|---:|---:|
| States reachable | 21 | 18 |
| Event transitions | 69 | 46 |
| Cặp R | 65 | 42 |
| D | 5 | 5 |
| Query Z3 trong một lần kiểm chứng đầy đủ | 20 | 24 |
| SAT / UNSAT / UNKNOWN | 1 / 19 / 0 | 0 / 24 / 0 |

P1/P5 vi phạm ở v0; P2-P4 thỏa. v1 thỏa cả năm trên mô hình.
P1 v0: k=0 UNSAT, k=1 SAT; `s0 --open_door--> s3` có
authenticated=False và door_open=True. v1 bổ sung guard xác thực.
P5 v0: prefix `s0 --admin_reset [True]--> s5`, cycle
`s5 --reset_retry--> s5`; reset_step=loop_start=1. v1 bỏ nhánh retry,
chỉ giữ reset_complete trong resetting, không dùng fairness để che lỗi.

Tổng 44 query Z3: 1 SAT, 43 UNSAT, 0 UNKNOWN, 0 lỗi ứng dụng. Các query
trong pytest hoặc lần chạy khác không cộng vào con số của một lần nghiệm thu.
P5 có `NOT_APPLICABLE/NOT_USED` ở cột BMC, không phải UNSAT.

Mô hình: [v0](../results/v0/model.json), [v1](../results/v1/model.json).
Kiểm chứng và SMT-LIB: [v0](../results/v0/verification.json),
[v1](../results/v1/verification.json); [CSV](../results/comparison.csv).
Hình: [P1](../results/g4/diagrams/counterexample_p1_v0.svg),
[P5](../results/g4/diagrams/counterexample_p5_v0.svg).

## 6. Sinh mã, đối chiếu và sơ đồ

Nguồn: [artifacts.py](../smartlock/artifacts.py), `generate_python`,
`audit_generated`, `diagram_views`, `render_view`, `build_artifacts`.
Generator chuyển initial, states, labels, event assumptions và transitions
JSON thành `INITIAL_STATE`, `STATES`, `LABELS`, `EVENT_INPUTS`, `TRANSITIONS`
cùng runtime tra bảng. Trùng khóa state/event nhưng khác đích gây ValueError
trước ghi file; không chọn ngẫu nhiên. Không viết lại guard/action thành
một chương trình nghiệp vụ riêng.

[v0](../generated/v0/smart_lock.py), [v1](../generated/v1/smart_lock.py) chỉ
import argparse/json, không cần model.py, toolkit, Z3 hoặc JSON bên ngoài.
`step` kiểm ID, event, quyền admin rồi tra bảng; sai thì InvalidEvent.
Sinh từ v0 vẫn giữ lỗi. Test copy một file sang thư mục trống và chạy
`python -I -S` xác nhận độc lập.

Audit so initial, mọi state/label và toàn bộ bảng cạnh, sau đó so mọi
state x 9 event x hai giá trị quyền với `model.step`. So toàn bảng còn bắt
cạnh thừa dùng event lạ. Các đường BFS đến từng state cũng được replay.

| Phiên bản | Trường hợp | Chấp nhận / từ chối | Cạnh khớp |
|---|---:|---:|---:|
| v0 | 378 | 125 / 253 | 69/69 |
| v1 | 324 | 82 / 242 | 46/46 |
| Tổng | 702 | 207 / 495 | 115/115 |

702 là phép đối chiếu hữu hạn, không phải số tests pytest. Cùng initial và
quan hệ bước cho phép quy nạp các chuỗi input hợp lệ tương ứng. Simulator
không có scheduler: bên gọi phải gửi reset_complete để tiến bước v1.
Không gửi input không tự trở thành cạnh chờ hợp lệ trong Kripke.

Bảy hình lấy từ graph tích hợp: hai graph đầy đủ, ba lát cắt chức năng,
hai trace phản ví dụ. Lát cắt không thay graph đầy đủ khi kiểm CTL.
Graphviz xuất DOT/SVG/PNG; initial được đánh dấu, lỗi tô đỏ, prefix P5 xanh
và cycle đỏ. Metadata kiểm PNG/SVG và cạnh nằm trong
[experiment_summary.json](../results/g4/experiment_summary.json),
[CSV tổng hợp](../results/g4/experiment_summary.csv),
[bảng state](../results/g4/state_legend.csv).

## 7. Kiểm thử và giới hạn

Bộ `tests/` có 199 trường hợp: 78 mô hình/BFS, 72 CTL/BMC và 49 mã sinh/sơ đồ.
Các nhánh UNKNOWN/ERROR hiếm có tests giả lập được đặt tên rõ; lần kiểm chứng
chính thức không gặp UNKNOWN. Tests v0 PASS xác nhận hành vi lỗi mong đợi,
không khẳng định v0 an toàn. Số 203 trong audit lịch sử gồm thêm 4 tests
tham chiếu tài liệu lớp, không phải dependency của bộ 199 tests hiện tại.

Lệnh cài đặt, chạy và kiểm thử ở [README, mục 6](../README.md#6-cài-đặt-chạy-và-kiểm-thử).
[Log kiểm chứng](../results/g3/verification.log),
[chạy simulator độc lập](../results/g4/standalone_examples.log),
[log pytest](../results/g5/pytest.log) và
[đối chiếu kết quả](../results/g5/evidence_audit.json) giữ số liệu thực nghiệm.
Các đường dẫn máy cũ trong bằng chứng là provenance, không phải dependency.

Giới hạn: trạng thái hữu hạn, input xác thực trừu tượng, action nguyên tử,
reset nội bộ có ưu tiên; chưa mô hình hóa mất điện, phần cứng, mạng hoặc
concurrency/thời gian thực. Chứng minh đúng năm đặc tả không có nghĩa an
toàn tuyệt đối. Nguồn toolkit và thông tin phân phối ở
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
