# Mô hình hóa và kiểm chứng Smart Lock bằng Kripke, CTL và BMC/Z3

## 1. Giới thiệu

Bài tập lớn môn An toàn phần mềm: mô phỏng khóa cửa thông minh, sinh mô hình
Kripke bằng BFS và kiểm chứng năm thuộc tính CTL. **v0** có hai lỗi cố ý;
**v1** bổ sung kiểm tra xác thực khi mở cửa và loại chu trình reset vô hạn.
Phạm vi nghiệp vụ dựa trên tài liệu học phần [1], [2].

Năm chức năng: **Authentication** (xác thực), **Account Lockout** (khóa sau
đúng ba lần sai liên tiếp), **Door Control** (mở/đóng cửa), **Alarm** (báo
động khi tamper), **Admin Recovery** (phục hồi với xác thực quản trị).

Công nghệ: Python, softsec-toolkit [3], Kripke, BFS, CTL, BMC, Z3 [7],
pytest và Graphviz [8].

## 2. Mô hình Kripke và BFS

Một mô hình tích hợp cho mỗi phiên bản: `K=(S,S0,R,L)` [4]. Trạng thái gồm
`authenticated`, `failed_attempts`, `door_open`, `alarm`, `phase`,
`admin_authorized`; initial là `(False,0,False,False,'normal',False)`.

BFS bắt đầu từ initial, gọi events/guards/actions trong `model.step`, thêm
state mới vào hàng đợi và ghi mọi cạnh hợp lệ. Chỉ sinh phần reachable,
không ép đủ 192 tổ hợp miền hoặc lọc bỏ trạng thái vi phạm.
Số state v0/v1 là **21/18**; số event transitions **69/46**; số cặp R **65/42**.

## 3. Năm đặc tả CTL

AP được tính từ trạng thái bởi `labels`. AG nghĩa luôn đúng trên mọi đường;
AF nghĩa mọi đường cuối cùng đạt điều kiện [5].

| Mã | Công thức | Yêu cầu |
|---|---|---|
| P1 | `AG(door_open -> (authenticated AND NOT locked_out))` | Mở cửa phải có xác thực và chưa lockout |
| P2 | `AG(locked_out -> attempts_eq_3)` | Lockout đi kèm bộ đếm bằng 3 |
| P3 | `AG(alarm -> NOT door_open)` | Báo động thì cửa đóng |
| P4 | `AG(resetting -> admin_authorized)` | Reset có quyền quản trị |
| P5 | `AG(resetting -> AF idle)` | Mọi lần reset phải hoàn tất |

P1-P4: quét bad-state trên toàn graph và BMC/Z3. P5: CTL least fixed-point
cho AF idle, kèm lasso khi vi phạm. Không có parser CTL tổng quát.

## 4. BMC/Z3, kết quả và counterexample

BMC unroll k bước từ initial, ràng buộc từng bộ source/event/target đúng
mô hình, rồi hỏi có bad-state ở vị trí 0..k hay không [6], [7]. Z3 được gọi
thật từ k=0 tăng dần; SAT được giải mã và replay bằng logic gốc.
UNSAT chỉ loại phản ví dụ trong bound; UNKNOWN và ERROR được ghi riêng.

Độ sâu ngắn nhất lớn nhất **D=5** đủ cho bốn safety dạng bad-state hiện tại
trên graph đầy đủ/total, không áp dụng để kết luận P5.

| Thuộc tính | Phương pháp | v0 | v1 |
|---|---|---|---|
| P1 | Duyệt graph + BMC/Z3 | VIOLATED; k=1 SAT | HOLDS; k=0..5 UNSAT |
| P2 | Duyệt graph + BMC/Z3 | HOLDS | HOLDS |
| P3 | Duyệt graph + BMC/Z3 | HOLDS | HOLDS |
| P4 | Duyệt graph + BMC/Z3 | HOLDS | HOLDS |
| P5 | CTL AF fixed-point | VIOLATED; lasso | HOLDS |

Một lần kiểm chứng hai phiên bản có **44 query Z3: 1 SAT, 43 UNSAT,
0 UNKNOWN, 0 lỗi ứng dụng**. P2-P4 kiểm k=0..5; P1 v0 dừng tại SAT đầu tiên.

- **P1 v0:** `s0 --open_door--> s3`; cửa mở chưa xác thực, phản ví dụ ngắn nhất một bước. [Sơ đồ P1](results/g4/diagrams/counterexample_p1_v0.svg).
- **P5 v0:** prefix `s0 --admin_reset [True]--> s5`, cycle `s5 --reset_retry--> s5` lặp vô hạn. [Sơ đồ P5](results/g4/diagrams/counterexample_p5_v0.svg).

Bằng chứng: [model v0](results/v0/model.json), [model v1](results/v1/model.json),
[kiểm chứng v0](results/v0/verification.json), [kiểm chứng v1](results/v1/verification.json),
[CSV so sánh](results/comparison.csv). [Bảy sơ đồ](results/g4/diagrams/) có DOT/SVG/PNG;
[bảng state](results/g4/state_legend.csv) giải nghĩa ID theo từng phiên bản.

## 5. Cấu trúc mã nguồn

```text
smartlock/    model.py, kripke.py, ctl.py, bmc.py, artifacts.py
generated/    v0/smart_lock.py, v1/smart_lock.py
tests/        mô hình, BFS, kiểm chứng, mã sinh và sơ đồ
toolkit/      softsec-toolkit/ch1_models/kripke.py
docs/         Technical_Overview.md
results/      mô hình, kiểm chứng, sơ đồ, CSV/JSON/log bằng chứng
run.py        CLI mô phỏng, kiểm chứng, sinh mã/sơ đồ
requirements.txt, pytest.ini
```

