# G2 — Giải thích mã nguồn và mô hình Smart Lock

Trạng thái: **G2 đã được người dùng duyệt; kết quả dưới đây là bàn giao G2**.
G3 đã được triển khai riêng, xem `G3_GiaiThich.md`.
Thiết kế gốc là `G1_ThietKe.md`, đã được người dùng duyệt. Không bổ sung
biến trạng thái hoặc chức năng ngoài thiết kế đó.

## 1. G2 đã làm gì và chưa làm gì?

Đã triển khai đủ năm chức năng trên một kiểu trạng thái và một bộ quy
tắc tích hợp; chạy BFS sinh toàn bộ phần reachable riêng cho v0 và v1;
xuất JSON; kiểm tra cấu trúc và bất biến dữ liệu cơ bản; chạy unit tests.

Chưa viết CTL checker, BMC/Z3, lasso checker, bộ replay phản ví dụ từ
solver, chương trình Python sinh độc lập, sơ đồ hoặc PDF. Năm công thức
CTL trong G1 giữ nguyên, sẽ triển khai ở G3. Việc G2 kiểm tra tính nhất
quán của state không được ghi thành kết quả kiểm chứng năm công thức.

## 2. Các file đã viết

| File | Trách nhiệm |
| --- | --- |
| `smartlock/__init__.py` | Đánh dấu package, không chứa logic nghiệp vụ. |
| `smartlock/model.py` | State, miền giá trị, AP, guard/action, hai cấu hình, sinh các bước khả thi. |
| `smartlock/kripke.py` | Nạp lớp toolkit, BFS, lưu cạnh có event, đường đi khám phá, kiểm tra dữ liệu và xuất JSON. |
| `run.py` | CLI sinh mô hình và mô phỏng chuỗi event bằng chính hàm step. |
| `tests/test_model.py` | Unit tests cho năm chức năng, miền trạng thái, quyền admin và hai lỗi cố ý. |
| `tests/test_kripke.py` | Tests BFS, đồ thị, AP, dữ liệu xuất và CLI. |
| `requirements.txt` | Chỉ cần pytest ở G2; runtime mô phỏng dùng standard library. |
| `pytest.ini` | Giới hạn test mặc định vào `tests/`, không tự chạy lab C/ASan. |
| `docs/G2_GiaiThich.md` | Tài liệu đang đọc. |

Đã cập nhật README để chạy lại, và trạng thái duyệt trong tài liệu G1.
Không chỉnh sửa mã hoặc dữ liệu trong `references/` và `toolkit/`.

Đầu ra đã sinh:

- `results/v0/model.json`, `results/v1/model.json`.
- `results/g2/model_generation.log`: log CLI sinh mô hình.
- `results/g2/pytest.log`: log đầy đủ từng trường hợp kiểm thử.
- `results/g2/simulation_examples.log`: lệnh, output và exit code của tám ví dụ.

## 3. Kiểu State hoạt động ra sao?

`State` là `@dataclass(frozen=True)` với đúng sáu trường:

```text
(authenticated, failed_attempts, door_open, alarm, phase, admin_authorized)
```

`frozen=True` ngăn việc gán lại trực tiếp một trường. Khi một action cần
thay đổi state, `dataclasses.replace()` tạo state mới. State cũ vẫn nguyên,
nên có thể dùng làm khóa dictionary/set khi BFS kiểm tra trùng lặp.

Equality/hash của dataclass dùng cả sáu giá trị. Hai object State có cùng
giá trị được xem là một trạng thái dù được tạo ở hai lần gọi hàm khác
nhau. Các tên `s0`, `s1` chỉ phục vụ hiển thị sau khi đã khám phá.

`State.__post_init__()` kiểm tra miền dữ liệu: bốn Boolean phải đúng kiểu
bool, bộ đếm là int từ 0 đến 3, pha thuộc normal/locked_out/resetting.
True không được chấp nhận làm bộ đếm dù Python coi bool là lớp con int.

