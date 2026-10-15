# G4 — Sinh mã Python, sơ đồ và đối chiếu thực nghiệm Smart Lock

## 1. Kết quả và phạm vi bàn giao

G4 dùng nguyên mô hình tích hợp G2 và bằng chứng CTL/BMC của G3. Đầu ra
là hai chương trình Python độc lập, bảy sơ đồ có cả SVG/PNG, bảng tổng
hợp và các tests đối chiếu. Không thêm chức năng, biến trạng thái hay
thuộc tính CTL; không viết lại BFS, logic nghiệp vụ hoặc engine Z3.

Kết quả chạy ngày 15/10/2026: **199/199 tests dự án PASS**, trong đó giữ
nguyên 150 tests G2/G3 và thêm 49 tests G4. Chạy riêng bốn tests Python
tham chiếu đã dùng ở G1: **4/4 PASS**. Tổng phạm vi G1–G4: **203 PASS,
0 FAIL**. Đây là số trường hợp pytest; 702 đối chiếu hữu hạn bên trong
audit là phép kiểm tra khác, không cộng thành 702 tests pytest.

| Phiên bản | States reachable | Transitions có event | Cặp quan hệ R | Độ sâu BFS lớn nhất |
|---|---:|---:|---:|---:|
| v0 | 21 | 69 | 65 | 5 |
| v1 | 18 | 46 | 42 | 5 |

R chỉ lưu cặp nguồn/đích. Hai event khác nhau có thể cùng cặp đó nên số
transition có event lớn hơn số cặp R. G4 giữ event để mô phỏng và gắn
nhãn sơ đồ; các số trên được đọc từ mô hình, không ép đủ 192 states.

## 2. File được thêm và sửa

| File/nhóm file | Vai trò |
|---|---|
| `smartlock/artifacts.py` | Sinh Python, đối chiếu toàn miền, trích sơ đồ, gọi Graphviz, tổng hợp dữ liệu G2/G3 |
| `tests/test_artifacts.py` | 49 trường hợp pytest mới, bao gồm chạy Python cô lập và kiểm tra sơ đồ thật |
| `generated/v0/smart_lock.py`, `generated/v1/smart_lock.py` | Hai đầu ra tự động; không sửa tay |
| `results/g4/experiment_summary.json` | Nguồn bằng chứng chi tiết: hash, đối chiếu, stdout chạy độc lập, CTL, danh mục node/edge và ảnh |
| `results/g4/experiment_summary.csv` | 10 dòng: 5 thuộc tính × 2 phiên bản, kèm số liệu mô hình và mã sinh |
| `results/g4/state_legend.csv` | Giải nghĩa ID, sáu biến và AP cho toàn bộ 39 state của hai phiên bản |
| `results/g4/diagrams/*.{dot,svg,png}` | Bảy sơ đồ, mỗi sơ đồ có nguồn DOT và hai định dạng ảnh |
| `results/g4/*.log` | Log sinh mã/ảnh, pytest dự án, tests G1, ví dụ chạy độc lập và nghiệm thu |
| `run.py` (sửa) | Thêm chế độ `--artifacts`, `--generated-dir`, `--dot`; giữ nguyên lệnh G2/G3 |
| `README.md` (sửa) | Tiến độ, hướng dẫn chạy G4 và liên kết bằng chứng |
| `docs/G3_GiaiThich.md` (sửa cuối file) | Cập nhật điểm dừng lịch sử sau khi G3 được duyệt |
| `docs/G4_GiaiThich.md` | Tài liệu này |

Giữ nguyên bốn module `model.py`, `kripke.py`, `ctl.py`, `bmc.py`, ba
file tests G2/G3, hai `model.json`, hai `verification.json` và bảng
`results/comparison.csv` của G3. Đối chiếu SHA-256 trước/sau được lưu
trong `results/g4/acceptance_checks.json`. Không chỉnh toolkit hay
requirements.txt để thêm thư viện Python ở G4.

## 3. Sinh code từ Kripke nghĩa là gì, vì sao cần?

Mô hình Kripke đã có tập state S, initial, quan hệ chuyển tiếp và labels.
G2 còn lưu event trên từng cạnh. Ta chuyển dữ liệu hữu hạn đó thành
các bảng Python và một hàm tra bảng. Ví dụ, cạnh G2 của v1:

```text
source=s1, event=open_door, target=s5
```

