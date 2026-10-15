# G1 — Thiết kế Smart Lock và kế hoạch triển khai tối giản

Ngày lập: 15/10/2026. **G1 đã được người dùng duyệt và cho phép thực hiện G2.**
Thiết kế được giữ nguyên; kết quả triển khai G2 xem `G2_GiaiThich.md`.

Tài liệu này mô tả quy tắc dự kiến. Các đường đi minh họa và kết quả v0/v1
ở dưới là dự đoán từ thiết kế, chưa phải đầu ra của bộ kiểm chứng Smart Lock.
Kết quả thực nghiệm duy nhất ở G1 là kiểm tra mã mẫu trong mục 12.

## 1. Căn cứ từ tài liệu và giới hạn phạm vi

Đã đọc toàn bộ hai hướng dẫn BTL và các phần liên quan trực tiếp của ba
slide chương, Lab 1, Lab 6 cùng mã Python liên quan:

- `references/BTL_01_HuongDan_DeTai.pdf`: trang 5 khuyến nghị chương trình
  nhỏ; trang 7 cho phép chọn module toolkit phù hợp; trang 9–10 nêu chủ đề
  Kripke + BMC và ví dụ khóa cửa; trang 19 yêu cầu bằng chứng và mã chạy lại.
- `references/BTL_02_HuongDan_BaoCao.pdf`: trang 4 yêu cầu PDF tiếng Việt,
  10–20 trang nội dung chính, cỡ chữ tương đương 12pt, giãn dòng 1.5; trang
  5–6 quy định cấu trúc/bìa/mục lục; trang 14–20 yêu cầu bằng chứng, giới hạn
  và trích đoạn code; trang 23 yêu cầu ghi nguồn và phạm vi hỗ trợ AI.
- `references/Chuong1_Phan2_ATPM.pdf`: mục 1.5, đặc biệt trang 41–68,
  định nghĩa Kripke, đường đi, quan hệ total, safety/liveness và AG/AF.
- `references/Chuong3_Phan1_ATPM.pdf`: phần đặc tả, quy trình kiểm chứng,
  giới hạn suy luận và SAT/SMT, đặc biệt trang 7–8, 15–16, 56–70.
- `references/Chuong3_Phan2_ATPM.pdf`: mục 3.5, trang 4–11, 21–23, 28–29,
  công thức BMC, tăng bound, completeness threshold.
- `references/lab1_kripke_access_model/`: README, PDF, Python model checker,
  hai JSON mô hình và các test Python liên quan.
- `references/lab6_bounded_model_checking/`: README, PDF, Python BMC engine,
  test BMC và đặc tả bốn case gốc. Không lấy kết quả ghi sẵn làm bằng chứng
  đã chạy trong project này.
- `toolkit/softsec-toolkit/ch1_models/kripke.py`, các ví dụ SMT/BMC trong
  `ch3_verify/02_smt_examples.py`, `ch3_verify/03_bmc_manual.py`, requirements.

Đề tài áp dụng thực chất Chương 1 (sinh mô hình từ logic) và Chương 3
(kiểm chứng CTL, SMT/BMC). Theo hướng chủ đề 1, không triển khai các chương
khác chỉ để tăng số kỹ thuật. Chỉ mô phỏng logic Python: không web, database,
IoT, C, parser CTL tổng quát hay framework kiểm chứng.

## 2. Một mô hình, năm chức năng, bốn nhóm nghiệp vụ

Toàn hệ thống dùng cùng kiểu `State` và cùng hàm sinh bước kế tiếp.
Bốn nhóm logic trong `model.py` gồm:

1. Authentication + Account Lockout: F1 và F2.
2. Door Control: F3.
3. Alarm: F4.
4. Admin Recovery: F5.

Không tạo bốn mô hình Kripke rời. `v0` và `v1` là hai cấu hình của cùng
quy tắc, chỉ khác hai điểm lỗi được chỉ rõ ở mục 8.

Đầu vào mật khẩu được trừu tượng hóa thành hai lớp `password_ok` và
`password_bad`. Quyền admin là kết quả kiểm tra tin cậy từ môi trường mô
phỏng, không phải dữ liệu do người dùng thường tự gán để nâng quyền.
Không xây dựng hệ thống tài khoản hoặc thuật toán mật mã thật.

## 3. Bảng biến trạng thái

Một trạng thái có thứ tự giá trị:

`s = (authenticated, failed_attempts, door_open, alarm, phase, admin_authorized)`.

