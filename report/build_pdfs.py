"""Biên soạn hai tài liệu G5 từ Markdown và trích đoạn nguyên bản G1-G4.

Không kiểm chứng, sinh lại hoặc sửa mã Smart Lock. Chạy từ mọi cwd:
    python report/build_pdfs.py
Phụ thuộc: report/requirements-report.txt; Times New Roman và Consolas
trong C:/Windows/Fonts, hoặc thư mục do REPORT_FONT_DIR chỉ định.
"""

from collections import defaultdict
from html import escape
import io
import json
import keyword
import os
from pathlib import Path
import re
import textwrap
import tokenize

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents
from svglib.svglib import svg2rlg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report"
INK = colors.HexColor("#18364a")
GRAY = colors.HexColor("#52616b")
W, H = A4
LEFT, RIGHT, TOP, BOTTOM = 70.87, 56.69, 56.69, 56.69
WIDTH = W - LEFT - RIGHT


def register_fonts():
    folder = Path(os.environ.get("REPORT_FONT_DIR", "C:/Windows/Fonts"))
    for name, filename in {"TimesVN": "times.ttf", "TimesVN-Bold": "timesbd.ttf",
                           "TimesVN-Italic": "timesi.ttf", "TimesVN-BoldItalic": "timesbi.ttf",
                           "CodeVN": "consola.ttf", "Arial": "arial.ttf",
                           "MathVN": "cambria.ttc"}.items():
        pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
    pdfmetrics.registerFontFamily("TimesVN", normal="TimesVN", bold="TimesVN-Bold",
                                  italic="TimesVN-Italic", boldItalic="TimesVN-BoldItalic")


def styles():
    base = dict(fontName="TimesVN", fontSize=12, leading=18, textColor=colors.black)
    return {
        "body": ParagraphStyle("Body", **base, alignment=TA_JUSTIFY, spaceAfter=7),
        "bullet": ParagraphStyle("Bullet", **base, leftIndent=12, firstLineIndent=-10, spaceAfter=5),
        "h1": ParagraphStyle("Chapter", fontName="TimesVN-Bold", fontSize=16, leading=22,
                             textColor=INK, spaceAfter=12, keepWithNext=True),
        "h2": ParagraphStyle("Section", fontName="TimesVN-Bold", fontSize=13, leading=19,
                             textColor=INK, spaceBefore=8, spaceAfter=7, keepWithNext=True),
        "caption": ParagraphStyle("Caption", fontName="TimesVN-Italic", fontSize=10.5,
                                  leading=14, alignment=TA_CENTER, spaceBefore=5, spaceAfter=8),
        "cell": ParagraphStyle("Cell", fontName="TimesVN", fontSize=10.5, leading=14),
        "headcell": ParagraphStyle("HeadCell", fontName="TimesVN-Bold", fontSize=10.5,
                                   leading=14, textColor=colors.white),
        "code": ParagraphStyle("Code", fontName="CodeVN", fontSize=9.0, leading=12,
                               leftIndent=6, rightIndent=6, spaceAfter=0),
        "formula": ParagraphStyle("Formula", fontName="CodeVN", fontSize=9.7, leading=14,
                                  spaceBefore=4, spaceAfter=9, leftIndent=6),
        "cover": ParagraphStyle("Cover", fontName="TimesVN-Bold", fontSize=22, leading=30,
                                textColor=INK, alignment=TA_CENTER, spaceAfter=15),
        "center": ParagraphStyle("Center", **base, alignment=TA_CENTER, spaceAfter=8),
    }


