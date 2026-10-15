# Phân công nghiên cứu và chuẩn bị báo cáo

Đây là phân công đề xuất, chưa phải xác nhận đóng góp thực tế. Nhóm điền
họ tên/MSSV, điều chỉnh trách nhiệm và xác nhận sau khi từng người đã
đọc, chạy, giải thích được code. Không tạo bốn hệ thống độc lập.

| Thành viên | Họ tên / MSSV | File cần đọc | Phần báo cáo | Kiến thức cần nắm | Câu hỏi phải tự trả lời |
|---|---|---|---|---|---|
| Người 1 | [NHÓM ĐIỀN] / [NHÓM ĐIỀN] | smartlock/model.py; kripke.py; tests/test_model.py; test_kripke.py; results/v0,v1/model.json | Chương 1-2; bảng biến/guard/action; Phụ lục A/B | Sáu biến, input admin, AP độc lập; State frozen; BFS/FIFO/seen/parents/depth; S/S0/R/L | Vì sao 21/18 thay vì 192? Vì sao event edge nhiều hơn R? Khóa lần thứ ba nằm ở đâu? Constructor có che lỗi không? |
| Người 2 | [NHÓM ĐIỀN] / [NHÓM ĐIỀN] | smartlock/ctl.py; model.py::labels; tests/test_verification.py (CTL, AF, lasso); docs/G3_GiaiThich.md | Chương 3; phối hợp Chương 6 | AG/AF, safety/liveness; bad-state; least fixed-point; totality; tiền đề đạt được | Vì sao P5 không dùng bad-state? Z0/expanded hoạt động sao? Vì sao có complete mà v0 vẫn sai? P2 một chiều có giới hạn gì? |
| Người 3 | [NHÓM ĐIỀN] / [NHÓM ĐIỀN] | smartlock/bmc.py; kripke.py::make_trace/replay_trace; ctl.py::validate_counterexample; run.py::_verify; JSON G3; tests/test_verification.py | Chương 4; Bảng 4.1/4.2; Hình CE; lệnh kiểm chứng | I/domain/T/bad; k và D; Solver.add/check/model; SAT/UNSAT/UNKNOWN/ERROR; giải mã và replay | 44 check đến từ đâu? Query k=0 có gì? Vì sao k=1 P1 v0 SAT/ngắn nhất? UNSAT nhỏ hơn D kết luận gì? |
| Người 4 | [NHÓM ĐIỀN] / [NHÓM ĐIỀN] | smartlock/artifacts.py; generated/v0,v1/smart_lock.py; tests/test_artifacts.py; results/g4; results/g5; report/build_pdfs.py | Chương 5; tổng hợp Chương 7; Phụ lục C/D; rà định dạng/gói nộp | Sinh literal từ JSON; runtime tra bảng; bất định; toàn miền S×E×quyền; SVG/DOT; provenance/hash | Chứng minh mã sinh không viết tay thế nào? 702 khác 115 ra sao? Cạnh thừa bị bắt thế nào? File có chạy riêng không? |

## Trách nhiệm chung

- Cả bốn người đọc hai hướng dẫn giảng viên, toàn bộ Chương 6 và khai báo AI
  trong Chương 7. Kết luận chỉ trên mô hình hữu hạn, không phải khóa vật lý.
- Mỗi người tự chạy authentication/door, lockout, alarm/recovery và hai CE v0;
  giải thích được ID và sáu giá trị mỗi bước, kể cả quyền admin tường minh.
- Đọc `report/TaiLieu_HocVaGiaiThichCode.pdf`, tự trả lời 25 câu hỏi trước
  khi xem đáp án. Đổi câu hỏi chéo giữa người 1/3 và người 2/4.
- Kiểm tra số liệu trong `results/g5/evidence_audit.json`, tests cuối cùng,
  mục lục và hình PDF; không lấy số PASS để gọi v0 an toàn.
- Giữ mô tả AI hỗ trợ đáng kể đúng thực tế; không ký xác nhận đã tự kiểm
  hoặc đã đóng góp một phần việc khi chưa thực hiện.

## Những chỗ cần nhóm tự điền trước khi nộp

1. Họ tên/MSSV bốn thành viên; tên nhóm; lớp, học kỳ và năm học.
2. Xác nhận tên trường/khoa/giảng viên trên bìa phù hợp lớp thực tế
   (hiện lấy từ hướng dẫn: Phenikaa, Khoa Hệ thống thông tin, ThS. Vũ Quang Dũng).
3. Phân công và đóng góp thực tế; ngày nhóm rà soát/chấp nhận bản cuối.
4. Mẫu tên thư mục/PDF nộp theo thông báo lớp; hiện dùng tên đề tài do người dùng yêu cầu.
5. Kiểm tra URL repository và quyền truy cập của giảng viên; README dùng origin
   `https://github.com/bbaonngoc/kripke-model-checking.git`. Hình thức nộp hiện tại
   là gửi link GitHub, không nộp ZIP; xác nhận quyền công khai module toolkit.

Sửa thông tin bìa tại `report/build_pdfs.py::cover`, nội dung tại hai Markdown
trong report/, rồi xuất lại PDF theo README. Không sửa trực tiếp mã sinh hoặc
mô hình để thay đổi kết quả của báo cáo.
