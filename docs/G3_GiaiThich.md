# G3 — Kiểm chứng CTL và BMC/Z3 cho Smart Lock

Trạng thái: **đã thực hiện G3, dừng chờ duyệt trước G4**.
Mọi kết quả trong tài liệu được đối chiếu với JSON và log chạy thực tế.
Không thay đổi logic nghiệp vụ, sáu biến hoặc hai lỗi cố ý của G2.

## 1. Phạm vi và việc tái sử dụng mô hình G2

G3 dùng cùng SmartLockModel, State, labels(), guard/action và BFS của G2.
Mỗi phiên bản chỉ có một mô hình tích hợp; CTL và BMC cùng đọc mô hình đó,
không có danh sách states riêng hoặc quy tắc nghiệp vụ SMT viết lại.

load_g2_model() đọc snapshot model.json, gọi chính build_model() G2 và
đối chiếu toàn bộ to_dict() với snapshot: states, labels, events, R,
initial, depth và thống kê phải khớp. Nếu sai thì báo lỗi, không ghi đè
snapshot để ép kết quả. Cách này kiểm tra nguồn gốc mô hình rồi tái sử
dụng object SmartLockModel G2 cho cả hai phương pháp.

Hai snapshot được giữ nguyên byte, có SHA-256 trong verification.json:

- v0: `1c2480b813aeb640d4cdcedeffd98521444945e3941fb0b56f0c765d752f7e26`.
- v1: `d0d83b24961a5de7803f8c9023ebd9df6770528d2b2d7c0c6843bfd16cdde085`.

smartlock/model.py cũng không sửa. G2 vẫn có 21 states/69 event edges ở
v0, 18 states/46 event edges ở v1. Không tạo đủ 192 tổ hợp, không bỏ state
vi phạm khỏi mô hình. Phần mới chỉ phục vụ kiểm chứng đúng năm công thức.

## 2. CTL, AG và AF là gì?

CTL (Computation Tree Logic) diễn tả điều kiện trên các nhánh thực thi của
hệ thống. Từ một state có thể có nhiều sự kiện, nên có nhiều cách tiếp
diễn. Công thức CTL cho biết cần xét mọi cách hay chỉ một cách.

- A: mọi đường tiếp diễn.
- G: ở mọi vị trí trên đường, kể cả state hiện tại.
- F: tại một vị trí hữu hạn trong tương lai, được phép là vị trí hiện tại.
- AG φ: trên mọi đường, φ luôn đúng.
- AF φ: trên mọi đường, cuối cùng phải có φ; chỉ có một đường tới φ là chưa đủ.