| Biến | Miền giá trị | Ý nghĩa và quy ước |
| --- | --- | --- |
| `authenticated` | `False, True` | Phiên người dùng hiện tại đã xác thực; kết thúc khi đóng cửa, tamper hoặc bắt đầu reset. |
| `failed_attempts` | `0, 1, 2, 3` | Số lần nhập sai kể từ xác thực thành công/reset gần nhất; không vượt 3. |
| `door_open` | `False, True` | Trạng thái cửa do logic điều khiển mô phỏng. |
| `alarm` | `False, True` | Đã phát hiện tamper; chỉ reset hoàn tất mới xóa báo động. |
| `phase` | `normal, locked_out, resetting` | Pha vận hành; `normal` cho phép xử lý thông thường, `locked_out` chặn đăng nhập, `resetting` là quá trình phục hồi nội bộ. |
| `admin_authorized` | `False, True` | Kết quả kiểm tra quyền được lưu cho yêu cầu reset đã nhận; không suy ra từ `phase`. Khởi tạo và xóa về `False` khi hoàn tất reset. |

Có tối đa `2 × 4 × 2 × 2 × 3 × 2 = 192` tổ hợp miền giá trị.
Đây là **cận trên lý thuyết, không phải số trạng thái reachable**.
BFS ở G2 mới xác định số trạng thái và cạnh chính xác cho từng cấu hình.

Không thêm biến `locked_out` riêng vì đã có `phase`. Không định nghĩa
`locked_out` bằng `failed_attempts == 3`: làm vậy khiến P2 trở thành đồng
nhất thức, không kiểm tra được cập nhật pha khóa có đi kèm đúng bộ đếm.

`admin_authorized` cần được lưu vì P4 kiểm tra trạng thái đang reset có
bằng chứng quyền. Hai trường này có ý nghĩa khác nhau: hành động đang chạy
và kết quả kiểm tra quyền đã nhận. Không viết nhãn này bằng biểu thức
`phase == resetting`, không tự ép nó đúng khi kiểm chứng.

Trạng thái ban đầu duy nhất:

`s_init = (False, 0, False, False, normal, False)`.

Các quan hệ nghiệp vụ như `alarm -> !door_open` là điều phải kiểm tra trên
trạng thái được sinh. Không dùng chúng làm bộ lọc loại bỏ trạng thái sau
chuyển tiếp hoặc ràng buộc SMT đầu vào, vì sẽ che mất lỗi cần phát hiện.
Chỉ kiểm tra miền giá trị/kiểu dữ liệu ở mức biểu diễn.

## 4. Atomic propositions và bảng trạng thái minh họa

Hàm `labels(s)` tính các nhãn trực tiếp từ dữ liệu:

| AP | Điều kiện đúng |
| --- | --- |
| `authenticated` | `s.authenticated` |
| `door_open` | `s.door_open` |
| `alarm` | `s.alarm` |
| `locked_out` | `s.phase == locked_out` |
| `attempts_eq_3` | `s.failed_attempts == 3` |
| `resetting` | `s.phase == resetting` |
| `admin_authorized` | `s.admin_authorized` |
| `idle` | `s == s_init`, tức cửa đóng, chưa xác thực, bộ đếm 0, không alarm, pha normal, quyền reset đã xóa |

`idle` là trạng thái sạch sau phục hồi, không chỉ có nghĩa “không resetting”.
`normal` vẫn có thể đi kèm báo động hoặc bộ đếm 1–2; vì vậy guard phải kiểm
tra alarm và các điều kiện tương ứng.

Ví dụ giá trị dưới đây chỉ giúp đọc thiết kế, không phải danh sách states
đầu vào của BFS. Tên trong cột đầu là mô tả, không phải định danh logic:

| Mô tả | `authenticated` | `failed_attempts` | `door_open` | `alarm` | `phase` | `admin_authorized` |
| --- | --- | --- | --- | --- | --- | --- |
| Ban đầu / phục hồi xong | False | 0 | False | False | normal | False |
| Sai một lần | False | 1 | False | False | normal | False |
| Sai hai lần | False | 2 | False | False | normal | False |
| Khóa sau lần sai thứ ba | False | 3 | False | False | locked_out | False |
| Xác thực thành công | True | 0 | False | False | normal | False |
| Mở cửa hợp lệ | True | 0 | True | False | normal | False |
| Tamper từ trạng thái ban đầu | False | 0 | False | True | normal | False |
| Admin bắt đầu reset sau lockout | False | 3 | False | False | resetting | True |

Các trạng thái kết hợp khác, ví dụ alarm khi đã locked_out, vẫn được sinh
nếu quy tắc cho phép; không bị bỏ sót vì bảng minh họa này.

## 5. Guard và action của v1

Ký hiệu: `a=authenticated`, `f=failed_attempts`, `d=door_open`, `b=alarm`,
`p=phase`, `u=admin_authorized`. Các biến không ghi trong action được giữ
nguyên. Mỗi sự kiện là một bước nguyên tử.