trở thành phần tử thật trong file được sinh:

```python
TRANSITIONS = {
    # ... các cạnh khác từ JSON ...
    ('s1', 'open_door'): 's5',
}
```

Khi gọi `step('s1', 'open_door')`, chương trình trả `'s5'`. Nó không
tự tính lại điều kiện mật khẩu hay tự sửa trạng thái. State ID là tên
ngắn cho bộ sáu giá trị; `state_values('s5')` trả bản sao dictionary của
bộ giá trị đó. Các ID chỉ có ý nghĩa trong phiên bản tương ứng: s5 của
v0 là resetting, còn s5 của v1 là cửa mở sau xác thực.

Sinh mã giúp nối mô hình đã kiểm chứng với chương trình mô phỏng có
thể chạy. Cùng một dữ liệu làm nguồn cho kiểm chứng, runtime và sơ đồ
giảm khả năng ba phần được viết tay khác nhau. Đây là simulator theo
bảng hữu hạn, chưa phải firmware điều khiển một khóa cửa vật lý.

## 4. Đầu vào và thuật toán sinh mã

`smartlock/artifacts.py::generate_python(model_path, destination)` nhận
đường dẫn JSON G2 và đường dẫn Python đầu ra; trả `None`, ghi file khi
đầu vào hợp lệ, phát sinh lỗi nếu phát hiện cạnh sai hoặc bất định.

Các dữ liệu được chuyển:

| Dữ liệu G2 | Literal Python được sinh |
|---|---|
| `version` | `VERSION` |
| Bytes của `model.json` | `SOURCE_MODEL_SHA256` để truy nguồn |
| `initial_states` (đúng một phần tử) | `INITIAL_STATE` |
| ID và sáu giá trị trong `states` | `STATES[id] = tuple` |
| `labels` của từng state | `LABELS[id] = tuple` |
| `event_assumptions` | `EVENT_INPUTS`, bao gồm yêu cầu xác thực admin |
| Các bộ `source,event,target` | `TRANSITIONS[(source,event)] = target` |

Tên/thứ tự sáu trường lấy từ dataclass `State` G2 qua `STATE_FIELDS`;
chín tên event dùng nguyên hằng `EVENTS` G2. Generator được phép import
mô hình để biết định dạng và kiểm tra miền. Hai chương trình **đã sinh**
chỉ import `argparse` và `json`, không import `smartlock`, toolkit hay Z3,
và không cần đọc lại JSON khi chạy.

Thuật toán từng bước:

1. Đọc JSON UTF-8, lấy ID và bộ sáu giá trị đúng thứ tự.
2. Kiểm tra ID duy nhất, đúng một initial, initial tồn tại và giá trị
   thuộc miền State G2. Không dùng invariant an toàn để loại state v0.
3. Duyệt mọi transition; kiểm tra nguồn/đích tồn tại và event thuộc G2.
4. Tạo bảng `(source,event) -> target`. Nếu cùng khóa có hai đích khác
   nhau, dừng bằng `ValueError("Nondeterministic transition ...")`.
   Cạnh lặp giống hệt chỉ có cùng một ý nghĩa; không chọn ngẫu nhiên.
5. Tuần tự hóa dữ liệu thành literal Python bằng `repr`; nối với mẫu
   `RUNTIME` chứa bộ tra bảng và CLI. Mẫu không chứa guard nghiệp vụ.
6. Chỉ sau khi kiểm tra xong mới tạo thư mục/file, ghi UTF-8 với LF.
   Cùng bytes JSON và cùng generator sinh cùng bytes Python; có test
   tái sinh xác nhận điều này.

Generator không phải bộ xử lý Kripke tổng quát. Nó dành cho đúng cấu
trúc JSON, sáu trường, chín event và điều kiện admin của Smart Lock này.

## 5. Các hàm của chương trình được sinh

Tên hàm dưới đây tồn tại trong **cả hai** file
`generated/v0/smart_lock.py` và `generated/v1/smart_lock.py`.

### `state_values(state)`

Input là state ID dạng string; output là dictionary gồm sáu giá trị.
Hàm kiểm tra ID thuộc bảng `STATES`, rồi ghép `STATE_FIELDS` với tuple.
ID không hợp lệ phát sinh `InvalidState`. Dictionary mới giúp bên gọi
không vô tình sửa bảng qua giá trị trả về.

### `step(state, event, *, admin_authenticated=False)`

