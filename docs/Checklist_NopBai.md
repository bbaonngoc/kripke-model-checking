# Checklist bàn giao qua GitHub

Căn cứ: `references/BTL_01_HuongDan_DeTai.pdf` (27 trang) và
`references/BTL_02_HuongDan_BaoCao.pdf` (27 trang). PASS chỉ áp dụng
những mục đã có bằng chứng. Mục cần thông tin cá nhân được ghi CHỜ NHÓM,
không tự đánh dấu hoàn tất thay các thành viên.

| Yêu cầu | Căn cứ | Trạng thái / nơi kiểm tra |
|---|---|---|
| Chủ đề Kripke + BMC, hệ thống nhỏ, ít nhất 3 CTL safety/liveness | BTL_01 tr. 5, 9-10 | ĐẠT: Smart Lock, 5 chức năng, 5 CTL, 2 phiên bản, 1 graph tích hợp mỗi phiên bản |
| Áp dụng ít nhất 2 chương thực chất | BTL_01 tr. 19 | ĐẠT: Chương 1 với State/guard/action/BFS/Kripke thật; Chương 3 với CTL/BMC/Z3 thật; không chỉ dùng Chương 1 làm nền lý thuyết |
| Lỗi cố ý được nêu rõ, so trước/sau sửa | BTL_01 tr. 21 | ĐẠT: BUG-01 xác thực, BUG-02 reset liveness; báo cáo Chương 2, 4-5 |
| PDF tiếng Việt, nội dung chính 10-20 trang, cỡ 12pt, giãn dòng 1.5 | BTL_02 tr. 4 | ĐẠT: 18 trang chính, Times New Roman 12pt/leading 18; code/bảng nhỏ hơn; results/g5/pdf_qa.json |
| Bìa và mục lục tự động, có số trang | BTL_02 tr. 6 | ĐẠT phần cấu trúc/TOC; CHỜ NHÓM điền họ tên/MSSV/lớp/học kỳ |
| Mô tả hệ thống, input/output, sơ đồ, quy mô mã | BTL_02 tr. 9 | ĐẠT: Chương 1-2, 5, Phụ lục A-C; input trừu tượng và giới hạn nêu rõ |
| Phương pháp cụ thể, nguồn toolkit rõ | BTL_02 tr. 11, 13 | ĐẠT: tên file/hàm, I/domain/T/bad, bound, fixed-point; toolkit nguyên bản |
| Mọi số liệu có log/JSON/ảnh, giải thích ý nghĩa | BTL_02 tr. 14-16 | ĐẠT: results/G1-G5; evidence_audit.json không có chênh lệch; CE P1/P5 có state/event cụ thể |
| Hạn chế trung thực, không nhầm bound với toàn cục | BTL_02 tr. 17-18 | ĐẠT: Chương 4, 6; D=5 chỉ cho bad-state safety, P5 fixed-point; caller gửi reset_complete |
| Code ngắn, có định dạng/tô màu, nộp đủ mã | BTL_02 tr. 20 | ĐẠT: trích 8-16 dòng mỗi block trong báo cáo, số dòng thật, màu token; source đầy đủ trong repository |
| Nguồn tài liệu/mã, phạm vi AI hỗ trợ | BTL_02 tr. 19, 23 | ĐẠT: Chương 7 ghi giảng viên/toolkit/Z3/NuSMV/Graphviz/CWE và AI hỗ trợ đáng kể; nhóm xác minh trước khi nộp |
| README, dependencies, mã chạy lại được | BTL_01 tr. 19; BTL_02 tr. 21-22 | Xem README mới và results/github/validation.json: kiểm tra cây source qua Git, venv mới, 199 tests dự án |
| Kiểm tra chính tả/định dạng/TOC/hình/công thức | BTL_02 tr. 22 | ĐẠT: render và rà hai PDF; kiểm mục lục, font, bounds, 7 sơ đồ; pdf_qa.json |
| Tên thư mục/PDF theo MSSV/họ tên | BTL_02 tr. 21-22 | CHỜ NHÓM: đang dùng tên placeholder, không có MSSV/họ tên thật |
| Phân công và khả năng giải thích của cả nhóm | BTL_01 tr. 21; yêu cầu người dùng | ĐÃ SOẠN đề xuất ở PhanCongNhom.md và 25 Q&A; CHỜ NHÓM xác nhận đóng góp/học code thực tế |

## Thành phần repository gửi giảng viên

- `report/`: hai PDF, hai nguồn Markdown, build_pdfs.py, requirements-report.txt.
- `smartlock/`, `generated/`, `tests/`, `run.py`, `pytest.ini`, `requirements.txt`.
- `toolkit/softsec-toolkit/ch1_models/kripke.py`: chỉ module Kripke cần thiết.
  CHỜ NHÓM xác nhận quyền công khai; xem THIRD_PARTY_NOTICES.md.
- `docs/`: G1-G4, phân công và checklist; `results/`: bằng chứng G1-G5, sơ đồ.
- `README.md`, requirements được chốt phiên bản, `.gitattributes` giữ nguyên byte
  của bằng chứng; `results/github/` ghi kiểm tra source sạch và danh sách file.
- `references/`, ZIP và `report/package_submission.py` bị Git bỏ qua, giữ nguyên
  trên ổ đĩa. Giảng viên chỉ cần link GitHub, không có bước nộp ZIP.
- Log G1/G5 tham chiếu được giữ như lịch sử; 4 tests từ tài liệu lớp không nằm
  trong 199 tests dự án và không phải dependency để chạy lại repository.

Không xóa file gốc hoặc sửa logic G1–G4. Chưa commit/push. Trước khi công khai,
nhóm xác nhận quyền toolkit, điền thông tin nhóm và kiểm tra quyền truy cập
repository của giảng viên. Hai PDF G5 được giữ nguyên; các chỗ nói về gói nộp
trong tài liệu lịch sử không thay đổi hình thức bàn giao GitHub hiện tại.