| Sự kiện | Guard | Action |
| --- | --- | --- |
| `password_ok` | `p=normal AND !b AND !a AND !d` | `a=True; f=0` |
| `password_bad` | `p=normal AND !b AND !a AND !d AND f<3` | `f'=min(f+1,3); a=False; p'=locked_out nếu f'=3, ngược lại normal` |
| `open_door` | `p=normal AND !b AND a AND !d` | `d=True` |
| `close_door` | `p=normal AND d` | `d=False; a=False` (kết thúc phiên) |
| `tamper` | `p!=resetting` | `b=True; d=False; a=False`, giữ nguyên `f,p` |
| `reset_request(admin=True)` | `p!=resetting` và kiểm tra quyền cho kết quả True | `p=resetting; u=True; a=False; d=False`, giữ `f,b` cho tới hoàn tất |
| `reset_request(admin=False)` | Không có guard chấp nhận | Từ chối yêu cầu; không tạo bước chuyển nghiệp vụ |
| `reset_complete` | `p=resetting` | Gán toàn bộ trạng thái bằng `s_init` |
| `wait` | `p!=resetting` | Giữ nguyên trạng thái (self-loop mô phỏng chờ) |

`reset_request` được lưu tên sự kiện cùng kết quả kiểm tra quyền, ví dụ
`admin_reset`, để bảng sinh mã chỉ nhận sự kiện đã định danh rõ ràng.
Yêu cầu không có quyền được kiểm thử bằng đường từ chối, không giả thành
một reset hợp lệ. Quyền kiểm tra admin độc lập với `authenticated` của
người dùng thường: admin vẫn được phục hồi khi lockout/alarm.

Ba lần sai là ba sự kiện `password_bad` liên tiếp trong lịch sử thử mật
khẩu; thao tác chờ/đóng cửa không tự đặt lại bộ đếm. `password_ok` hoặc
`reset_complete` xóa chuỗi sai. Sau khi đã xác thực, giao diện mô phỏng
không nhận thêm lần thử mật khẩu trước khi phiên kết thúc.

Sự kiện có guard sai được API mô phỏng từ chối bằng `InvalidEvent` (hoặc
`ValueError` với thông báo rõ), giữ nguyên trạng thái của bên gọi. Không
đưa các lần nhập sai loại sự kiện thành cạnh “từ chối” trong Kripke.
Sự kiện không nhận diện được cũng bị từ chối.

### Totality và giả định tiến triển

- Mọi trạng thái ngoài reset có `wait`, do đó luôn có ít nhất một kế tiếp.
- Trong `resetting` của v1 chỉ có `reset_complete`; không có `wait`, tamper,
  nhập mật khẩu, từ chối input hay reset lặp thành cạnh xen vào.
- Không tự thêm self-loop vào mọi trạng thái. Thêm tại resetting sẽ tạo
  đường thực thi vô hạn không tới idle và làm P5 sai.
- Các sự kiện ngoài khi reset đang chạy được coi là chưa xử lý, không
  tiêu thụ một bước thời gian của mô hình. Giả định reset là thao tác nội
  bộ có ưu tiên, hoàn tất sau một bước logic; không cần giả định fairness
  để bỏ qua một đường đi xấu trong đồ thị v1.
- Đây là giả định thiết kế phần mềm được công bố: không mô hình hóa mất
  điện, hỏng cơ cấu, tiến trình nội bộ bị dừng hoặc lỗi phần cứng.

## 6. Kripke và BFS sinh trạng thái thật

`K = (S, S0, R, L)` trong mỗi cấu hình:

- `S0 = {s_init}`.
- `S` được khám phá bằng áp dụng guard/action từ `S0` cho tới hết queue.
- `R` gồm cặp trạng thái của các bước hợp lệ đã sinh.
- `L(s)=labels(s)`; không đọc nhãn được gán tay từ file JSON.

Thuật toán dự kiến, chỉ là giả mã ở G1:

```text
seen = {s_init}; queue = [s_init]
while queue chưa rỗng:
    s = lấy đầu queue
    for (event, next_state) sinh từ các guard/action khả thi tại s:
        lưu (s, event, next_state)
        if next_state chưa thuộc seen:
            thêm next_state vào seen và cuối queue
            lưu parent và khoảng cách BFS
```

`State` dự kiến là frozen dataclass, hash/equality dựa vào cả sáu giá trị.
ID `s0,s1,...` chỉ được gán khi khám phá, phục vụ hiển thị. Không dùng ID
để quyết định hai trạng thái có giống nhau. Thứ tự duyệt sự kiện cố định
để ID, sơ đồ và log tái lập được.