Input là ID hiện tại, tên event và kết quả xác thực admin kiểu bool;
output là ID kế tiếp. Hàm thực hiện:

1. Từ chối giá trị quyền khác bool, ví dụ `1` hay `'yes'`.
2. Dùng `state_values` kiểm tra state tồn tại; kiểm tra event là string.
3. Đọc `EVENT_INPUTS[event]`. Nếu metadata yêu cầu admin mà input False,
   phát sinh `InvalidEvent("Admin verification is required")`.
4. Tra `TRANSITIONS[(state,event)]`; có khóa thì trả ID đích.
5. Thiếu khóa thì phát sinh `InvalidEvent`, nêu event và state.

Ví dụ v1: `step('s0','open_door')` bị từ chối;
`step('s1','open_door') == 's5'`. `admin_reset` luôn cần bool True,
kể cả sau `password_ok`. Quyền người dùng và quyền quản trị là hai
điều kiện riêng từ G2.

Hàm không sửa state của bên gọi. Sự kiện bị từ chối không tạo cạnh
self-loop và không được tính như một bước Kripke. Self-loop hợp lệ
như `wait` chỉ xuất hiện khi bảng G2 thực sự có cạnh đó.

### `main(argv=None)`

Đọc `--events` và `--admin-authenticated`; bắt đầu tại `INITIAL_STATE`,
gọi `step` theo thứ tự, in ID cùng sáu giá trị sau mỗi bước. Kết thúc
bình thường trả exit code 0; gặp event bị từ chối in `REJECTED` và trả
1. Cờ admin biểu diễn kết quả xác thực trong môi trường mô phỏng của
toàn chuỗi CLI, không phải một cơ chế kiểm tra mật khẩu admin thật.

## 6. Đối chiếu toàn bộ chương trình sinh với G2

`smartlock/artifacts.py::audit_generated(model, program)` nhận đối tượng
`SmartLockModel` G2 và file Python; output là dictionary bằng chứng
PASS/số trường hợp/hash/stdout, hoặc phát sinh lỗi ngay khi không khớp.

Hàm dùng `runpy.run_path` nạp namespace mà không chạy `main`, rồi:

1. So initial, tập ID, tập event, toàn bộ sáu giá trị và labels với G2.
2. So **tập cạnh nhúng đầy đủ** với các bộ G2. Phép so này bắt cả cạnh
   thừa dùng tên event ngoài chín tên đã biết, không chỉ cạnh bị thiếu.
3. Lặp mọi reachable state × chín event × `{False, True}` cho admin.
4. Kỳ vọng được tính bằng `smartlock/model.py::step` G2: thành công thì
   đổi State trả về thành ID, `InvalidEvent` thì kỳ vọng bị từ chối.
5. Gọi `step` của file sinh trên cùng input; so đích hoặc sự từ chối.
   Chỉ bắt đúng `InvalidEvent`, không che lỗi lập trình khác thành từ chối.
6. Thu tập bộ ba đã thực hiện, yêu cầu bằng đúng tập transition G2.
7. Chạy file bằng subprocess `python -I -S ... --events password_ok
   open_door`; kiểm tra exit code thật và lưu stdout/stderr.

`-I` cô lập các thiết lập môi trường Python, `-S` bỏ nạp site-packages.
Test `test_generated_file_runs_alone_with_isolated_python_and_no_site_packages`
còn copy duy nhất file sinh sang thư mục tạm rỗng rồi chạy tại đó,
chứng minh không cần các file trong dự án để mô phỏng.

| Phiên bản | Phạm vi đầy đủ | Chấp nhận đúng | Từ chối đúng | Cạnh phân biệt khớp |
|---|---:|---:|---:|---:|
| v0 | 21 × 9 × 2 = 378 | 125 | 253 | 69/69 |
| v1 | 18 × 9 × 2 = 324 | 82 | 242 | 46/46 |
| Tổng | 702 | 207 | 495 | 115/115 |

Số lần chấp nhận không bằng số cạnh vì hầu hết event có thể được gọi
với cả hai input admin. Riêng `admin_reset` chỉ chấp nhận khi True.
Ngoài miền event hữu hạn còn có tests chuỗi không biết và state ID sai;
mọi event không có trong bảng đều bị từ chối bằng cùng cơ chế tra khóa.