Hàm này **không loại bỏ trạng thái sai nghiệp vụ**, ví dụ cửa mở khi chưa
xác thực. Nếu constructor cấm sẵn trạng thái đó, lỗi v0 sẽ bị che mất.
Tính đúng nghiệp vụ phải đến từ guard/action và được kiểm tra riêng.

`INITIAL_STATE = State()` có giá trị:

```text
(False, 0, False, False, normal, False)
```

## 4. Các hàm quan trọng trong model.py

### labels(state)

Trả về frozenset các AP đúng tại state. Các Boolean được đọc trực tiếp;
`locked_out` so sánh phase, `attempts_eq_3` so sánh bộ đếm, `idle` yêu cầu
toàn bộ state bằng INITIAL_STATE. Nhãn không phụ thuộc ID.

Ví dụ state bị khóa có nhãn locked_out và attempts_eq_3. State resetting
không được tự suy ra admin_authorized; AP này phải đọc trường quyền thật.
Một state không có AP nào đúng có labels rỗng là hoàn toàn hợp lệ.

### step(state, event, version, *, admin_authenticated=False)

Đây là hàm mô phỏng một bước, đồng thời là nguồn quy tắc dùng cho BFS.
Hàm kiểm tra version và kiểu kết quả xác thực admin trước khi xử lý:

1. Nếu đang resetting, chỉ nhận reset_complete; riêng v0 nhận thêm reset_retry.
2. Nếu không resetting, xét các guard của mật khẩu, cửa, tamper, admin reset và wait.
3. Guard đúng thì action trả State mới; guard sai thì ném InvalidEvent.

Không phải thử mọi nhánh rồi chọn state tùy ý. Mỗi cặp state/event với
kết quả quyền đã xác định có tối đa một kết quả.

Các guard/action đã cài đặt:

| Chức năng / sự kiện | Guard | Action |
| --- | --- | --- |
| F1: password_ok | normal, không alarm, chưa xác thực, cửa đóng | authenticated=True, failed_attempts=0 |
| F1–F2: password_bad | Như trên, bộ đếm dưới 3 | Tăng lên tối đa 3; chỉ đặt locked_out khi giá trị mới bằng 3 |
| F3: open_door v1 | normal, không alarm, cửa đóng, đã xác thực | door_open=True |
| F3: close_door | normal và cửa đang mở | door_open=False, authenticated=False |
| F4: tamper | Không resetting | alarm=True, door_open=False, authenticated=False; giữ bộ đếm và pha |
| F5: admin_reset | Không resetting và admin_authenticated=True | resetting, lưu admin_authorized=True, đóng cửa và hủy phiên; giữ alarm/bộ đếm |
| F5: reset_complete | resetting | Trả INITIAL_STATE, xóa cả alarm, bộ đếm và quyền đã lưu |
| wait | Không resetting | Giữ nguyên state |

Các biến không ghi trong action được giữ nguyên bởi replace().

Ba lần sai liên tiếp được hiểu là ba lần thử sai không có lần xác thực
thành công/reset hoàn tất xen giữa. wait không xóa bộ đếm. Khi xác thực
thành công, bộ đếm về 0; mở/đóng cửa xong rồi nhập sai sẽ bắt đầu từ 1.

### Quyền admin được thiết lập rõ ràng như thế nào?

```python
resetting = step(
    INITIAL_STATE, "admin_reset", "v1", admin_authenticated=True
)
```

admin_authenticated là kết quả xác thực quản trị được trừu tượng hóa từ
môi trường; chỉ guard của admin_reset chấp nhận kết quả True rồi lưu
admin_authorized vào state. Thiếu đối số, False hoặc chỉ đăng nhập người
dùng thông thường đều không đủ quyền reset. Các giá trị 0, 1, None, chuỗi
không được dùng thay Boolean.

Không thêm trường quyền admin thứ bảy vào State. Đối số trên là đầu vào
của sự kiện, còn admin_authorized là bằng chứng lưu lại trong quá trình
reset. Không triển khai cơ sở dữ liệu/mật khẩu admin thật. Cờ CLI
--admin-authenticated biểu diễn cùng giả định, không phải giải pháp bảo
mật triển khai thực tế.