Luồng đọc code: [model](smartlock/model.py) -> [BFS/Kripke](smartlock/kripke.py)
-> [CTL](smartlock/ctl.py) / [BMC](smartlock/bmc.py) -> [generator](smartlock/artifacts.py).
[Tổng quan kỹ thuật](docs/Technical_Overview.md) giải thích sáu biến, guard/action,
fixed-point, encoding, replay và cách đối chiếu mã sinh với mô hình.

## 6. Cài đặt, chạy và kiểm thử

Cần Python 3.10+, Git; cài Graphviz `dot` từ [nguồn chính thức](https://graphviz.org/download/)
và thêm vào PATH để chạy đầy đủ tests hoặc sinh ảnh. `GRAPHVIZ_DOT` cũng có
thể trỏ trực tiếp tới executable. Mô phỏng/kiểm chứng không cần Graphviz.
Tạo môi trường ảo theo tài liệu Python [9]:

```sh
git clone https://github.com/bbaonngoc/kripke-model-checking.git
cd kripke-model-checking
python -m venv .venv
```

Kích hoạt bằng `.\.venv\Scripts\Activate.ps1` (PowerShell) hoặc
`source .venv/bin/activate` (Linux/macOS), rồi chạy:

```sh
python -m pip install -r requirements.txt
dot -V
python -I -S generated/v1/smart_lock.py --events password_ok open_door
```

Nếu không kích hoạt được, thay `python` bằng `.\.venv\Scripts\python.exe`
trên Windows. [Hai file sinh](generated/) chỉ dùng thư viện chuẩn, không
import logic gốc; ví dụ lockout:

```sh
python -I -S generated/v1/smart_lock.py --events password_bad password_bad password_bad
```

Chạy lần lượt BFS, kiểm chứng cả v0/v1 và sinh lại mã/sơ đồ vào thư mục mới:

```sh
python -X utf8 run.py --output-dir tmp/recheck
python -X utf8 run.py --verify --output-dir tmp/recheck
python -X utf8 run.py --artifacts --output-dir tmp/recheck --generated-dir tmp/gen
python -X utf8 -m pytest --color=no -p no:cacheprovider -v
```

Bộ dự án có **199 tests**. Audit mã sinh đối chiếu **702 trường hợp**
(mọi state x 9 events x hai ngữ cảnh quyền), khớp **115/115 cạnh**;
702 không phải số tests pytest. [Chi tiết audit](results/g4/experiment_summary.json),
[log tests](results/g5/pytest.log). Môi trường đã kiểm tra: Windows,
Python 3.14.2, pytest 9.1.1, z3-solver 5.1.0.0, Graphviz 16.1.0.
[Kiểm tra source sạch](results/reproducibility.json), [log tái lập](results/reproducibility.log).

## 7. Giới hạn và tài liệu tham khảo

Input mật khẩu/admin đã trừu tượng hóa; action nguyên tử; không mô hình hóa
phần cứng, mất điện, mạng hoặc thời gian thực. v1 chỉ cho reset_complete
trong resetting; runtime cần bên gọi gửi event đó. P2 một chiều cần test
riêng lần sai thứ ba. Kết quả chỉ chứng minh năm đặc tả trên mô hình hữu hạn.

Snapshot được đối chiếu SHA-256; `.gitattributes` giữ nguyên byte. Khi chạy
lại, dùng cùng thư mục mới cho ba lệnh để tránh trộn model và verification
khác lần chạy. Dữ liệu gốc trong `results/` không cần ghi đè.

### 7.1. Tài liệu tham khảo

[1] Vũ Quang Dũng. *Hướng dẫn Bài tập lớn: Chủ đề, phạm vi và quy trình thực hiện*; *Hướng dẫn Báo cáo Bài tập lớn*. Học phần CSE703093, Phenikaa. Tài liệu lớp, không phân phối PDF gốc trong repository.

[2] Học phần An toàn phần mềm. *Chương 1 - Phần 2* (Kripke/CTL); *Chương 3 - Phần 1, Phần 2* (đặc tả, SMT và BMC). Slide được cung cấp trong lớp, không đóng kèm.

[3] softsec-toolkit. Bộ mã được cung cấp trong học phần; dùng lớp [KripkeStructure](toolkit/softsec-toolkit/ch1_models/kripke.py). [Nguồn mã và thông tin phân phối](THIRD_PARTY_NOTICES.md).

[4] Edmund M. Clarke Jr., Orna Grumberg, Daniel Kroening, Doron Peled, Helmut Veith. *Model Checking*, 2nd ed., MIT Press, 2018. [Nhà xuất bản](https://mitpress.mit.edu/9780262038836/model-checking/).

[5] NuSMV project (FBK). *Temporal Logic*. [Tài liệu chính thức về CTL](https://nusmv.fbk.eu/papers/sttt_j/html/node3.html).

[6] Armin Biere, Alessandro Cimatti, Edmund Clarke, Yunshan Zhu. *Symbolic Model Checking without BDDs*. TACAS 1999, LNCS 1579, tr. 193-207. [DOI: 10.1007/3-540-49059-0_14](https://link.springer.com/chapter/10.1007/3-540-49059-0_14).

[7] Microsoft/Z3 project. *Online Z3 Guide - Z3 Python: Introduction*. [Hướng dẫn chính thức](https://microsoft.github.io/z3guide/programming/Z3%20Python/Introduction/).

[8] Graphviz project. *DOT Language*. [Tài liệu chính thức](https://graphviz.org/doc/info/lang.html).

[9] Python Software Foundation. *venv - Creation of virtual environments*. [Python documentation](https://docs.python.org/3/library/venv.html).

### 7.2. Công khai hỗ trợ AI và đóng góp nhóm

AI hỗ trợ code, chỉnh sửa mã nguồn.