Tập state và toàn bộ quan hệ bước trùng nhau; do đó, với cùng chuỗi
input hợp lệ từ initial, có thể quy nạp theo độ dài chuỗi để kết luận
hai bên đi cùng state tại mỗi bước. Test còn replay đường BFS đến
**từng state reachable**, thay vì chỉ kiểm tra một đường thành công.

## 7. Minh họa năm chức năng và hai lỗi

Ví dụ mã sinh v1, dùng ID và các cạnh thật:

```text
Authentication + Door Control:
s0 --password_ok--> s1 --open_door--> s5 --close_door--> s0

Account Lockout (đúng ba lần liên tiếp):
s0 --password_bad--> s2 --password_bad--> s6 --password_bad--> s10
                 f=1                    f=2             f=3, locked_out

Alarm + Admin Recovery:
s10 --tamper--> s14 --admin_reset [admin_authenticated=True]--> s17
s17 --reset_complete--> s0
```

Sau hai lần sai rồi `password_ok`, failed_attempts trở về 0; tests còn
đóng cửa rồi nhập sai lại để xác nhận bắt đầu đếm từ 1. Alarm đóng cửa
và hủy xác thực. Đăng nhập thành công không cấp quyền admin.

Trong v0, generator phải giữ lỗi đã có trong đầu vào:

- P1: `s0 --open_door--> s3`, trong s3 `door_open=True` nhưng
  `authenticated=False`. File sinh v0 tái hiện đúng phản ví dụ G3.
- P5: prefix `s0 --admin_reset [True]--> s5`; cycle
  `s5 --reset_retry--> s5`, lặp vô hạn. Tests replay prefix, cạnh đóng
  chu trình và lặp thêm một lần; ý nghĩa vô hạn đến từ chu trình đã
  đóng và kết quả fixed-point G3, không từ việc chạy test vô hạn.

Trong v1, đầu vào đã sửa nên `s0/open_door` không có trong bảng. Với
**mọi** resetting state v1, bảng chỉ có `reset_complete -> s0`; cả
`wait` và `reset_retry` đều bị từ chối. Generator không tự vá lỗi v0
và không làm phát sinh bản logic nghiệp vụ thứ hai.

## 8. Tạo sơ đồ từ chính mô hình tích hợp

### `diagram_views(models, reports)` và `_part(version, edges, state_ids)`

Input là hai mô hình G2 và báo cáo G3; output là danh sách bảy cấu hình
sơ đồ. `_part` giữ nguyên ID, event và target, chỉ chọn tập con để vẽ.
Hai sơ đồ tổng thể chứa toàn bộ node và event edge; ba sơ đồ chức năng
là lát cắt/ví dụ từ mô hình tích hợp, không phải mô hình kiểm chứng mới.

| Sơ đồ | Cách lấy dữ liệu | Phạm vi thật |
|---|---|---|
| Kripke v0 | Toàn bộ mô hình v0 | 21 node, 69 event edge |
| Kripke v1 | Toàn bộ mô hình v1 | 18 node, 46 event edge |
| Authentication + Lockout | v1, chọn event password_ok/password_bad | 5 node, 6 cạnh |
| Door + Alarm | v1, phase normal, failed_attempts=0; chọn password_ok/open/close/tamper | 4 node, 7 cạnh |
| Admin Recovery | Mỗi phiên bản lấy đường BFS tới locked_out có alarm, rồi admin_reset và các cạnh đi ra resetting | v0: 6 node/7 cạnh; v1: 6 node/6 cạnh |
| Counterexample P1 | Trace G3 đã replay | 2 node, 1 cạnh |
| Counterexample P5 | Trace G3, giữ loop_start/reset_step | 2 node, 2 cạnh (prefix và self-loop) |

Các lát cắt bỏ bớt event để đọc rõ; không được dùng chúng để kết luận
CTL vì chúng không giữ toàn bộ các đường của graph tích hợp. Đặc biệt
không suy ra mọi trạng thái đều reset ngay từ sơ đồ ví dụ Admin Recovery.

### `dot_text(view, models, reports)`

Input là một cấu hình sơ đồ và dữ liệu gốc; output là chuỗi DOT. Hàm
gắn tên node bằng `version_stateID`; lấy giá trị thật để in nhãn. State
initial có hai viền và mũi tên `initial` từ một điểm quy ước. Điểm này
chỉ là ký hiệu đồ họa, không thêm state vào mô hình.