### successors(state, version)

Lần lượt thử các tên event trong EVENTS theo thứ tự cố định. Mỗi lần gọi
chính step; nếu gặp InvalidEvent thì bỏ qua event đó, nếu thành công thì
yield cặp `(event, next_state)`.

Riêng ứng viên admin_reset truyền admin_authenticated=True một cách
tường minh: cạnh này nghĩa là yêu cầu đã xác thực quản trị thành công.
JSON lưu điều kiện ấy ở event_assumptions. Yêu cầu chưa xác thực bị từ
chối nên không có cạnh, đặc biệt không có self-loop từ chối trong reset.
Các lỗi khác ngoài InvalidEvent không bị nuốt âm thầm.

## 5. BFS tự sinh trạng thái từng bước

build_model(version) không nhận một danh sách state hay đồ thị khai báo
sẵn. Hàm chỉ khởi tạo INITIAL_STATE, sau đó gọi successors để sinh state.

Các cấu trúc dữ liệu dễ nhớ:

- queue: deque chứa state đã phát hiện nhưng chưa xét hết sự kiện.
- state_ids: ánh xạ State đầy đủ sang ID, nhận diện trùng theo sáu giá trị.
- states: ánh xạ ID sang dữ liệu State để xuất và đọc lại.
- transitions: giữ riêng từng bộ ba source/event/target.
- parents, distances: ghi cạnh phát hiện lần đầu và độ sâu BFS.
- graph: lớp KripkeStructure của toolkit giữ S, S0, R và L.

Trong mỗi vòng lặp:

1. popleft lấy một state từ đầu queue.
2. successors xét các sự kiện, kiểm tra guard, thực hiện action.
3. Nếu next_state chưa có trong state_ids: gán ID, thêm vào states/graph,
   lưu parent/depth và thêm cuối queue.
4. Dù target là state cũ hay mới, vẫn lưu cạnh có event và cặp trong R.
5. Lặp tới khi queue rỗng, nghĩa là không còn state reachable chưa mở rộng.

Không xét tích Descartes đủ 192 tổ hợp; không thêm state theo một danh
sách mong muốn; không bỏ state vi phạm nghiệp vụ khỏi BFS. Test quan sát
thực tế mỗi state được gọi successors đúng một lần trong quá trình xây.

Ví dụ vài lần mở rộng đầu tiên của **v1**:

- Bắt đầu: states chỉ có s0, queue chỉ có INITIAL_STATE.
- Lấy s0: password_ok sinh s1; password_bad sinh s2; open_door bị từ chối;
  tamper sinh s3; admin_reset đã xác thực sinh s4; wait quay lại s0.
- Lấy s1: open_door sinh s5; các đích alarm/reset/chờ đã biết không bị thêm trùng.
- Lấy s2: password_bad sinh s6 có bộ đếm 2; password_ok quay về s1;
  còn tamper/admin_reset sinh các tổ hợp phù hợp với bộ đếm 1.
- Tiếp tục lấy các state theo FIFO. Khi xét s6, password_bad sinh s10:
  bộ đếm bằng 3, pha locked_out.

Vì thứ tự EVENTS cố định và dict giữ thứ tự thêm, ID và JSON ổn định
giữa các lần chạy. ID khác nhau giữa v0/v1 vẫn có thể biểu diễn cùng giá
trị; phải so sáu trường khi so sánh hai mô hình.

## 6. Các hàm trong kripke.py và việc dùng toolkit

`_load_toolkit()` nạp đúng file ch1_models/kripke.py được cung cấp bằng
importlib. Không sao chép lớp đó và không thay đổi toolkit. Vị trí file
được tính từ __file__, không phụ thuộc thư mục đang đứng khi chạy CLI.