def inline(text):
    value = escape(text)
    value = re.sub(r"`([^`]+)`", r'<font name="CodeVN" size="10">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r'<b>\1</b>', value)
    value = re.sub(r"\[([^]]+)\]\((https?://[^)]+)\)", r'<link href="\2" color="#1d4b70">\1</link>', value)
    return value


class SourceCode(Flowable):
    """Khối code nguyên bản có số dòng và tô màu token Python, không sửa dòng."""
    def __init__(self, code, start_line=1, python=True):
        Flowable.__init__(self)
        self.lines = code.splitlines()
        self.start_line = start_line
        self.spans = defaultdict(list)
        if python:
            try:
                for token in tokenize.generate_tokens(io.StringIO(code).readline):
                    color = ("#536472" if token.type == tokenize.COMMENT else
                             "#8c3b13" if token.type == tokenize.STRING else
                             "#1d4ed8" if token.string in keyword.kwlist else
                             "#7e22ce" if token.type == tokenize.NUMBER else None)
                    if color:
                        for row in range(token.start[0], token.end[0] + 1):
                            begin = token.start[1] if row == token.start[0] else 0
                            end = token.end[1] if row == token.end[0] else len(self.lines[row - 1])
                            self.spans[row - 1].append((begin, end, color))
            except (tokenize.TokenError, IndentationError):
                pass  # Trích đoạn có thể bắt đầu giữa một khối Python.
        self.height = len(self.lines) * 12 + 16

    def wrap(self, available_width, available_height):
        self.width = available_width
        longest = max((self.text_width(line, 9) for line in self.lines), default=0)
        self.size = min(9, (available_width - 43) / max(longest, 1) * 9)
        if self.size < 7.5:
            raise ValueError("Code quá dài một dòng; chọn trích đoạn ngắn hơn hoặc phụ lục")
        return self.width, self.height

    @staticmethod
    def font_for(char):
        font = "CodeVN" if ord(char) in pdfmetrics.getFont("CodeVN").face.charToGlyph else "MathVN"
        if ord(char) not in pdfmetrics.getFont(font).face.charToGlyph:
            raise ValueError(f"Font không có ký tự code {char!r}")
        return font

    @classmethod
    def text_width(cls, text, size):
        return sum(pdfmetrics.stringWidth(char, cls.font_for(char), size) for char in text)

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor("#f3f5f6"))
        c.roundRect(0, 0, self.width, self.height, 3, stroke=0, fill=1)
        c.setFont("CodeVN", self.size)
        for row, line in enumerate(self.lines):
            y = self.height - 17 - row * 12
            c.setFillColor(GRAY)
            c.drawRightString(27, y, str(self.start_line + row))
            cuts = {0, len(line)}
            for begin, end, _ in self.spans[row]:
                cuts.update((begin, end))
            positions = sorted(cuts)
            for begin, end in zip(positions, positions[1:]):
                color = next((color for a, b, color in self.spans[row] if a <= begin < b), "#17202a")
                c.setFillColor(colors.HexColor(color))
                x = 36 + self.text_width(line[:begin], self.size)
                for char in line[begin:end]:
                    font = self.font_for(char)
                    c.setFont(font, self.size)
                    c.drawString(x, y, char)
                    x += pdfmetrics.stringWidth(char, font, self.size)