Kripke của bài này có quan hệ total: mỗi state có ít nhất một kế tiếp,
nên các đường thực thi có thể kéo dài vô hạn. Ngoài reset có wait;
trong reset v1 chỉ có reset_complete. Ngữ nghĩa này theo G1 và được
đối chiếu với [tài liệu CTL của NuSMV](https://nusmv.fbk.eu/papers/sttt_j/html/node3.html).

Safety nói “điều xấu không xảy ra”. Một đường hữu hạn tới cửa mở trái
phép đủ bác bỏ safety. Liveness nói “điều cần thiết cuối cùng xảy ra”.
Quan sát reset chưa xong sau vài bước chưa đủ bác bỏ liveness, vì nó có
thể hoàn tất ở bước sau; cần lý do chứng minh có thể tránh hoàn tất mãi.

P5 là **AG(resetting -> AF idle)**:
ở mọi state resetting đạt được, mọi nhánh từ đó phải tới idle. Lượng từ A
của AF quan trọng vì v0 vẫn có nhánh hoàn tất nhưng có cả nhánh retry mãi.

## 3. AP lấy từ dữ liệu nào?

Hàm labels() G2 giữ nguyên; không tin nhãn do người dùng tự viết trong
snapshot nếu nó không khớp các biến thật.

| AP | Điều kiện |
| --- | --- |
| authenticated | state.authenticated |
| door_open | state.door_open |
| alarm | state.alarm |
| locked_out | state.phase == locked_out |
| attempts_eq_3 | state.failed_attempts == 3 |
| resetting | state.phase == resetting |
| admin_authorized | state.admin_authorized, độc lập với phase |
| idle | Toàn bộ sáu giá trị bằng INITIAL_STATE |

Đặc biệt, không định nghĩa locked_out bằng bộ đếm 3, không định nghĩa
admin_authorized bằng resetting. Hai cách đó sẽ biến P2/P4 thành điều
đúng sẵn, che mất lỗi cập nhật hoặc kiểm tra quyền.

Mỗi kết quả CTL ghi danh sách antecedent_states để kiểm tra tiền đề có
thật sự đạt được. Số state kích hoạt P1–P5 lần lượt là v0: 4,2,8,8,8;
v1: 1,2,8,8,8. Vì vậy không có thuộc tính nào đúng chỉ do tiền đề không
bao giờ xuất hiện. Các tập này có thể chồng nhau, không cộng để đếm S.

## 4. Đúng năm đặc tả, ý nghĩa và phương pháp

| ID | Công thức | Ý nghĩa / loại | Cách kiểm tra |
| --- | --- | --- | --- |
| P1 | AG(door_open -> (authenticated AND NOT locked_out)) | Cửa mở cần xác thực và không lockout; safety F1/F2/F3 | Bad state trên đồ thị + BMC/Z3 |
| P2 | AG(locked_out -> attempts_eq_3) | Lockout phải có đúng ba lần sai; safety F2 | Bad state trên đồ thị + BMC/Z3 |
| P3 | AG(alarm -> NOT door_open) | Alarm thì cửa đóng; safety F3/F4 | Bad state trên đồ thị + BMC/Z3 |
| P4 | AG(resetting -> admin_authorized) | Reset cần bằng chứng quyền admin; safety F5 | Bad state trên đồ thị + BMC/Z3 |
| P5 | AG(resetting -> AF idle) | Mọi reset phải hoàn tất trên mọi nhánh; liveness F5 | CTL least fixed-point, lasso khi sai |

P2 là một chiều: không tự bắt được lỗi bộ đếm đã bằng 3 nhưng chưa
locked_out. Unit test G2 về lần sai thứ ba vẫn cần giữ nguyên. P1/P3
giả định bước điều khiển là nguyên tử: tamper đóng cửa và hủy phiên trong
cùng một action. P4 giả định kết quả xác thực quản trị là đầu vào tin cậy.
P5 dựa trên ưu tiên bước reset nội bộ của v1, không dựa vào fairness ẩn.

FORMULAS chỉ chứa chuỗi phục vụ báo cáo. Code không parse hoặc thực thi
chuỗi; bad_state và AF được viết riêng cho đúng nhóm công thức này.

## 5. Safety trên toàn bộ đồ thị: P1–P4

bad_state(state,pid) kiểm tra phủ định mệnh đề bên trong AG:

```text
bad1 = door_open AND (NOT authenticated OR locked_out)
bad2 = locked_out AND NOT attempts_eq_3
bad3 = alarm AND door_open
bad4 = resetting AND NOT admin_authorized
```

check_ctl() xét toàn bộ states reachable G2, không chỉ vài đường thử.
Không có bad state thì AG đúng trên toàn mô hình. Nếu có, chọn bad state
có khoảng cách BFS nhỏ nhất, lấy parents để dựng đường đi và replay nó.
Ở v0, bad1 có s3, s8, s13; s3 đạt ngay sau một bước nên được chọn.
Không có bad2/bad3/bad4 ở cả hai phiên bản. v1 cũng không có bad1.

Kết quả logic dùng HOLDS/VIOLATED, không dùng SAT/UNSAT vì đây là kiểm
tra đồ thị Python, chưa phải lời gọi Z3. BMC có các trạng thái riêng.

## 6. P5: tính fixed-point và dựng lasso

Đặt Succ(s) là các state kế tiếp theo R. Tính tập state thỏa AF idle:

```text
Z0 = {s | idle(s)}
Zn+1 = Zn ∪ {s | Succ(s) ⊆ Zn}
dừng khi Zn+1 = Zn
```

Điều kiện total được kiểm tra trước để tránh trường hợp tập kế tiếp
rỗng làm “mọi kế tiếp thuộc Z” đúng một cách rỗng. AF ở đây dùng **tất cả**
kế tiếp; không dùng điều kiện “có ít nhất một kế tiếp thuộc Z”.

Lập luận: state idle đã thỏa ngay. Nếu mọi kế tiếp chắc chắn tới idle,
thì state hiện tại cũng chắc chắn tới idle sau thêm một bước. Lấy điểm
bất động nhỏ nhất bằng cách bắt đầu từ idle, không bắt đầu từ toàn bộ S.

Kết quả thực tế:

- v0: Z0={s0}; vòng tiếp không thêm state, kích thước lịch sử là [1].
  Cả 8 state resetting đều nằm ngoài AF idle.
- v1: vòng đầu thêm cả 8 state resetting vì chúng chỉ có kế tiếp s0;
  kích thước lịch sử [1,9], sau đó ổn định. Cả 8 state resetting thuộc Z.

Các state khác vẫn có wait nên phần lớn không thuộc AF idle. Điều đó
không làm P5 sai ở v1 vì P5 chỉ đòi AF idle khi tiền đề resetting đúng.

Khi reset nằm ngoài Z, tại điểm bất động phải còn ít nhất một kế tiếp
ngoài Z. Theo các cạnh như vậy sẽ tránh idle; vì đồ thị hữu hạn, cuối
cùng lặp lại một state. Tách đường đã đi thành prefix hữu hạn và một
chu trình không rỗng: đó là lasso, biểu diễn một đường vô hạn hợp lệ.

Lasso v0 đã replay:

```text
prefix: s0 --admin_reset [admin_authenticated=True]--> s5
cycle:  s5 --reset_retry--> s5
infinite path: s0, s5, s5, s5, ...
reset_step = 1; loop_start = 1
```

Từ step 1 trở đi không có idle. s0 được phép là idle trong prefix trước
khi reset bắt đầu. Nếu reset_complete đi về s0 rồi bắt đầu reset khác,
không được dùng đường đó làm bằng chứng một reset trước không hoàn tất.
Tests có trường hợp bác bỏ lasso đi qua idle sau reset.

## 7. BMC mã hóa đường đi ra sao?

Mỗi bước dùng x_i là số nguyên chỉ ID state G2, e_i là số nguyên chỉ tên
event trong EVENTS. Sáu biến thật không bị thay thế bằng bộ state khác;
ID chỉ là mã hóa một-một của chính State đã sinh. Ánh xạ ngược được dùng
khi giải mã counterexample và in đủ sáu biến.

Với bound k, có k+1 state x0..xk và k event e0..e(k-1):

```text
I(x0) = x0 = id(s0)
Domain(xi) = 0 <= xi < |S|
Domain(ei) = 0 <= ei < |EVENTS|
T(xi,ei,xi+1) = OR cho từng (src,event,dst) trong transitions G2:
               xi=id(src) AND ei=id(event) AND xi+1=id(dst)

BMC_j(k) = I(x0) AND domains
           AND AND(i=0..k-1) T(xi,ei,xi+1)
           AND OR(i=0..k) bad_j(xi)
```

Điều kiện bad lấy từ dữ liệu State bằng bad_state(). Không thêm P1–P4
làm giả định đúng vào I hoặc T. T giữ event chứ không chỉ cặp R, nên vẫn
phân biệt tamper và wait cùng giữ nguyên một state.

Ở k=0 không có event/chuyển tiếp, nhưng vẫn có initial/domain/bad để kiểm
tra state ban đầu. k là số bước chuyển, không phải số state trên trace.

Ví dụ P1 v0:

- ID bad là 3,8,13; e(open_door)=2 theo EVENTS.
- k=0: x0=0, nhưng bad yêu cầu x0 thuộc {3,8,13}; Z3 trả UNSAT.
- k=1: T cho phép (x0,e0,x1)=(0,2,3), x1 là bad; Z3 trả SAT.
- Giải mã: s0 --open_door--> s3, bước vi phạm 1. Do k=0 đã thật sự UNSAT,
  phản ví dụ này ngắn nhất theo số bước chuyển.

Khi tập bad rỗng, code thêm BoolVal(False) vào solver và **vẫn gọi check()**.
Do đó các kết quả UNSAT P2–P4 không phải nhãn suy đoán hoặc bỏ qua solver.
SMT-LIB tương ứng có `(assert false)`, dễ kiểm tra lại.

Đây là BMC trên đồ thị đã liệt kê đầy đủ, đúng lựa chọn G1 để mã hóa dễ
hiểu và đối chiếu. Nó không phải kỹ thuật symbolic extraction từ mọi
chương trình Python, cũng không giải quyết state explosion.

## 8. SAT, UNSAT, UNKNOWN và ERROR

Theo [hướng dẫn Z3 Python chính thức](https://microsoft.github.io/z3guide/programming/Z3%20Python/Introduction/),
check() trả sat khi có phép gán thỏa ràng buộc, unsat khi không có,
unknown khi chưa quyết định được. Cách diễn giải trong bài:

| Trạng thái query | Ý nghĩa và xử lý |
| --- | --- |
| SAT | Có đường vi phạm trong bound; lấy model, giải mã, replay; chỉ công bố SAT hợp lệ sau replay. |
| UNSAT | Không có phản ví dụ trong bound được mã hóa; chưa tự suy ra toàn cục nếu chưa đủ ngưỡng. |
| UNKNOWN | Chưa kết luận, ghi reason_unknown(); dừng tăng bound để không bỏ qua lỗi nông chưa kiểm tra xong. |
| ERROR | Lỗi ứng dụng: input, tạo solver, check, giải mã hoặc replay. Không phải kết quả thứ tư của Z3. |

Mỗi query ghi riêng solver_called, solver_status, status, reason và
counterexample. Nếu chưa gọi check thì solver_status=None, không được
ghi UNSAT. Nếu Z3 trả SAT nhưng replay lỗi, solver_status vẫn SAT còn
status là ERROR và không xuất counterexample như bằng chứng hợp lệ.

solver.model() chỉ được gọi sau SAT. Mỗi query đặt timeout 10.000 ms;
nếu solver trả UNKNOWN thì lưu nguyên lý do. Không có UNKNOWN thực tế
trong lần nghiệm thu; tests nhánh này dùng lớp giả lập có ghi rõ tên.

Kết luận của chuỗi BMC là một tầng khác:

- VIOLATED: đã có SAT và phản ví dụ replay đúng.
- HOLDS: UNSAT tới completeness threshold của nhóm safety hiện tại.
- BOUNDED_NO_COUNTEREXAMPLE: UNSAT tới bound nhỏ hơn threshold; holds=None.
- INCONCLUSIVE: gặp UNKNOWN; holds=None.
- ERROR: lỗi thực thi, không khẳng định thuộc tính đúng/sai từ BMC.

JSON lưu smt2 của từng query từ solver.to_smt2(). Header `:status unknown`
do hàm xuất SMT-LIB tạo là thông tin đầu vào, **không phải kết quả check()**.
Kết quả thật đọc ở solver_status. Tests đã nạp lại các query SAT/UNSAT
vào solver mới và đối chiếu kết quả để kiểm tra bằng chứng có thể dùng lại.

## 9. Completeness Threshold: vì sao D=5 đủ cho safety?

reachable_depths() tính lại khoảng cách ngắn nhất từ initial trên R.
Cả hai phiên bản có:

```text
D = max(shortest_distance(s0,s) với s reachable) = 5
```

Một đường đạt độ sâu 5 là ba password_bad, tamper, rồi admin_reset.
Ví dụ v1 kết thúc ở s17: failed_attempts=3, alarm=True, resetting=True.

Nếu một bad state đạt được thì có đường ngắn nhất tới nó dài không quá
D. Vì R total, mọi tiền tố ngắn hơn D có thể kéo dài thành đúng D bước,
và công thức BMC vẫn kiểm tra bad ở mọi vị trí 0..D. Vì vậy UNSAT tại D
sau khi xác nhận mô hình đầy đủ và mã hóa đúng đủ loại trừ mọi bad state
reachable của P1–P4 trên **mô hình này**.

D là một completeness threshold đủ dùng cho nhóm invariant trạng thái,
không khẳng định ngưỡng nhỏ nhất cho từng công thức. Không dùng |S|=21/18
như giá trị D; cận thô |S|-1 cũng đủ nhưng không cần thiết ở bài này.

check_safety_bmc() chạy từ 0 tới D, dừng ngay khi gặp SAT đã replay,
UNKNOWN hoặc ERROR. Nếu chỉ giới hạn k=0, P1 v0 trả
BOUNDED_NO_COUNTEREXAMPLE dù kiểm tra đồ thị biết nó sai ở bước 1.

Ngưỡng reachability này không chứng minh P5: một chu trình có thể bị lặp
vô hạn dù không khám phá state mới. P5 dùng fixed-point toàn đồ thị, không
nhận kết luận từ việc BMC safety UNSAT tới 5.

## 10. Từng hàm Python quan trọng

### Các hàm mới trong kripke.py

**load_g2_model(path) -> SmartLockModel.** Input là đường dẫn JSON G2.
Đọc snapshot, dùng đúng build_model của G2 và đối chiếu toàn bộ dữ liệu.
Output là object chung cho CTL/BMC; snapshot sai/cũ gây ValueError. Ví dụ
file v0 phải khớp 21 states, 69 event edges và cùng labels/giá trị.

**make_trace(model,state_ids,events,pid) -> dict.** Nhận n+1 ID và n event,
đọc dữ liệu State thật rồi tạo steps chứa số bước, ID, sáu biến, labels,
incoming_event và điều kiện admin. Không tự tìm đường đi. Ví dụ [s0,s3]
và [open_door] tạo trace P1 v0 hai state.

**replay_trace(model,trace) -> True hoặc exception.** Kiểm tra initial,
dữ liệu/nhãn từng row, điều kiện quyền, sự tồn tại cạnh có event và kết
quả step() G2. Nó xác nhận đường đi; chưa quyết định đường đó có vi phạm
P1 hoặc có lasso P5 hay không. Event hoặc state bị thay đổi sẽ bị từ chối.

### Các hàm trong ctl.py

**bad_state(state,pid) -> bool.** Nhận State và một trong P1–P4, trả phủ
định mệnh đề trạng thái bằng AP thật. Ví dụ door_open=True nhưng
authenticated=False làm bad1=True. P5 bị từ chối, không coi resetting là bad.

**reachable_depths(model) -> dict ID/depth.** BFS trên R từ initial,
chỉ thêm state lần đầu để lấy khoảng cách ngắn nhất; không đọc depth có
sẵn rồi tin ngay. Ví dụ v1 s10 sâu 3, s17 sâu 5.

**validate_model(model) -> None hoặc exception.** Kiểm tra cấu trúc G2
và so khoảng cách tính lại với distances. Mô hình thiếu cạnh, không
total, nhãn sai hoặc thiếu phần reachable không được dùng để khẳng định
thuộc tính đúng toàn cục. Không dùng bất biến cần chứng minh làm bộ lọc.

**validate_counterexample(model,trace,pid) -> True hoặc exception.** Gọi
replay_trace trước. Với safety, kiểm tra có bad và violation_step là bước
bad đầu tiên. Với P5, kiểm tra reset_step, loop_start, chu trình không
rỗng/khép kín và không có idle sau điểm reset. Ví dụ thiếu quyền admin
hoặc chu trình đi qua idle thì không được công bố làm bằng chứng.

**af_idle_fixed_point(model) -> (set AF, history).** Input graph total.
Bắt đầu từ các state idle, lặp phép mở rộng mọi kế tiếp đều trong tập,
trả tập cố định và từng vòng lặp để giải thích. Ví dụ v1 trả 9 state,
lịch sử kích thước [1,9]. Không gọi Z3 trong hàm này.

**_prefix_trace(model,target,pid) -> dict.** Dùng path_to() G2 dựng tiền
tố BFS tới target. Ví dụ tới s3 v0 chỉ có open_door. Đây là helper riêng
để check_ctl không lặp code tạo trace.

**_liveness_trace(model,target,af_idle) -> dict.** Input là một resetting
nằm ngoài AF. Ghép tiền tố BFS rồi lần lượt theo cạnh ngoài AF, dùng
dictionary seen để tìm ID lặp. Output là lasso có reset_step và loop_start,
đã replay/kiểm tra. Ví dụ s0,s5,s5 của v0.

**check_ctl(model) -> dict P1..P5.** Validate mô hình; quét bad cho bốn
safety, tính AF cho P5; dựng và kiểm tra bằng chứng khi sai; thêm công
thức, ý nghĩa, loại và danh sách tiền đề. Output HOLDS/VIOLATED là kết
quả trên toàn đồ thị hữu hạn, không phải kết quả SAT/UNSAT giả của Z3.

### Các hàm trong bmc.py

**transition_constraint(model,x,e,y) -> biểu thức Z3.** Mã hóa đúng các
cạnh có event G2 thành disjunction; không tự tạo thêm cạnh. Tests dùng
solver liệt kê hết các bộ ba SMT rồi so sánh chính xác với transitions.

**encode_path(model,k) -> (states,events,constraints).** Tạo k+1 Int state
và k Int event, cùng initial/domain/T cho từng bước. Ví dụ k=1 có x0,e0,x1.
Hàm chưa gọi Solver và chưa thêm phủ định thuộc tính. Bound âm/bool/số
thực bị từ chối.

**check_bound(model,pid,k) -> dict query.** Đây là nơi gọi Solver(),
set(timeout), add(ràng buộc đường đi), add(bad), to_smt2(), check().
SAT mới gọi model(), giải mã Int ID thành State/event và kiểm tra
counterexample. UNSAT/UNKNOWN được xử lý riêng; exception thành ERROR
nhưng giữ nguyên kết quả solver đã trả nếu có. Ví dụ P1 v0 k=1 trả SAT
và trace hai state; P2 v1 k=0 vẫn thật sự check() rồi trả UNSAT.

**check_safety_bmc(model,pid,max_bound=None) -> dict kết luận.** Tính D,
gọi check_bound theo thứ tự 0,1,...; không nhảy bound. Dừng tại bằng
chứng hoặc kết quả chưa kết luận/lỗi. Output gồm checked_bounds, checks,
ngưỡng, holds, kết luận và cờ shortest_counterexample. Ví dụ P1 v0 dừng
ở [0,1]; P1 v1 chạy đủ [0,1,2,3,4,5]. Bound yêu cầu lớn hơn D được giới
hạn ở D vì đã đủ cho nhóm safety này.

### Các hàm điều phối trong run.py

**_trace_text(trace) -> str.** Định dạng ID/event và chỉ số vi phạm/chu
trình để đọc log/CSV. Dữ liệu chi tiết vẫn có trong steps ở JSON.

**_verify(args) -> exit code.** Nạp/đối chiếu snapshot, chạy CTL và bốn
chuỗi BMC, kiểm tra hai phương pháp có đồng ý không, ghi verification.json
và comparison.csv, in từng query cùng bằng chứng. Lỗi hoặc UNKNOWN trả
exit code 1; thuộc tính VIOLATED có bằng chứng hợp lệ vẫn là lần kiểm
chứng chạy thành công, không phải lỗi thực thi. Không hardcode kết quả
mong đợi của v0/v1 vào thuật toán.

**main(argv) -> exit code.** Giữ chế độ sinh/mô phỏng G2 khi không có
--verify. Chế độ G3 mới nhận --max-bound; không nhận cùng --events.
Z3 được import muộn ở nhánh kiểm chứng, không sửa API mô phỏng G2.

## 11. Kết quả nghiệm thu thực tế v0/v1

HOLDS nghĩa thỏa trên mô hình hữu hạn; VIOLATED có bằng chứng đã replay.

| P | Phương pháp | v0 | Bound/CE v0 | v1 | Bound/CE v1 |
| --- | --- | --- | --- | --- | --- |
| P1 | Reachable bad + BMC/Z3 | VIOLATED | k=0 UNSAT, k=1 SAT; s0 --open_door--> s3 | HOLDS | k=0..5 đều UNSAT, không CE |
| P2 | Reachable bad + BMC/Z3 | HOLDS | k=0..5 đều UNSAT, không CE | HOLDS | k=0..5 đều UNSAT, không CE |
| P3 | Reachable bad + BMC/Z3 | HOLDS | k=0..5 đều UNSAT, không CE | HOLDS | k=0..5 đều UNSAT, không CE |
| P4 | Reachable bad + BMC/Z3 | HOLDS | k=0..5 đều UNSAT, không CE | HOLDS | k=0..5 đều UNSAT, không CE |
| P5 | CTL fixed-point | VIOLATED | Prefix s0->s5; cycle s5->s5; không gọi Z3 | HOLDS | Cả 8 reset thuộc AF idle; không gọi Z3 |

Không có kết quả bất ngờ phải thay đổi mô hình hoặc sửa dự đoán G1.
Các kết luận safety từ BMC và kiểm tra đồ thị đồng ý ở cả hai phiên bản.
V0 khác v1 đúng hai lỗi: thiếu guard xác thực và reset_retry cho phép lặp.

P1 v0 gồm các giá trị:

```text
s0 = (False,0,False,False,normal,False)
    --open_door-->
s3 = (False,0,True,False,normal,False)    bad1=True, violation_step=1
```

P5 v0 gồm các giá trị:

```text
s0 = (False,0,False,False,normal,False)
    --admin_reset, admin_authenticated=True-->
s5 = (False,0,False,False,resetting,True)
    --reset_retry--> s5 --reset_retry--> s5 ...
```

## 12. Những lần gọi Z3 và cách đọc bằng chứng

| Nhóm query trong lần chạy --verify --version both | Số lần check | SAT | UNSAT | UNKNOWN |
| --- | ---: | ---: | ---: | ---: |
| v0 P1: k=0,1 | 2 | 1 | 1 | 0 |
| v0 P2/P3/P4: mỗi P có k=0..5 | 18 | 0 | 18 | 0 |
| v1 P1/P2/P3/P4: mỗi P có k=0..5 | 24 | 0 | 24 | 0 |
| Tổng | 44 | 1 | 43 | 0 |

Có 0 lỗi ứng dụng ở lần nghiệm thu. JSON tách application_errors khỏi
solver_outcomes vì ERROR không phải phản hồi thứ tư của Z3.
Các lần gọi solver trong unit tests là các thí nghiệm riêng, không cộng
vào 44 query của lần nghiệm thu được lưu trong verification.log.

Đọc results/v0/verification.json hoặc v1 tương tự:

1. source_model_sha256 và g2_statistics xác định đúng mô hình đã kiểm.
2. ctl/Pj có formula, meaning, status, antecedent_states và counterexample.
3. bmc/Pj/checks có một record cho mỗi bound thực sự đã chạy, kèm
   solver_called, solver_status, status, reason, smt2 và model Z3 khi SAT.
4. counterexample/steps có initial, mọi state trung gian, incoming_event,
   dữ liệu sáu biến và điều kiện admin; violation_step hoặc loop_start
   chỉ rõ nơi làm bằng chứng.
5. P5 nằm trong ctl; không tạo bmc/P5 hoặc gán UNSAT cho nó.
6. safety_methods_agree phải True cho bốn kết quả đã kết luận đầy đủ.

comparison.csv có 10 dòng dữ liệu, một dòng cho mỗi cặp phiên bản/thuộc
tính, ghi phương pháp, kết luận CTL, kết luận BMC, bound và CE ngắn gọn.
P5 có NOT_APPLICABLE/NOT_USED ở các cột BMC/solver, không phải UNSAT.

## 13. Tests đã chạy

Lệnh: Python 3.14.2, Z3 5.1.0, pytest 9.1.1, chạy toàn bộ mặc định từ
pytest.ini, gồm nguyên hai file test G2 và file test_verification.py mới.

**150 PASS, 0 FAIL: 78 trường hợp G2 + 72 trường hợp G3.**
Log đầy đủ nằm tại results/g3/pytest.log. Nhóm mới kiểm tra:

- Năm CTL ở cả hai phiên bản, tiền đề reachable và kết quả trước/sau sửa.
- Bốn BMC so với CTL, shortest trace, k=0, domain và unroll không “nhảy” state.
- Solver liệt kê chính xác các event edges của G2, kể cả event song song.
- SAT/UNSAT bằng solver thật; tập bad rỗng vẫn có lời gọi check thật.
- Nạp lại SMT-LIB đã lưu để giải lại SAT/UNSAT.
- Bound nhỏ chỉ cho kết luận bounded; D đúng khoảng cách ngắn nhất.
- Fixed-point dùng mọi kế tiếp; lasso có prefix/cycle đúng; deadlock bị từ chối.
- Replay phát hiện đổi state, labels, event, điều kiện admin, chỉ số vòng
  hoặc bước vi phạm; đường hợp lệ chưa chắc là bằng chứng vi phạm.
- Snapshot G2 sai/thiếu cạnh không được dùng để tuyên bố an toàn toàn cục.
- CLI giữ nguyên snapshot G2 và ghi đủ 44 query trong một lần chạy nghiệm thu.

Tests UNKNOWN và ERROR dùng giả lập có tên test ghi rõ simulated. Không
khẳng định Z3 đã thực tế trả UNKNOWN trong lần nghiệm thu. Test lỗi
replay dùng SAT thật rồi làm hỏng trace để xác nhận giữ solver_status=SAT,
status=ERROR, không công bố phản ví dụ hỏng.

## 14. File tạo/sửa và cách chạy lại

File mới viết tay: smartlock/ctl.py, smartlock/bmc.py,
tests/test_verification.py, docs/G3_GiaiThich.md.

File sửa: smartlock/kripke.py chỉ thêm đối chiếu snapshot/trace/replay;
run.py thêm chế độ --verify và xuất kết quả; requirements.txt thêm
z3-solver; README và trạng thái duyệt trong G2_GiaiThich.md.
Không sửa model.py, hai file tests G2, snapshot G2, references hoặc toolkit.

Đầu ra mới: results/v0/verification.json, results/v1/verification.json,
results/comparison.csv, results/g3/verification.log, results/g3/pytest.log.
Không có file của G4/G5.

```powershell
$pythonExe = 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.14-64\python.exe'
& $pythonExe -m pip install -r requirements.txt
& $pythonExe -X utf8 run.py --verify --version both
& $pythonExe -X utf8 -m pytest --color=no -p no:cacheprovider -v
```

Chạy tại thư mục repo. Có thể chọn --version v0/v1. Nếu chưa có snapshot,
chạy run.py --version both để sinh G2 trước. Dùng --output-dir để chỉ thư
mục chứa hai snapshot và nơi lưu kết quả; --verify không ghi đè model.json.
--max-bound chỉ tác động safety BMC, không cắt đồ thị dùng cho CTL.

## 15. Câu hỏi giảng viên có thể hỏi

**1. AG và AF khác nhau thế nào?** AG kiểm tra luôn đúng ở mọi vị trí
trên mọi đường. AF yêu cầu trên mọi đường có một vị trí hữu hạn thỏa.
P1 dùng AG vì không được mở trái phép; P5 cần AF để bảo đảm kết thúc reset.

**2. Vì sao P1 là safety, P5 là liveness?** Tới cửa mở trái phép là tiền
tố hữu hạn đủ làm chứng P1 sai. Với P5, phải chứng minh một reset có thể
mãi không hoàn tất, được biểu diễn bằng chu trình tránh idle.

**3. AP có phải các tên s0/s1 không?** Không. ID chỉ định danh state.
labels() tính AP từ sáu biến, ví dụ locked_out từ phase và attempts_eq_3
từ failed_attempts. Hai nhãn đó phải độc lập để P2 có ý nghĩa.

**4. BMC hỏi tìm công thức đúng hay tìm vi phạm?** Mã hóa initial, các
transition và phủ định safety. SAT nghĩa tồn tại đường làm sai thuộc tính.
Không được thêm chính safety làm giả định đúng trước khi tìm phủ định.

**5. k=1 có một hay hai state?** Hai state x0,x1 và một event e0.
k là số chuyển tiếp. k=0 vẫn phải kiểm tra initial, không bỏ qua nó.

**6. Hàm nào thật sự gọi Z3?** check_bound() gọi Solver(), add() và
check(); SAT mới gọi model(). transition_constraint()/encode_path() chỉ
tạo biểu thức; check_ctl()/af_idle_fixed_point() không gọi solver.

**7. Vì sao UNSAT ở k=0 của P1 v0 chưa đủ?** Initial không vi phạm,
nhưng ngay một bước open_door đã tới s3. Vì vậy k=0 UNSAT và k=1 SAT
không mâu thuẫn, nó minh họa giới hạn bound.

**8. Làm sao biết counterexample ngắn nhất?** Thử k=0 rồi tăng từng 1,
dừng tại SAT đầu tiên sau khi mọi bound nhỏ hơn đều UNSAT. Nếu có
UNKNOWN ở bound nhỏ thì dừng, không bỏ qua rồi tự gọi trace sau là ngắn nhất.

**9. UNKNOWN và ERROR có giống UNSAT không?** Không. UNKNOWN là solver
chưa quyết định; ERROR là lỗi ứng dụng. Cả hai không cho bằng chứng vắng
vi phạm. solver_status được tách khỏi status của ứng dụng.

**10. Replay kiểm tra gì ngoài việc ID tồn tại?** Kiểm tra initial,
đúng state/labels, tên event, quyền admin, cạnh trong G2 và kết quả step()
đúng toàn bộ state đích. Sau đó còn kiểm tra predicate vi phạm hoặc lasso.

**11. Vì sao có reset_complete mà P5 v0 vẫn sai?** Vì AF đòi mọi đường
hoàn tất. Một lựa chọn reset_retry tự lặp đủ tạo đường không bao giờ về idle.
Kiểm tra “tồn tại đường hoàn tất” sẽ kiểm tra nhầm một thuộc tính yếu hơn.

**12. Fixed-point bắt đầu từ đâu?** Từ tập idle. Mỗi vòng thêm state có
mọi kế tiếp trong tập cũ. v0 chỉ có s0; v1 thêm 8 resetting. Không bắt
đầu từ toàn bộ S vì sẽ không tính đúng least fixed-point AF.

**13. Completeness threshold của bài là bao nhiêu, vì sao?** D=5 là
khoảng cách ngắn nhất lớn nhất từ initial tới mọi state reachable. Một
bad state nếu tồn tại sẽ có đường tới dài không quá 5; total cho phép
kéo dài tiền tố ngắn hơn, nên BMC với bad ở mọi vị trí đủ bao phủ safety.

**14. Có dùng D=5 để kết luận P5 không?** Không. Đi hết các state chưa
loại trừ khả năng lặp chu trình vô hạn. P5 cần fixed-point/lasso trên
đồ thị đầy đủ, không phải bad-state BMC của P1–P4.

**15. V1 thỏa cả năm có chứng minh khóa cửa ngoài đời an toàn không?**
Chỉ chứng minh các đặc tả đã chọn trên mô hình hữu hạn và giả định đã nêu.
Chưa mô hình hóa hỏng phần cứng, mất điện, xác thực thật hoặc mọi chi tiết
triển khai. Mô hình và encoding vẫn phải được hiểu, kiểm tra và giải thích.

## 16. Giới hạn, vấn đề còn tồn tại và điểm dừng

Không có lỗi chạy hoặc bất đồng CTL/BMC chưa giải quyết trong nghiệm thu.
Các giới hạn là giả định đã công bố: kết quả mật khẩu/admin trừu tượng,
action nguyên tử, reset nội bộ ưu tiên, miền trạng thái hữu hạn. BMC dùng
đồ thị đã BFS đầy đủ, không tuyên bố khả năng kiểm chứng tổng quát.

P2 vẫn cần test chức năng đúng lần thứ ba vì công thức một chiều. UNKNOWN
và các lỗi hiếm được kiểm tra bằng giả lập, không phải bằng chứng Z3 đã
gặp chúng trên mô hình nhỏ này. Báo cáo đã phân biệt rõ điểm đó.

Tại thời điểm bàn giao G3, chưa triển khai sinh mã độc lập/sơ đồ ở G4
hoặc PDF ở G5. Điểm dừng G3 đã được người dùng duyệt; kết quả G4 được
giải thích riêng trong [G4_GiaiThich.md](G4_GiaiThich.md). Chưa thực hiện G5.