`Transition` chỉ có source, event, target, là dữ liệu của cạnh, không
phải ba biến trạng thái mới. SmartLockModel gom các thành phần của một
mô hình tích hợp, không tạo mô hình riêng cho từng F.

`path_to(target)` đi ngược parents rồi đảo thứ tự để trả đường đi BFS
từ s0 tới target. Nó giúp giải thích state xuất hiện từ đâu; chưa phải
bộ replay counterexample từ solver của G3.

`statistics()` đếm state, reachable qua API toolkit, cạnh có event, cặp
trong R và độ sâu BFS lớn nhất. `to_dict()` gom đầy đủ dữ liệu; `write_model()`
tạo thư mục đầu ra và lưu UTF-8 JSON dễ đọc.

Lớp toolkit dùng set đích nên R gộp hai sự kiện cùng cặp đầu/cuối.
transitions riêng của project giữ lại tên cả hai, phục vụ mô phỏng và
các bước sau. Ví dụ ở alarm, tamper và wait đều có thể giữ nguyên state.

## 7. Ví dụ cụ thể đã chạy

Thứ tự tuple dưới đây giữ nguyên thứ tự sáu biến State. ID thuộc **v1**.

### Xác thực rồi mở cửa

```text
s0 = (False, 0, False, False, normal, False)
  --password_ok-->
s1 = (True,  0, False, False, normal, False)
  --open_door-->
s5 = (True,  0, True,  False, normal, False)
```

### Khóa đúng lần sai thứ ba

```text
s0  --password_bad--> s2  : failed_attempts=1, phase=normal
s2  --password_bad--> s6  : failed_attempts=2, phase=normal
s6  --password_bad--> s10 : failed_attempts=3, phase=locked_out
```

Tại s10, password_ok/password_bad/open_door đều bị từ chối. Bộ đếm không
tăng tiếp lên 4. Test test_third_consecutive_bad_password_causes_lockout
xác nhận từng lần thử trên cả v0 và v1, không chỉ kiểm tra state cuối.

### Admin phục hồi sau lockout và alarm

```text
s10 --tamper--> s14
s14 --admin_reset [admin_authenticated=True]--> s17
s17 --reset_complete--> s0
```

Ở s17, admin_authorized=True, failed_attempts=3, alarm=True, cửa đóng.
Chỉ sau reset_complete mới xóa toàn bộ dữ liệu về s0. Thiếu điều kiện
xác thực admin thì không đi được từ s14 sang s17.

## 8. Hai lỗi v0 được giữ lại đúng thiết kế

BUG-01: guard open_door của v0 bỏ điều kiện authenticated. Trong dữ liệu
thật, s0 đi thẳng tới s3 với door_open=True và authenticated=False.
Ba state có cửa mở trái phép ứng với bộ đếm 0, 1, 2 được BFS giữ lại.
v1 không có ba state này.

BUG-02: mỗi state resetting của v0 có thêm reset_retry quay lại chính
nó. v0 có 8 self-loop như vậy; vẫn có lựa chọn reset_complete. v1 có
8 state resetting nhưng từng state chỉ có cạnh reset_complete về s0.

G2 đã kiểm tra sự tồn tại/vắng mặt các cạnh này và chạy ví dụ hữu hạn.
Chưa gọi kết quả đó là kiểm chứng AF hoặc chứng minh đường lặp vô hạn
bằng thuật toán lasso; phần đó thuộc G3.

Tests của v0 đạt nghĩa là v0 có đúng hành vi lỗi được mong đợi, cùng các
chức năng còn lại đúng thiết kế. Không có nghĩa v0 là một hệ thống an toàn.

## 9. Kết quả sinh mô hình thực tế

Số liệu lấy từ lần chạy run.py, có JSON và log tương ứng:

| Đại lượng | v0 | v1 |
| --- | ---: | ---: |
| States | 21 | 18 |
| Reachable states | 21 | 18 |
| Transitions có tên sự kiện | 69 | 46 |
| Cặp (source,target) phân biệt trong R | 65 | 42 |
| State có pha normal | 11 | 8 |
| State có pha locked_out | 2 | 2 |
| State có pha resetting | 8 | 8 |
| Độ sâu BFS lớn nhất | 5 | 5 |

