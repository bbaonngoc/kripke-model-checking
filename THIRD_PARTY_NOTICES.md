# Nguồn mã và quyền phân phối

`toolkit/softsec-toolkit/ch1_models/kripke.py` là module nguyên bản được
cung cấp cùng tài liệu thực hành môn An toàn phần mềm. Dự án dùng lớp
`KripkeStructure` của module này; các chương và tài nguyên khác của toolkit
không cần để chạy dự án và không được đưa vào repository.

Trong bản tài nguyên được cung cấp chưa tìm thấy LICENSE, COPYING hoặc
thông báo cho phép phân phối công khai. Việc được cung cấp để học tập chưa
được coi là xác nhận quyền công khai trên GitHub. **Đang chờ nhóm xác nhận
quyền phân phối module này trước khi công khai repository.** Không tự gán
giấy phép cho mã của tác giả/giảng viên.

Các PDF bài giảng, hướng dẫn và tài nguyên thực hành gốc trong `references/`
được giữ ở máy làm việc, bị Git bỏ qua, không phải dependency của 199 tests
dự án. Các log G1 có lưu kết quả tham chiếu lịch sử; chúng không có nghĩa
là những tài nguyên gốc được phân phối trong repository này.

Python, pytest, Z3 và Graphviz được cài riêng từ nguồn của từng dự án,
không đóng kèm binary hoặc môi trường ảo. Tham khảo giấy phép tại nguồn:
[Python](https://docs.python.org/3/license.html),
[pytest](https://github.com/pytest-dev/pytest/blob/main/LICENSE),
[Z3](https://github.com/Z3Prover/z3/blob/master/LICENSE.txt),
[Graphviz](https://graphviz.org/license/).