Chú giải: `A=authenticated`, `D=door_open`, `B=alarm`,
`U=admin_authorized`, `f=failed_attempts`; `N=normal`, `L=locked_out`,
`R=resetting`. Sơ đồ tổng thể dùng nhãn ngắn, tra sáu biến ở
`state_legend.csv`. Mã sN phải đi cùng version khi tra bảng.

Node thuộc `violating_states` P1/P5 G3 có viền/nền đỏ. Cạnh mở cửa
trái phép và reset_retry lỗi tô đỏ. Ở phản ví dụ P5, prefix tô xanh,
cycle tô đỏ và thêm `[cycle]`; vị trí cycle lấy từ `loop_start`, không
đoán theo tên state. Trace được `validate_counterexample` G3 kiểm tra
trước khi chuyển sang hình.

Nhiều event cùng nguồn/đích được gộp nhãn nhiều dòng trên một mũi tên
để giảm dày, không bỏ event. Tổng số mũi tên hình vì vậy có thể bằng
số cặp R, còn danh mục trong JSON vẫn giữ mọi transition có event.

### `resolve_dot(explicit)` và `render_view(view, models, reports, folder, dot)`

`resolve_dot` tìm executable theo thứ tự: tham số `--dot`, biến môi
trường `GRAPHVIZ_DOT`, PATH, bản portable tại `tmp/graphviz/*/bin/dot.exe`.
Không tìm được thì phát sinh lỗi rõ ràng, không giả vờ đã vẽ thành công.