Giữ riêng các cạnh `(source,event,target)`; nhiều sự kiện có thể cùng cặp
đầu/cuối. Khi xuất, báo riêng:

- Số trạng thái và số reachable states (phải bằng nhau vì xây bằng BFS).
- `|R|`: số cặp `(source,target)` phân biệt của Kripke.
- Số transition gắn sự kiện: số bộ ba phân biệt; có thể lớn hơn `|R|`.
- Trạng thái ban đầu, toàn bộ giá trị state, nhãn và danh sách transitions.
- Độ sâu lớn nhất trong cây BFS từ trạng thái ban đầu.

Không khai báo sẵn toàn bộ `S`. Không dùng bộ lọc safety để làm nhỏ `S`.
Chi phí khám phá tỷ lệ số state và các lần xét sự kiện; số sự kiện cố định
nhỏ nên phù hợp bài tập lớn.

## 7. Đúng năm thuộc tính CTL

`AG φ`: trên mọi đường thực thi, φ đúng tại mọi trạng thái, kể cả hiện tại.
`AF φ`: trên mọi đường thực thi từ trạng thái hiện tại, sau hữu hạn bước
phải có φ (được phép đúng ngay tại bước 0).

Ngữ nghĩa total và AG/AF này khớp tài liệu Chương 1; đối chiếu thêm
[tài liệu CTL của NuSMV](https://nusmv.fbk.eu/papers/sttt_j/html/node3.html).

| ID | Công thức giữ nguyên yêu cầu | Loại / chức năng |
| --- | --- | --- |
| P1 | `AG(door_open -> (authenticated AND NOT locked_out))` | Safety; F1, F2, F3 |
| P2 | `AG(locked_out -> attempts_eq_3)` | Safety; F2 |
| P3 | `AG(alarm -> NOT door_open)` | Safety; F3, F4 |
| P4 | `AG(resetting -> admin_authorized)` | Safety; F5 |
| P5 | `AG(resetting -> AF idle)` | Liveness; F5 |

**P1.** Mọi trạng thái cửa mở phải có xác thực và không lockout. Guard mở
cửa v1 bảo đảm điều kiện này; các bước hủy xác thực đồng thời đóng cửa.
Một trạng thái `d=True,a=False` là vi phạm với tiền tố hữu hạn, ví dụ
`s_init --open_door--> ...` khi bỏ guard xác thực.

**P2.** Khi pha là locked_out thì bộ đếm phải đúng 3. Điều này đòi hỏi bước
sai thứ ba cập nhật cả pha và bộ đếm, đồng thời không có bước giảm bộ đếm
mà vẫn giữ pha khóa. Ví dụ lỗi khóa sớm ở `f=2` làm P2 sai.
P2 chỉ phát biểu một chiều: tự nó không bắt lỗi `f=3` nhưng vẫn `normal`.
Vì vậy test chức năng phải kiểm tra chưa khóa ở lần 1–2, khóa đúng lần 3
và chặn cả mật khẩu đúng lẫn mở cửa sau lockout. Không thêm công thức CTL
chính thứ sáu để thay đổi yêu cầu.

**P3.** Trong mọi trạng thái alarm, cửa phải đóng. Giả định phát hiện
tamper và hành động đóng cửa cùng một bước nguyên tử; mở cửa bị chặn khi
alarm. Ví dụ từ cửa đang mở, lỗi chỉ bật `alarm=True` mà quên đóng cửa
sẽ tạo trạng thái `b=True,d=True` vi phạm. Mô hình không khẳng định cơ
cấu phần cứng thật luôn đóng được cửa.

**P4.** Mỗi reset đang xử lý phải giữ kết quả quyền admin hợp lệ. Guard
nhận reset phải kiểm tra quyền và action lưu kết quả đó; nhãn đọc `u`,
không suy ra từ pha. Ví dụ chấp nhận `reset_request(admin=False)` rồi
đặt `p=resetting,u=False` sẽ vi phạm. Đây là safety vì quan sát hữu hạn
tới trạng thái này đã đủ làm chứng.

**P5.** Sau mọi lần bắt đầu reset, mọi cách tiếp diễn phải về trạng thái
sạch `idle`. Giả định ưu tiên bước nội bộ được mô hình hóa bằng cạnh duy
nhất `reset_complete` trong v1. Một đường `resetting --reset_retry-->
resetting ...` vô hạn vi phạm P5, dù vẫn tồn tại lựa chọn hoàn tất.
Tiền tố hữu hạn đơn thuần chưa chứng minh “không bao giờ hoàn tất”; phải
có chu trình/lasso hoặc tính toán đầy đủ trên đồ thị hữu hạn.

### Phương pháp kiểm chứng vừa đủ

P1–P4: bốn predicate Python cố định mô tả bad state; xét toàn bộ states
reachable. Nếu có bad state, BFS parent cho phản ví dụ ngắn nhất.
Không viết parser diễn giải chuỗi CTL.

P5: tính tập `AF_idle` bằng điểm bất động nhỏ nhất:

```text
Z0 = {s | idle(s)}
Z(n+1) = Z(n) ∪ {s | Succ(s) không rỗng và Succ(s) ⊆ Z(n)}
lặp tới khi Z không thay đổi
P5 đúng khi mọi s có resetting đều thuộc Z
```

Nếu tồn tại resetting không thuộc Z, dựng tiền tố từ initial tới nó;
tiếp tục chọn kế tiếp ngoài Z cho tới khi lặp một trạng thái. Kết quả là
lasso tránh idle **từ lần reset vi phạm trở đi**, có chỉ số đầu chu kỳ
và tên sự kiện trên từng cạnh. Không cấm idle ở tiền tố trước lần reset,
vì trạng thái ban đầu chính là idle.

Báo số trạng thái kích hoạt từng tiền đề (`door_open`, `locked_out`,
`alarm`, `resetting`) và test có đường đi tới chúng để tránh kết luận
đúng một cách rỗng do chức năng không bao giờ được kích hoạt.

## 8. Hai cấu hình v0/v1 và hai lỗi minh họa

**BUG-01 — thiếu điều kiện xác thực khi mở cửa.**

- v0: guard `open_door` chỉ kiểm tra `p=normal AND !b AND !d`.
- v1: thêm `a` vào guard như mục 5.
- Thuộc tính bị ảnh hưởng dự kiến: P1.
- Phản ví dụ dự kiến: `s_init --open_door--> (False,0,True,False,normal,False)`;
  bước vi phạm 1, BMC dự kiến UNSAT ở k=0 và SAT ở k=1.

**BUG-02 — reset có thể lặp mãi.**

- v0: ngoài `reset_complete`, có `reset_retry` với guard `p=resetting`,
  action giữ nguyên trạng thái.
- v1: bỏ `reset_retry`; resetting chỉ chạy `reset_complete`.
- Thuộc tính bị ảnh hưởng dự kiến: P5.
- Lasso dự kiến: `s_init --admin_reset--> r --reset_retry--> r ...`.
  `reset_complete` vẫn tồn tại trong v0, nên “có thể hoàn tất” không đủ
  chứng minh “mọi đường đều hoàn tất”.

| Thuộc tính | Dự đoán v0 | Dự đoán v1 |
| --- | --- | --- |
| P1 | Vi phạm bởi BUG-01 | Thỏa |
| P2 | Thỏa | Thỏa |
| P3 | Thỏa | Thỏa |
| P4 | Thỏa | Thỏa |
| P5 | Vi phạm bởi BUG-02 | Thỏa |

**Bảng trên chưa được chạy kiểm chứng.** Không dùng từ PASS/SAT như kết
quả thực tế của Smart Lock cho tới G3. Không cần cài thêm lỗi thứ ba.

## 9. BMC với Z3 và giới hạn kết luận

Chọn mã hóa đồ thị Kripke đã sinh thay vì viết lại logic nghiệp vụ bằng
một hệ quy tắc SMT độc lập. Mỗi bước có `x_i` là ID state và `e_i` là ID
sự kiện; các ID ánh xạ ngược được sang đủ sáu biến và tên sự kiện.

```text
I(x0) := x0 = id(s_init)
T(xi,ei,xi+1) := OR cho mỗi (src,event,dst) hợp lệ:
                  (xi=id(src) AND ei=id(event) AND xi+1=id(dst))
BMC_j(k) := I(x0)
            AND các ràng buộc miền ID tại i=0..k
            AND AND(i=0..k-1) T(xi,ei,xi+1)
            AND OR(i=0..k) bad_j(xi)               [j thuộc P1..P4]
```

`bad_j` lấy giá trị các biến của state để tính phủ định thuộc tính j.
Không đưa chính các invariant cần chứng minh vào I/T làm giả định.
Với k=0, phần AND chuyển tiếp rỗng có giá trị True: vẫn kiểm tra initial.

Chạy từng bound `0,1,2,...,D` (có thể dừng một thuộc tính ở SAT đã replay
hợp lệ, nhưng giữ log các bound đã chạy). Cả bốn thuộc tính safety đều
được gọi solver thật, kể cả trường hợp không có bad state trong đồ thị.

Trạng thái kết quả phải tách rõ, đúng với
[hướng dẫn Python chính thức của Z3](https://microsoft.github.io/z3guide/programming/Z3%20Python/Introduction/):

- `SAT`: solver tìm phép gán; chỉ công bố phản ví dụ hợp lệ sau khi giải mã
  và replay thành công từ initial theo đúng guard/action của cấu hình.
- `UNSAT`: không có phản ví dụ của thuộc tính đó trong bound đã kiểm tra.
- `UNKNOWN`: solver chưa kết luận; lưu `reason_unknown()`, không đổi thành
  UNSAT hoặc an toàn.
- `ERROR`: lỗi thực thi/giải mã/replay; ghi thông tin lỗi. Đây là trạng thái
  ứng dụng, không phải kết quả trả về thứ tư của `Solver.check()`.

Lưu riêng `solver_status` và `verification_status`: nếu solver SAT nhưng
replay thất bại thì giữ bằng chứng solver SAT và báo ERROR ở bước xử lý,
không xuất “phản ví dụ thật”. Không gọi `solver.model()` khi UNSAT/UNKNOWN.

Replay kiểm tra: initial đúng; từng event thỏa guard; action cho đúng
toàn bộ state kế tiếp; cặp có trong đồ thị; bước vi phạm thật sự làm
predicate sai. Với lasso còn kiểm tra cạnh khép vòng và không có idle
trong đoạn từ resetting vi phạm tới hết chu kỳ.

### Completeness Threshold trong đúng bài toán này

Sau khi BFS đã sinh hết đồ thị, tính `D = max_s shortest_distance(s_init,s)`.
Với một initial và invariant state-based P1–P4, nếu có bad state thì có
đường tới nó dài không quá D. Vì quan hệ total, mọi tiền tố ngắn hơn D
có thể kéo dài để khớp mã hóa đúng D bước. Vì vậy D là một completeness
threshold đủ dùng cho **reachability của bad state trên mô hình này**;
cận thô khác là `|S|-1`. D không nhất thiết là ngưỡng nhỏ nhất cho từng Pj.

Chỉ sau khi xác nhận đồ thị đã khám phá đầy đủ, total, encoding đúng và
solver UNSAT tới ngưỡng phù hợp mới có thể kết luận invariant đúng trên
toàn mô hình hữu hạn. UNSAT ở bound nhỏ không đủ. Không áp dụng D này để
kết luận liveness P5; P5 được kiểm tra đồ thị đầy đủ như mục 7.

Đánh đổi được công bố: BMC ở đây dùng lại đồ thị đã liệt kê, có tác dụng
minh họa encoding và đối chiếu với explicit model checking, không giải
quyết state explosion hoặc chứng minh toàn bộ triển khai khóa cửa thực tế.

## 10. Tái sử dụng toolkit sau khi kiểm tra API thực tế

`toolkit/softsec-toolkit/ch1_models/kripke.py` có:

- `KripkeStructure()` không đối số; `add_state(s,labels,initial)`;
  `add_transition(src,dst)` yêu cầu hai đầu đã tồn tại.
- `reachable_states()`, `find_path(target)`, `is_reachable(target)`;
  `satisfies_EF(prop)` và `satisfies_AG_EF(prop)`.
- Không có API AG implication hoặc AF tổng quát, không có exporter hình
  hoàn chỉnh trong file thực tế, không tự bảo đảm totality.
- `transitions[src]` là set ID đích, không giữ tên event. Hai event cùng
  cặp state sẽ bị gộp nếu chỉ lưu bằng cấu trúc này.

Đề xuất tái sử dụng nguyên lớp làm nơi chứa `S,S0,R,L`, kiểm tra
reachability và đường đi. `smartlock/kripke.py` có adapter nhỏ nạp module
theo đường dẫn file bằng `importlib`, vì toolkit hiện không được đóng gói
để `pip install`. Không sửa toolkit, không tạo plugin hoặc package mới
cho toolkit. Adapter giữ thêm ánh xạ ID -> State và cạnh có event;
`successors` mới trong model.py mới là nguồn sinh trạng thái thật.

Lab 1 có lớp khác, constructor khác và `from_json()` đọc đầy đủ states,
transitions khai báo sẵn. `reachable_states()` của cả hai lớp chỉ duyệt
đồ thị, không sinh không gian trạng thái từ nghiệp vụ. Không gọi lại
các hàm đó rồi mô tả là đã đáp ứng yêu cầu BFS bắt buộc của project.

Lab 1 dùng key `src->dst` lưu event, có thể ghi đè khi nhiều sự kiện cùng
hai đầu; type annotation của `transition_events` cũng không khớp giá trị
string thực tế. Vì vậy tham khảo ý tưởng phản ví dụ, không sao chép
cách lưu event hoặc parser công thức đơn giản.

Ví dụ `ch3_verify/03_bmc_manual.py` thực sự gọi Z3 và mã hóa quan hệ bằng
OR các cạnh. Tái sử dụng cách mã hóa đó cho đồ thị sinh tự động. Lab 6
chỉ có nhánh `if result == sat`, mọi kết quả khác rơi xuống SAFE;
không dùng nguyên cách phân loại này cho project mới.

Slide có nhắc `ch3_staticsat.bounded_checker`, nhưng đường dẫn đó không
tồn tại trong bộ toolkit được cung cấp. Không giả định API trong slide
là module đã cài sẵn. Ví dụ counter của toolkit quay `3->0`, còn slide
trang 55 dùng `3->3`; mô hình Smart Lock phải tự quy định ngữ nghĩa.

## 11. Cấu trúc project dự kiến và số file

Các đường dẫn dưới đây là **kế hoạch, chưa tạo mã nguồn ở G1**:

```text
kripke-model-checking/
  README.md
  .gitignore
  requirements.txt
  run.py                         # CLI chạy pipeline theo cấu hình/bound
  smartlock/
    __init__.py
    model.py                     # State, labels, guard/action, v0/v1
    kripke.py                    # BFS, toolkit adapter, replay, export JSON
    ctl.py                       # P1–P4 invariants, AF cho P5 và lasso
    bmc.py                       # encoding, Z3, trạng thái kết quả
    artifacts.py                 # sinh Python, DOT/SVG và bảng so sánh
  tests/
    test_model.py
    test_kripke.py
    test_verification.py
    test_artifacts.py
  docs/
    G1_ThietKe.md                 # tài liệu hiện tại
  generated/
    v0/smart_lock.py              # mã Python sinh ra, chỉ dùng standard library
    v1/smart_lock.py
  results/
    g1/toolkit_checks.log         # bằng chứng hiện tại
    v0/                          # model.json, CTL/BMC, trace/lasso, sơ đồ
    v1/
    comparison.csv               # một bảng nhỏ, không workbook/dashboard
  report/
    BaoCao_BTL_Kripke.md          # nguồn báo cáo có thể chỉnh sửa
    build_report.py              # tạo PDF từ nguồn và kết quả thực tế
    BaoCao_BTL_Kripke.pdf         # chỉ tạo ở G5
  references/                    # giữ tài liệu hiện có
  toolkit/                       # giữ toolkit hiện có
```

Cốt lõi gồm **6 file chạy chính**: `run.py` và 5 module nghiệp vụ/kiểm
chứng/xuất kết quả. Thêm 4 file test, 1 `__init__.py`, 1 script dựng báo
cáo: **12 file Python viết tay** theo kế hoạch. Hai simulator là đầu ra
sinh tự động, không phải hai mô hình viết riêng. Không tách module cho
từng F nếu chỉ làm tăng số file.

Phụ thuộc dự kiến: `z3-solver`, `pytest`; G5 thêm `reportlab`, `pypdf`
để tạo/kiểm tra PDF. Sơ đồ dùng lệnh Graphviz `dot` qua subprocess, không
cần cài thêm wrapper Python `graphviz`. Hiện `dot` chưa có trong PATH;
sẽ chuẩn bị/kiểm tra khi làm sơ đồ ở G4, không cài đặt thêm ở G1.

Sinh mã: nhúng states và bảng `(state_id,event)->next_state_id` từ mô
hình đã sinh, có `step` và cách chạy chuỗi sự kiện bằng CLI. Hai phiên
bản có thể có nhiều event khác nhau nhưng mỗi cặp state/event chỉ một
đích; tính xác định này phải được kiểm tra trước khi sinh mã. Chương
trình sinh ra không import smartlock, toolkit, Z3 hoặc pytest.

Sơ đồ ở G4 gồm Kripke đầy đủ v0/v1, ba luồng nghiệp vụ có nhóm chức năng
và trace/lasso đánh dấu cạnh lỗi. Hình luồng được ghi rõ là hình giải thích,
không thay cho graph trạng thái đầy đủ; xuất DOT và SVG/PNG đưa vào báo cáo.

## 12. Kiểm tra đã chạy ở G1

Log gốc: `results/g1/toolkit_checks.log`.

Môi trường chạy kiểm tra: Python 3.14.2, pytest 9.1.1, Z3 5.1.0. Python
runtime dùng đọc PDF có `pypdf`/Poppler; runtime đó không có Z3/pytest.
Đã chọn interpreter Python cài trên máy có đủ Z3/pytest để chạy kiểm tra.
Shortcut `python` của Microsoft Store không chạy được Python trong PATH;
README ghi lại đường dẫn interpreter đã chạy thành công.

Kết quả thực tế:

- Ba test Python Lab 1: mô hình safe thỏa các thuộc tính của lab; bản buggy
  vi phạm P1 của lab; khả năng mở cửa của bản buggy vẫn đạt được.
- Một test Python Lab 6: kết quả BMC của bốn case gốc khớp kỳ vọng.
- Tổng pytest: **4 passed in 0.21s**. Chỉ con số này là số test pytest đã
  chạy trong G1; không báo toàn bộ test lab đã PASS.
- Kiểm tra API bằng assertion: counter có 4 trạng thái đạt được, đường đi
  `0->1->2->3`, cạnh kết thúc của ví dụ thực tế là `3->0`; API không có
  AG implication/AF, không tự total hóa và không giữ tên sự kiện.
- Chạy thật `bmc_k1_with_z3()`: **SAT**, witness `s0=0,s1=1`.
- Một công thức Z3 mâu thuẫn đơn giản: **UNSAT**.
- Chưa thực nghiệm solver trả UNKNOWN; nhận xét nhánh UNKNOWN của Lab 6
  dựa vào đọc code. Chưa có bằng chứng P1–P5 của Smart Lock.

Không chạy test C/ASan hoặc các kỹ thuật nằm ngoài đề tài. Không sửa dữ
liệu tham khảo và không lấy các log PASS có sẵn trong lab làm kết quả G1.

### Kế hoạch test các bước sau

- G2: đúng/sai mật khẩu, bộ đếm 1–2–3, reset chuỗi sai sau thành công,
  chặn đăng nhập/mở cửa sau lockout; mở/đóng cửa; tamper; reset có/không
  quyền; BFS không trùng state, cạnh hợp lệ, total và ID ổn định.
- G3: đúng năm CTL trên hai cấu hình; k=0; SAT/UNSAT bằng solver thật;
  replay đúng/sai; lasso P5; D và giới hạn bound; kiểm tra tiền đề reachable.
  Test UNKNOWN và ERROR dùng giả lập kết quả/exception có ghi rõ, tránh
  gọi chúng là kết quả UNKNOWN thực tế của solver nếu chưa xảy ra.
- G4: duyệt mọi cạnh của bảng sinh mã để đối chiếu `step`; thử sự kiện
  bị từ chối; chạy simulator độc lập không có verifier trong import path;
  kiểm tra file sơ đồ và log được tạo từ lần chạy thực tế.
- G5: đối chiếu số liệu/ảnh với results, tạo PDF thật, render và xem các
  trang, kiểm tra tiếng Việt, font, mục lục, tràn trang và nguồn chỉnh sửa.

## 13. Lộ trình G2–G5 và phân công nhóm

1. G2: viết model.py, BFS/adapter và test mô hình. Xuất state/transition
   để đọc trước khi dùng làm đầu vào kiểm chứng.
2. G3: viết các predicate, AF, BMC và replay. Ghi kết quả từng bound,
   phản ví dụ, ngưỡng đầy đủ và so sánh v0/v1.
3. G4: sinh simulator, sơ đồ và test nhất quán; hoàn thiện CLI tái lập kết quả.
4. G5: biên soạn báo cáo khoảng 15–18 trang nội dung chính trong giới hạn
   10–20 trang, theo đúng cấu trúc giảng viên. Phụ lục trích đoạn code,
   hướng dẫn chạy, log và 18 câu hỏi–đáp về Kripke/BFS/CTL/BMC/Z3/code.

Phân công gợi ý: sinh viên 1 phụ trách biến và guard/action; sinh viên 2
BFS/sơ đồ; sinh viên 3 CTL/BMC; sinh viên 4 tests/sinh mã/tổng hợp báo cáo.
Cả nhóm đọc chung quy tắc và giải thích được counterexample; không chia
thành bốn hệ thống độc lập. Thông tin họ tên/MSSV/lớp/học kỳ cần bổ sung
trước G5, chưa cần để duyệt mô hình ở G1.

## 14. Bàn giao G1 và điểm dừng

Đã tạo tài liệu thiết kế này, bổ sung README, cập nhật .gitignore và lưu log
kiểm tra toolkit. Chưa tạo thư mục mã nguồn Smart Lock, chưa sinh mô
hình v0/v1, chưa chạy kiểm chứng của đề tài hoặc tạo báo cáo cuối kỳ.

Các quyết định cần duyệt: sáu biến và ý nghĩa idle, guard/action ở mục 5,
ưu tiên hoàn tất reset, hai lỗi v0, hai phương pháp kiểm chứng và cấu trúc
6 file chạy chính. Điểm dừng trên đã được người dùng duyệt sau G1;
G2 được triển khai theo thiết kế này và có tài liệu bàn giao riêng.