Vì alarm có thể đi kèm lockout/reset, không cộng số state theo AP để
suy ra tổng state: các tập nhãn có thể chồng nhau. Bảng theo phase ở
trên là phân hoạch nên có thể cộng.

Toàn bộ danh sách states, transitions và labels nằm trong hai model.json;
không rút gọn hoặc bỏ cạnh chờ trong các file dữ liệu. Mỗi file cũng có
initial_states, relation, event_assumptions, statistics và kết quả kiểm tra.

## 10. Kiểm tra cấu trúc và các bất biến cơ bản

structural_checks() có 11 kiểm tra: không trùng giá trị state; initial
đúng; tập state toolkit khớp; tất cả reachable; R total; nhãn khớp dữ
liệu; không trùng cạnh có event; một state/event chỉ một đích; toàn bộ
guard/action khớp các cạnh đã ghi; R đúng là phép bỏ tên event khỏi các
cạnh; đường parents khớp độ sâu.

basic_invariants() ghi rõ state vi phạm nếu có, cho bốn điều kiện:

1. Bộ đếm nằm trong 0–3.
2. Pha locked_out đi kèm bộ đếm 3.
3. State có alarm thì cửa đóng.
4. State resetting có admin_authorized=True.

Cả 11 kiểm tra cấu trúc và 4 điều kiện dữ liệu đều đạt ở cả hai phiên
bản trong lần chạy G2. Chúng không được dùng làm guard hoặc bộ lọc BFS.
Hai lỗi cố ý không bị bốn điều kiện này che khuất: lỗi mở cửa không qua
xác thực và cạnh reset_retry có tests riêng xác nhận.

run.py kiểm tra các kết quả này trước khi ghi JSON. Mã kiểm tra không
có parser CTL, phép tính AF, lasso hoặc lời gọi Z3. Dùng các bất biến
dữ liệu ở G2 không thay thế việc kiểm chứng P1–P5 ở G3.

## 11. Tests và log thực tế

Lệnh đã chạy:

```powershell
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe' -X utf8 -m pytest --color=no -p no:cacheprovider -v
```

Kết quả lần chạy cuối: **78 passed in 0.23s**, Python 3.14.2, pytest 9.1.1. Số 78 là
số trường hợp sau khi parameterize v0/v1 và các đầu vào, không phải 78
hàm kiểm thử viết tay. Xem results/g2/pytest.log để đối chiếu từng tên test.

Các nhóm tests gồm miền sáu biến, nhãn độc lập, mật khẩu đúng/sai, đúng
lần thứ ba, ngắt chuỗi sai bởi lần đúng, chờ không xóa bộ đếm, chặn
lockout, cửa, alarm, reset thiếu/đủ quyền, reset ưu tiên, hai lỗi v0,
BFS không trùng, total, giữ event song song, độ sâu, JSON và CLI.

Tám ví dụ CLI đã được chạy thật trong simulation_examples.log: mở cửa
hợp lệ; ba lần sai; mật khẩu đúng bị từ chối sau lockout; reset thiếu
quyền; reset có quyền sau alarm/lockout; lỗi mở cửa v0; reset_retry v0;
wait bị từ chối khi reset ở v1. Các trường hợp bị từ chối có exit code 1
đúng mong đợi, không bị ghi thành lỗi chạy test.

README có lệnh cài pytest và chạy lại mô hình/tests. G2 không cần Z3,
Graphviz hoặc thư viện tạo PDF. Không dùng kết quả G1 để cộng vào 78.

## 12. Câu hỏi giảng viên có thể hỏi

**1. State và ID khác nhau thế nào?** State là sáu giá trị nghiệp vụ.
ID s0/s1 chỉ là tên hiển thị được BFS gán sau khi khám phá.