`render_view` ghi DOT, gọi subprocess Graphviz thật hai lần với `-Tsvg`
và `-Tpng`, kiểm tra exit code/timeout, thu stderr. Sau đó parse XML SVG,
kiểm tra viewBox, chữ ký PNG và kích thước dương; trả metadata và đường
dẫn. Graphviz có tài liệu chính thức về [SVG output](https://graphviz.org/docs/outputs/svg/).

Bản Graphviz dùng nghiệm thu: **16.1.0** portable, tải từ
[trang tải chính thức](https://graphviz.org/download/), đối chiếu SHA-256
ZIP với file checksum công bố. Portable/cache nằm trong tmp bị Git bỏ
qua, không phải dependency Python và không cần để chạy simulator đã sinh.

### Danh mục ảnh và kiểm tra khả năng đọc

- Kripke v0: [SVG](../results/g4/diagrams/kripke_v0.svg), [PNG](../results/g4/diagrams/kripke_v0.png) — 2304 × 2256 px.
- Kripke v1: [SVG](../results/g4/diagrams/kripke_v1.svg), [PNG](../results/g4/diagrams/kripke_v1.png) — 2311 × 1769 px.
- Authentication + Lockout: [SVG](../results/g4/diagrams/authentication_lockout.svg), [PNG](../results/g4/diagrams/authentication_lockout.png) — 816 × 1051 px.
- Door + Alarm: [SVG](../results/g4/diagrams/door_alarm.svg), [PNG](../results/g4/diagrams/door_alarm.png) — 807 × 1051 px.
- Admin Recovery: [SVG](../results/g4/diagrams/admin_recovery.svg), [PNG](../results/g4/diagrams/admin_recovery.png) — 913 × 1411 px.
- P1 v0: [SVG](../results/g4/diagrams/counterexample_p1_v0.svg), [PNG](../results/g4/diagrams/counterexample_p1_v0.png) — 716 × 661 px.
- P5 v0: [SVG](../results/g4/diagrams/counterexample_p5_v0.svg), [PNG](../results/g4/diagrams/counterexample_p5_v0.png) — 772 × 691 px.

Đã mở xem cả bảy PNG và kiểm tra nhãn/initial/cạnh lỗi; Graphviz trả
0 cảnh báo cho cả bảy. Tests còn kiểm node thật và event label trong
SVG. Đồ thị tổng thể vẫn dày do số cạnh thật; nên dùng SVG phóng lớn
hoặc phụ lục, sơ đồ chức năng trong phần trình bày chính. Chưa dàn
trang PDF A4 ở G4 nên không tuyên bố mọi chữ sẽ đọc được nếu ép cả
graph tổng thể vào một hình nhỏ trong báo cáo.

## 9. Tổng hợp thực nghiệm, CTL và bound

`build_artifacts(results_dir, generated_dir, dot_path=None)` điều phối:

1. `load_g2_model` nạp snapshot và yêu cầu khớp đúng BFS/guard/action G2.
   Kiểm version, hash mô hình, statistics, đúng năm công thức trong báo
   cáo G3; replay phản ví dụ có sẵn. Không lập bộ states mới cho G4.
2. Sinh từng Python, chạy audit đầy đủ; chỉ ghi PASS khi audit thành công.
3. Đọc trực tiếp kết quả `ctl`, `bmc`, checked_bounds và solver_outcomes
   từ `verification.json` G3; ghép với statistics và số đo audit G4.
4. Ghi bảng state, render bảy sơ đồ; ghi CSV/JSON và in log.

Hàm trả summary dictionary. SHA-256 của mô hình, báo cáo G3 và file sinh
nằm trong summary để truy nguyên đầu vào. CSV có 10 dòng thực nghiệm,
không gán trước P1/P5 phải sai; status lấy từ báo cáo thật. JSON còn chứa
toàn trace và các bộ edge dùng để vẽ.

`run.py::main(argv)` là điểm vào CLI: parse tham số, kiểm tra
`--artifacts` không ghép với `--verify`, `--events`, `--max-bound` hoặc
một version riêng; sau đó import muộn `build_artifacts`, truyền đường
dẫn và trả 0 khi toàn bộ quy trình thành công. Ví dụ `main(['--artifacts'])`
sinh cả v0/v1; tổ hợp sai như `--artifacts --verify` bị argparse từ chối.
Các nhánh mô phỏng G2 và kiểm chứng G3 vẫn dùng các hàm cũ.

| Thuộc tính, công thức | Phương pháp | v0 | v1 | Bound G3 / phản ví dụ |
|---|---|---|---|---|
| P1 `AG(door_open -> (authenticated AND NOT locked_out))` | Toàn bộ reachable states + BMC/Z3 | VIOLATED | HOLDS | v0 k=0 UNSAT, k=1 SAT; v1 k=0..5 UNSAT. CE v0 s0 → s3, open_door |
| P2 `AG(locked_out -> attempts_eq_3)` | Toàn bộ reachable states + BMC/Z3 | HOLDS | HOLDS | Cả hai k=0..5 UNSAT, không có CE |
| P3 `AG(alarm -> NOT door_open)` | Toàn bộ reachable states + BMC/Z3 | HOLDS | HOLDS | Cả hai k=0..5 UNSAT, không có CE |
| P4 `AG(resetting -> admin_authorized)` | Toàn bộ reachable states + BMC/Z3 | HOLDS | HOLDS | Cả hai k=0..5 UNSAT, không có CE |
| P5 `AG(resetting -> AF idle)` | CTL least fixed-point trên đồ thị đầy đủ | VIOLATED | HOLDS | Không có bound BMC; CE v0 prefix s0 → s5, cycle s5 → s5 |

G3 đã gọi solver 44 lần trong lần nghiệm thu: v0 1 SAT/19 UNSAT, v1
24 UNSAT; tổng 1 SAT/43 UNSAT/0 UNKNOWN, 0 lỗi ứng dụng. G4 **tái sử
dụng** kết quả đó, lệnh `--artifacts` không gọi Solver.check. Tests G3
khi chạy lại vẫn gọi solver theo các bài test tương ứng; không cộng
những lần gọi của tests vào 44 query của lần kiểm chứng đã lưu.

D=5 là khoảng cách ngắn nhất lớn nhất từ initial tới mọi reachable
state, đủ để phát hiện mọi bad-state reachable của P1–P4. Không dùng
D=5 để suy ra liveness P5. P5 dựa trên AF fixed-point và phản ví dụ chu
trình; trạng thái sinh ra giữ nguyên cả khả năng lặp này trong v0.

## 10. Tests và bằng chứng có thể tái lập

`tests/test_artifacts.py` có fixture `outputs` copy dữ liệu G2/G3 vào
thư mục tạm, sinh mã/ảnh thật ở đó; không ghi lại bằng chứng G2/G3.
Các nhóm test chính:

- Initial, state, labels, hash và imports; chạy độc lập trong thư mục rỗng.
- Toàn miền state/event/admin, so cả bảng nhúng để bắt cạnh thiếu/thừa.
- Năm chức năng, lần nhập sai thứ ba, chuỗi nhiều bước, mọi đường BFS.
- Replay cả hai counterexample v0; kiểm mọi resetting v1 chỉ có complete.
- State/event/quyền sai, phát hiện bất định trước khi ghi file, target không tồn tại.
- Tái sinh cùng bytes; cấy cạnh `backdoor` vào bản sao để bảo đảm audit bắt được.
- Bảy sơ đồ có node/edge thật, SVG có nhãn event, PNG hợp lệ, P5 giữ prefix/cycle.
- Bảng tổng hợp lấy đúng G2/G3, giữ nguyên bytes đầu vào, CLI phân biệt giai đoạn.

Môi trường nghiệm thu: Python 3.14.2, pytest 9.1.1, Z3 5.1.0,
Graphviz 16.1.0, Windows. Chạy từ thư mục gốc dự án:

```powershell
$pythonExe = 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe'
& $pythonExe -X utf8 run.py --artifacts
& $pythonExe -X utf8 -m pytest --color=no -p no:cacheprovider -v
& $pythonExe -I -S generated/v0/smart_lock.py --events open_door
& $pythonExe -I -S generated/v1/smart_lock.py --events open_door
& $pythonExe -I -S generated/v1/smart_lock.py --events password_ok open_door
& $pythonExe -I -S generated/v1/smart_lock.py --admin-authenticated --events password_bad password_bad password_bad tamper admin_reset reset_complete
```

Lệnh mở cửa ngay của v1 phải trả 1 (từ chối đúng), không phải lỗi môi
trường. Nếu dot chưa ở PATH, thêm `--dot <duong_dan_dot.exe>` cho lệnh
`--artifacts`; xem hướng dẫn README. Không cần cài dot để chỉ chạy file
Python đã sinh. Bộ tests G4 có kiểm render thật nên cần dot.

Bốn tests tham chiếu G1 được chạy riêng bằng lệnh đã ghi ở README;
đây là các tests Python Lab1/Lab6 thuộc nghiệm thu G1. Các bài C/ASan
khác trong references không thuộc bộ tests của Smart Lock này.

Log đã lưu:

- [Sinh mã/đối chiếu/render](../results/g4/artifacts.log).
- [199 tests dự án: 199 PASS, 0 FAIL](../results/g4/pytest.log).
- [Bốn tests tham chiếu G1: 4 PASS, 0 FAIL](../results/g4/g1_reference_pytest.log).
- [Các chuỗi chạy Python độc lập, exit code và stdout thật](../results/g4/standalone_examples.log).
- [Đối chiếu nguồn G2/G3, mở ảnh và tổng nghiệm thu](../results/g4/acceptance_checks.json).

## 11. Kết quả chứng minh được gì và còn giới hạn gì?

Đối chiếu hữu hạn chứng minh dữ liệu state/labels/initial và quan hệ
một bước của hai runtime sinh ra khớp G2 cho toàn miền đã nêu. Bằng
quy nạp, các chuỗi hợp lệ cũng khớp. G3 đã kiểm năm CTL trên graph đó;
G4 giữ nguyên graph, labels và input assumptions nên mô phỏng bảo toàn
các hành vi đã phân tích, kể cả hai lỗi cố ý của v0.

Không có sai khác transition, test thất bại hoặc lỗi render chưa xử
lý trong lần nghiệm thu. Giới hạn vẫn là mật khẩu/admin được trừu tượng
thành event/kết quả bool, action nguyên tử, hữu hạn reachable states,
không mô hình hóa mất điện/hỏng phần cứng/concurrency thực tế.

P5 nói về đường thực thi Kripke với event nội bộ reset được thực hiện.
Runtime không có đồng hồ hay scheduler: bên gọi phải gửi `reset_complete`
để tiến bước v1. Nếu bên gọi dừng gửi event hoặc bắt lỗi từ chối rồi
đứng yên ngoài mô hình, đó không phải một self-loop hợp lệ để áp dụng
kết quả CTL. Vì vậy G4 không chứng minh thời hạn reset theo giây trên
sản phẩm thật. Không có fairness mới được thêm để che lỗi v0.

Graphviz là công cụ ngoài cần có khi tái sinh ảnh/tests G4; ảnh đã lưu
và Python độc lập có thể mở/chạy ngay. Đồ thị tổng thể cần xem ở kích
thước lớn. Chưa biên soạn hoặc xuất PDF cuối kỳ; **dừng ở G4, chờ duyệt
trước G5**.

## 12. Mười lăm câu hỏi giảng viên có thể hỏi

**1. Đâu là bằng chứng đây là code sinh, không phải Smart Lock viết tay?**
`generate_python` đọc từng state/transition JSON rồi tuần tự hóa bảng.
`RUNTIME` chỉ tra bảng, không có nhánh tính số lần sai hay điều khiển
cửa. Test tái sinh byte-for-byte và hash truy nguồn cho phép kiểm lại.

**2. File được sinh có cần import model.py không?** Không. Chỉ có
argparse/json; bảng được nhúng. Test copy một file sang thư mục trống,
chạy Python với -I -S vẫn thành công.

**3. Tại sao dùng ID s0, s1 thay vì đối tượng State?** ID là cách mã hóa
ngắn gọn một state hữu hạn. `STATES` và `state_values` ánh xạ về đủ sáu
giá trị, được đối chiếu toàn bộ với G2. Không thêm biến nghiệp vụ thứ bảy.

**4. Nếu một state và event có hai đích thì sao?** Generator phát hiện
khóa trùng có target khác và phát sinh ValueError trước khi ghi file.
Smart Lock hiện tại xác định theo input đã nêu; không chọn ngẫu nhiên.

**5. Tại sao admin_authenticated không phải state thứ bảy?** Đây là
input xác thực của lần gọi admin_reset, đã có trong giả định G2.
Kết quả lưu ở biến admin_authorized của state resetting; metadata
EVENT_INPUTS bảo đảm gọi thiếu quyền bị từ chối.

**6. Sai event có giữ nguyên state thành một self-loop không?** Hàm
phát sinh InvalidEvent và không trả state kế tiếp. Đó là từ chối input,
không là cạnh mô hình. Self-loop wait/reset_retry chỉ có khi bảng chứa.

**7. Kiểm vài đường đi có đủ gọi là nhất quán không?** Chưa đủ. Audit
so tập cạnh đầy đủ và toàn bộ 702 bộ state/event/admin. Các đường ví dụ
và replay BFS là bằng chứng bổ sung giúp hiểu hoạt động.

**8. 702 phép so khác 115 transition như thế nào?** 702 tính mọi state,
event và hai giá trị quyền, kể cả input bị từ chối. 115 là tổng số bộ
ba nguồn/event/đích hợp lệ phân biệt của hai phiên bản.

**9. Làm sao chắc không có cạnh thừa với tên event lạ?** Ngoài lặp chín
event, audit so toàn bộ TRANSITIONS nhúng với tập cạnh G2. Test thêm
một cạnh backdoor vào bản sao xác nhận audit phát hiện được.

**10. Vì sao v0 sinh ra vẫn sai?** Sinh mã bảo toàn hành vi đầu vào,
không phải tự sửa lỗi. V0 cần giữ cạnh mở cửa không xác thực và chu
trình reset_retry để minh họa lỗi; v1 sinh từ graph đã sửa.

**11. Một self-loop reset_retry chứng minh P5 sai thế nào?** Có prefix
từ initial tới resetting rồi chu trình không chứa idle. Có thể lặp
chu trình vô hạn, nên AF idle tại resetting sai. P5 yêu cầu mọi đường,
không chỉ tồn tại đường reset_complete.

**12. Vì sao không dùng sơ đồ chức năng để kiểm CTL?** Lát cắt cố ý
bỏ event/cạnh để dễ nhìn; bỏ một nhánh có thể thay đổi nghĩa A trong
AG/AF. CTL G3 dùng graph tích hợp đầy đủ, các hình chức năng chỉ giải thích.

**13. Tại sao số transitions khác số mũi tên hay số cặp R?** Nhiều
event có thể nối cùng nguồn/đích. R bỏ nhãn event; hình gộp các tên
trên một mũi tên. Bảng dữ liệu vẫn giữ mọi event transition.

**14. Có thể dùng D=5 để kết luận reset luôn hoàn tất không?** Không.
D đủ cho bad-state safety reachable hiện tại. Vòng lặp vô hạn cần
phân tích liveness bằng fixed-point/lasso như G3; không thêm bound giả
cho P5 trong bảng G4.

**15. V1 PASS có nghĩa firmware ngoài đời an toàn chưa?** Chỉ kết luận
được trên simulator và mô hình cùng giả định. Cần đặc tả/kiểm chứng
thêm nếu triển khai phần cứng, thời gian thực hoặc concurrency. G4
không tự mở rộng phạm vi để tuyên bố những bảo đảm đó.