class Report(BaseDocTemplate):
    def __init__(self, destination, title):
        super().__init__(str(destination), pagesize=A4, leftMargin=LEFT, rightMargin=RIGHT,
                         topMargin=TOP, bottomMargin=BOTTOM, title=title,
                         author="Nhóm 4 sinh viên - thông tin chờ điền", allowSplitting=1)
        frame = Frame(LEFT, BOTTOM, WIDTH, H - TOP - BOTTOM, leftPadding=0,
                      rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates(PageTemplate(id="normal", frames=frame, onPage=self.decorate))
        self.entries = []

    def beforeDocument(self):
        self.entries = []

    def decorate(self, canvas, doc):
        if doc.page == 1:
            return
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5da"))
        canvas.line(LEFT, H - 38, W - RIGHT, H - 38)
        canvas.setFont("TimesVN", 9)
        canvas.setFillColor(GRAY)
        canvas.drawString(LEFT, H - 30, "CSE703093 | Kripke + CTL + BMC/Z3 | Smart Lock")
        canvas.drawCentredString(W / 2, 32, str(doc.page))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and hasattr(flowable, "toc_level"):
            text = flowable.getPlainText()
            key = flowable.bookmark_key
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(text, key, level=flowable.toc_level, closed=False)
            self.notify("TOCEntry", (flowable.toc_level, text, self.page, key))
            self.entries.append({"title": text, "page": self.page, "level": flowable.toc_level})


def cover(st, study=False):
    title = "TÀI LIỆU HỌC VÀ GIẢI THÍCH CODE" if study else "BÁO CÁO BÀI TẬP LỚN"
    return [Spacer(1, 18), Paragraph("TRƯỜNG ĐẠI HỌC PHENIKAA", st["center"]),
            Paragraph("KHOA HỆ THỐNG THÔNG TIN", st["center"]), Spacer(1, 24),
            Paragraph(title, st["cover"]),
            Paragraph("Mô hình hóa và kiểm chứng hình thức<br/>với mô hình Kripke", st["cover"]),
            Paragraph("Hệ thống nghiên cứu: Smart Lock", st["center"]),
            Paragraph("CSE703093 - An toàn phần mềm", st["center"]), Spacer(1, 16),
            Paragraph("Giảng viên hướng dẫn: ThS. Vũ Quang Dũng", st["center"]),
            Paragraph("Lớp: [NHÓM ĐIỀN] | Học kỳ, năm học: [NHÓM ĐIỀN]", st["center"]),
            Spacer(1, 12), make_table([
                ["Thành viên", "Họ và tên", "MSSV"],
                *[[f"Người {i}", "[NHÓM ĐIỀN]", "[NHÓM ĐIỀN]"] for i in range(1, 5)],
            ], st), Spacer(1, 22),
            Paragraph("Tài liệu nội bộ phục vụ đọc code và chuẩn bị trả lời" if study else
                      "Chủ đề 1: Mô hình hóa và kiểm chứng hình thức (Kripke + BMC)", st["center"]),
            Paragraph("Ngày tổng hợp bằng chứng: 15/10/2026", st["center"]), PageBreak()]


def make_table(rows, st, widths=None):
    if widths is None:
        count = len(rows[0])
        widths = [WIDTH / count] * count
    data = [[Paragraph(inline(str(cell)), st["headcell"] if i == 0 else st["cell"])
             for cell in row] for i, row in enumerate(rows)]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f7")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5da")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def evidence_tables():
    audit = json.loads((ROOT / "results/g5/evidence_audit.json").read_text(encoding="utf-8"))
    versions = audit["versions"]
    tables = {}
    tables["stats"] = [["Đại lượng", "v0", "v1"]] + [
        [label, *[versions[v]["statistics"][key] for v in ("v0", "v1")]]
        for key, label in [("reachable_states", "States reachable"), ("event_transitions", "Transitions có sự kiện"),
                           ("relation_pairs", "Cặp quan hệ R"), ("max_bfs_depth", "D (độ sâu ngắn nhất lớn nhất)")]]
    tables["results"] = [["P", "Phương pháp", "v0", "v1", "Bound safety"]] + [
        [pid, "CTL fixed-point" if pid == "P5" else "Đồ thị + Z3",
         versions["v0"]["ctl_status"][pid], versions["v1"]["ctl_status"][pid],
         "Không áp dụng" if pid == "P5" else "v0: 0..1" if pid == "P1" else "0..5"]
        for pid in ("P1", "P2", "P3", "P4", "P5")]
    tables["audit"] = [["Phiên bản", "Phép so", "Chấp nhận", "Từ chối", "Cạnh khớp"]] + [
        [v, *[versions[v]["generated_audit"][key] for key in
              ("cases_checked", "accepted_cases", "rejected_cases", "distinct_edges_matched")]]
        for v in ("v0", "v1")]
    tables["solver"] = [["Phiên bản", "Lượt check", "SAT", "UNSAT", "UNKNOWN"]] + [
        [v, versions[v]["solver_calls"], *[versions[v]["solver_outcomes"][k] for k in ("SAT", "UNSAT", "UNKNOWN")]]
        for v in ("v0", "v1")]
    tables["metrics"] = [["File", "Dòng vật lý", "Hàm/method"]] + [
        [name, row["lines"], row["functions_including_methods"]]
        for name, row in audit["code_metrics"].items() if not name.endswith("__init__.py")]
    return tables