**2. Vì sao dùng frozen dataclass?** Để state không bị đổi trực tiếp sau
khi đã dùng làm khóa set/dict; replace tạo object mới khi thực hiện action.

**3. BFS có thực sự sinh state hay chỉ duyệt JSON?** build_model bắt đầu
chỉ bằng INITIAL_STATE, gọi successors/step để tạo state mới. JSON là
đầu ra, không phải đồ thị đầu vào.

**4. Vì sao không sinh đủ 192 state?** 192 là tích miền giá trị. Nhiều
tổ hợp không có đường từ initial; ví dụ normal với bộ đếm 3 không được
guard/action của cả hai cấu hình sinh ra.

**5. Khóa đúng lần thứ ba nằm ở dòng logic nào?** Trong nhánh password_bad,
tính attempts mới rồi đặt phase=locked_out khi attempts == 3. Không khóa
dựa trên giá trị cũ bằng 3 hoặc ngay khi bộ đếm bằng 2.

**6. Một lần nhập đúng có xóa chuỗi sai không?** Có, action password_ok
đặt failed_attempts=0. wait không xóa chuỗi sai.

**7. Người dùng đăng nhập đúng có tự reset được không?** Không. authenticated
là quyền người dùng thường. admin_reset còn yêu cầu đầu vào xác thực quản
trị True, sau đó mới lưu admin_authorized.

**8. Có kiểm tra mật khẩu admin thật chưa?** Chưa và không thuộc phạm vi.
Giống password_ok/password_bad, kết quả xác thực quản trị được trừu tượng
hóa thành đầu vào sự kiện đã được môi trường xác định.

**9. R total nghĩa là gì?** Mỗi state có ít nhất một kế tiếp: wait ngoài
reset và reset_complete trong reset. Total không có nghĩa mỗi event đều
được chấp nhận ở mỗi state.

**10. Tại sao không thêm self-loop cho mọi state?** Self-loop trong reset
cho phép mãi không hoàn tất. v1 chỉ có reset_complete; v0 cố ý có reset_retry.
Giả định tiến triển của v1 nằm ngay trong quan hệ chuyển tiếp.

**11. Vì sao số cạnh có event lớn hơn |R|?** Tamper và wait ở alarm cùng
một cặp state đầu/cuối. R là set cặp nên gộp, nhưng transitions giữ cả hai tên.

**12. Nhãn admin_authorized có được suy từ resetting không?** Không, labels
đọc trường admin_authorized. Có thể tạo state hợp lệ về miền nhưng sai
nghiệp vụ để kiểm tra sự độc lập ấy; BFS không tự sinh nó khi guard đúng.

**13. Tại sao không chặn cửa mở trái phép trong constructor?** Làm vậy
che lỗi mô hình v0. Constructor chỉ bảo đảm miền hữu hạn; guard/action và
kiểm chứng mới quyết định đúng nghiệp vụ.

**14. 78 tests đạt có chứng minh năm CTL không?** Không. Tests kiểm tra
các yêu cầu G2, cấu trúc và lỗi cố ý. G3 mới kiểm chứng các công thức trên
mô hình đầy đủ bằng thuật toán đã thống nhất và BMC/Z3 cho safety.

**15. Phần nào tái sử dụng toolkit, phần nào nhóm viết?** Dùng nguyên
KripkeStructure để chứa S/S0/R/L và kiểm tra reachability/path. Nhóm viết
State, guard/action, BFS sinh states, cạnh gắn event, kiểm tra và xuất JSON.

## 13. Điểm bàn giao

G2 đã hoàn thành các đầu ra được yêu cầu và có bằng chứng chạy thực tế.
Nhóm có thể đọc theo thứ tự model.py -> test_model.py -> build_model()
trong kripke.py -> hai model.json -> tests BFS -> log chạy.

Điểm dừng G2 này đã được người dùng duyệt trước khi triển khai G3.
Các nhận xét “chưa triển khai G3” trong tài liệu mô tả đúng thời điểm
bàn giao G2; kết quả mới nằm trong tài liệu G3, không sửa lại log G2.