def parse_markdown(path, st, tables):
    """Cú pháp tài liệu cố định: @page, @code path first last, @figure name height, @table key."""
    lines = path.read_text(encoding="utf-8").splitlines()
    story = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("<!--"):
            i += 1
            continue
        if line == "@page":
            story.append(PageBreak())
        elif line.startswith("@code "):
            _, filename, begin, end = line.split()
            begin, end = int(begin), int(end)
            source = (ROOT / filename).read_text(encoding="utf-8").splitlines()
            excerpt = textwrap.dedent("\n".join(source[begin - 1:end]))
            story.append(KeepTogether([Paragraph(f"{escape(filename)} : dòng {begin}-{end}", st["caption"]),
                                       SourceCode(excerpt, begin), Spacer(1, 8)]))
        elif line.startswith("@figure "):
            _, name, height = line.split()
            drawing = svg2rlg(str(ROOT / "results/g4/diagrams" / (name + ".svg")))
            factor = min(WIDTH / drawing.width, float(height) / drawing.height)
            drawing.scale(factor, factor)
            drawing.width *= factor
            drawing.height *= factor
            drawing.hAlign = "CENTER"
            story.append(drawing)
        elif line.startswith("@table "):
            story.append(make_table(tables[line.split()[1]], st))
            story.append(Spacer(1, 8))
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", cell) for cell in row):
                    rows.append(row)
                i += 1
            story += [make_table(rows, st), Spacer(1, 8)]
            continue
        elif line.startswith("```"):
            language = line[3:]
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i]); i += 1
            story += [SourceCode("\n".join(block), python=language == "python"), Spacer(1, 8)]
        elif line.startswith("# "):
            p = Paragraph(inline(line[2:]), st["h1"])
            p.toc_level = 0
            p.bookmark_key = "section_" + str(len(story))
            story.append(p)
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), st["h2"]))
        elif line.startswith("> "):
            story.append(Paragraph(inline(line[2:]), st["formula"]))
        elif line.startswith("- "):
            story.append(Paragraph("• " + inline(line[2:]), st["bullet"]))
        else:
            block = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith(("#", "@", "|", "```", "> ", "- ")):
                i += 1; block.append(lines[i].strip())
            story.append(Paragraph(inline(" ".join(block)), st["body"]))
        i += 1
    return story


def build(name, study=False):
    st = styles()
    title = "Tài liệu học và giải thích code Smart Lock" if study else "Mô hình hóa và kiểm chứng hình thức với mô hình Kripke"
    doc = Report(OUT / (name + ".pdf"), title)
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("TOC0", fontName="TimesVN", fontSize=12,
                                      leading=19, spaceBefore=7, leftIndent=0)]
    story = cover(st, study) + [Paragraph("MỤC LỤC", st["h1"]), toc,
                              Spacer(1, 18), Paragraph("Mục lục được tạo tự động theo số trang PDF; số trang tính từ bìa. "
                              "Các mục phụ lục nằm sau phần nội dung chính.", st["caption"]), PageBreak()]
    story += parse_markdown(OUT / (name + ".md"), st, evidence_tables())
    doc.multiBuild(story)
    return {"file": name + ".pdf", "toc": doc.entries, "pages": doc.page,
            "body_font": "Times New Roman", "body_font_size": 12, "body_leading": 18}


if __name__ == "__main__":
    register_fonts()
    metadata = [build("BaoCao_BTL_Kripke"), build("TaiLieu_HocVaGiaiThichCode", study=True)]
    (ROOT / "results/g5/pdf_build.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in metadata:
        print(item["file"], item["pages"], "pages")
