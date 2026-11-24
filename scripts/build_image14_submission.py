from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "artifacts" / "submission" / "BRACE-MSI-IMAGE14-0.10.6rc1-final-no-ppt"
IMAGE_TAR = Path(r"D:\brace-msi-first-principles-release\BRACE-MSI-0.10.6rc1-A1\harness.tar")
RELEASE_MANIFEST = IMAGE_TAR.with_name("release-manifest.json")
SOURCE_COMMIT = "c653e0e04297b655b93e28a90abd9f36e2ff761d"
ARCHIVE_SHA256 = "F7518609974EAB3C156C07F6D0AA7CBFE6CF9253B43C5D20B3DC71B4C91D89CB"
IMAGE_ID = "sha256:52333ab152aa11a4a6b14a8270fcebe3e1e2290813f18ac77bf46e1810ca7504"
IMAGE_TAG = "brace-msi:0.10.6rc1"
SWANLAB_URL = "https://swanlab.cn/@nanmo-max/brace-msi-final"
SOURCE_URL = f"https://github.com/nanmo-max/rengongzhineng/tree/{SOURCE_COMMIT}"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, start=100, bottom=100, end=100) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def base_document(title: str, subtitle: str) -> Document:
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.2

    for style_name, size in (("Title", 22), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11)):
        style = styles[style_name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.bold = True

    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run(title)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(subtitle)
    run.bold = True
    run.font.size = Pt(12)
    doc.add_paragraph()
    return doc


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(item)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for index, text in enumerate(headers):
        cell = table.rows[0].cells[index]
        set_cell_shading(cell, "1F4E78")
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)
        run.font.size = Pt(9)
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for col_index, value in enumerate(values):
            cell = cells[col_index]
            if row_index % 2:
                set_cell_shading(cell, "EEF4F8")
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if col_index == 0 else WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(str(value))
            run.font.size = Pt(8.5)
    if widths:
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = Cm(width)
    doc.add_paragraph()


def add_footer(doc: Document, text: str) -> None:
    for section in doc.sections:
        footer = section.footer
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(100, 100, 100)


def build_run_guide(path: Path) -> None:
    doc = base_document(
        "BRACE MSI 镜像14系统运行说明",
        "正式绑定版本 0.10.6rc1  官方平台已完成十轮试运行",
    )
    doc.add_paragraph(
        "本说明用于上传、选择和运行平台镜像14。镜像14已经由项目负责人确认对应本地归档 brace-msi:0.10.6rc1。"
        "Docker归档、源码提交和平台试运行证据按同一版本绑定，不混入其他版本的镜像或材料。"
    )

    add_heading(doc, "一 版本与文件身份")
    add_table(
        doc,
        ["项目", "固定值"],
        [
            ["平台镜像", "镜像14"],
            ["Docker标签", IMAGE_TAG],
            ["归档文件", str(IMAGE_TAR)],
            ["归档大小", "81,208,320字节 约77.45 MiB"],
            ["归档SHA 256", ARCHIVE_SHA256],
            ["镜像ID", IMAGE_ID],
            ["源码提交", SOURCE_COMMIT],
            ["运行协议", "contest.harness.workspace.v2  SDK 1.0.2"],
        ],
        [4.2, 11.8],
    )

    add_heading(doc, "二 平台提交步骤")
    add_bullets(
        doc,
        [
            "镜像已在原平台导入时，选择状态为镜像可用的镜像14；在其他平台重新上传时，直接上传本说明列出的harness.tar。",
            "模型类型选择基础模型，基础模型选择Qwen/Qwen3.8-27B。镜像通过官方宿主rnd.model调用模型服务，不在镜像内携带Qwen权重。",
            "PyTRiO API Key只填写在平台受保护字段，不写入镜像、源码、文档、日志或SwanLab。",
            f"源码仓库填写 {SOURCE_URL}。",
            "训练记录字段填写材料包中的记录链接；镜像14精确十轮证据以随包官方试运行报告为准。",
            "保存版本后先执行平台校验。校验通过后再启动试运行；不要把材料ZIP、源码ZIP或Dockerfile改名为tar上传。",
        ],
    )

    add_heading(doc, "三 运行环境与接口")
    doc.add_paragraph(
        "镜像为linux/amd64、非root用户10001:10001。正式运行仅包含官方SDK、NumPy工业模型训练和固定入口；"
        "不包含训练数据、父checkpoint、隐藏数据、API Key、PyTRiO私有客户端、SwanLab客户端或大模型权重。"
    )
    add_table(
        doc,
        ["阶段", "平台输入", "镜像行为", "平台输出"],
        [
            ["轮次开始", "当前数据 父checkpoint 历史状态", "读取任务合同和历史 通过宿主模型提出训练Recipe", "训练提案与调用ID"],
            ["候选训练", "当前合法数据", "从父checkpoint执行CPU续训并本地计算主辅指标", "候选checkpoint及聚合指标"],
            ["部署决策", "父候选指标 资源 历史", "第二次宿主模型调用决定部署 保留或回滚 硬约束失败关闭", "选中产物和轮收据"],
            ["预测", "最终选中checkpoint 隐藏输入", "独立预测入口输出逐行id和outputs", "预测结果"],
        ],
        [2.6, 4.0, 6.5, 3.2],
    )

    add_heading(doc, "四 本地装载与只读核验")
    doc.add_paragraph("以下命令只用于核对Docker归档身份，不替代平台评测：")
    for command in (
        "docker load -i harness.tar",
        "docker image inspect brace-msi:0.10.6rc1 --format {{.Id}}",
        "docker run --rm brace-msi:0.10.6rc1 describe",
    ):
        p = doc.add_paragraph()
        run = p.add_run(command)
        run.font.name = "Consolas"
        run.font.size = Pt(9)
    doc.add_paragraph(
        "装载后镜像ID应为本说明第一节所列值。平台会提供数据和父checkpoint；不得把本地测试数据或模型权重打入正式归档。"
    )

    add_heading(doc, "五 异常处理与回滚")
    add_bullets(
        doc,
        [
            "模型调用失败或结构化响应无效时，记录失败收据并保持父checkpoint，不执行未经授权的任意代码。",
            "候选不可加载、指标非有限、父链错误或产物超限时，硬安全检查拒绝候选并保留父模型。",
            "训练或预测入口异常时保留workspace和轮收据，定位后上传新镜像；不要反复重跑同一不兼容版本。",
            "正式产物为checkpoint.npz，模型产物总量遵循平台64 MiB限制。",
        ],
    )

    add_heading(doc, "六 已确认平台运行结果")
    doc.add_paragraph(
        "镜像14于2026年11月20日完成一次不计正式成绩的试运行：A B C各10轮，共14,773条隐藏预测，"
        "输入Token 72,038、输出Token 2,380。该结果证明平台能够启动镜像、调用宿主模型、完成真实候选训练、父链和隐藏预测。"
    )
    add_table(
        doc,
        ["任务", "隐藏指标", "CPU用时", "运行用时"],
        [
            ["Gas", "Accuracy 0.866558  Macro F1 0.861027", "194.070664秒", "3360.169072秒"],
            ["Bearing", "MAE 230.506729  RMSE 354.669933", "139.098379秒", "3024.992483秒"],
            ["Engine", "MAE 41.087548  RMSE 56.187077  NASA 59,556,459,480.10695", "1358.917803秒", "4056.782814秒"],
        ],
        [2.4, 7.4, 3.0, 3.2],
    )
    doc.add_paragraph(
        "上述为历史试运行事实，不是正式成绩。平台报告也显示部分轮次的大模型数值比较与部署动作存在冲突；"
        "材料保留该已知边界，不把后续版本的修复写入镜像14。"
    )
    add_footer(doc, "BRACE MSI 镜像14 0.10.6rc1 运行说明")
    doc.save(path)


def build_project_description(path: Path) -> None:
    doc = base_document(
        "BRACE MSI 项目说明书",
        "镜像14历史正式候选 0.10.6rc1",
    )
    doc.add_paragraph(
        "BRACE MSI面向工业模型漂移场景，使用Qwen实验决策与确定性Harness协同完成父模型续训、候选评估、部署或回滚。"
        "本说明只描述平台镜像14及其可核验试运行，不混入其他版本的功能、测试结果或镜像哈希。"
    )

    add_heading(doc, "一 赛题问题与系统目标")
    doc.add_paragraph(
        "工业传感器、轴承和发动机数据会随设备老化、工况和环境变化发生分布漂移。静态模型无法持续适应，人工调参又难以在封闭CPU环境中无人值守完成。"
        "系统目标是从平台父checkpoint开始，在每轮合法数据上自主提出实验、执行续训、评价候选并决定部署、保留或回滚，同时记录模型调用、指标和资源。"
    )
    add_bullets(
        doc,
        [
            "不替换官方父模型，不从头训练另一套模型冒充续训。",
            "Qwen负责读历史、选择受控Recipe和解释决策；Harness负责真实执行和硬安全边界。",
            "平台逐轮不向策略返回隐藏成绩；系统使用当前合法数据自行计算主辅指标。",
            "最终隐藏测试只由平台在完整流程结束后执行。",
        ],
    )

    add_heading(doc, "二 系统架构")
    add_table(
        doc,
        ["组件", "职责", "边界"],
        [
            ["官方Workspace SDK", "接收当前数据 父checkpoint 状态及宿主模型服务", "协议contest.harness.workspace.v2"],
            ["Qwen实验决策", "训练前选择Recipe 训练后决定deploy retain rollback", "只输出结构化意图 不直接执行代码"],
            ["工业训练器", "基于父checkpoint执行NumPy Adam续训", "CPU运行 checkpoint.npz保持父兼容"],
            ["本地评估", "计算分类或回归的主辅指标", "不使用平台隐藏标签"],
            ["SafetyGate", "检查产物可加载 指标有限 父链和大小", "只做不可违反的硬约束"],
            ["状态与审计", "保存轮次 历史 调用ID 指标 资源和选择", "不记录密钥或逐样本私有内容"],
        ],
        [3.2, 7.0, 5.8],
    )

    add_heading(doc, "三 每轮自主优化流程")
    add_bullets(
        doc,
        [
            "读取平台提供的父checkpoint、当前合法数据和历史实验摘要。",
            "第一次Qwen调用提出受控训练Recipe及参数；Harness校验结构和允许范围。",
            "从父checkpoint执行一次真实候选训练，并计算父模型与候选模型同作用域指标。",
            "第二次Qwen调用综合主指标、辅助指标、资源和历史，决定部署候选、保留父模型或回滚。",
            "SafetyGate核验checkpoint、指标有限性、父链和64 MiB产物限制。",
            "原子保存选中模型、调用ID、参数、指标、资源和理由，再进入下一轮。",
        ],
    )
    doc.add_paragraph(
        "镜像14每个任务完成10轮，每轮训练一个候选，因此官方报告形成30次真实训练和双阶段模型调用记录。"
    )

    add_heading(doc, "四 三任务指标合同")
    add_table(
        doc,
        ["任务类型", "主指标", "辅助指标", "方向"],
        [
            ["六类气体分类", "Macro F1", "Accuracy", "越高越好"],
            ["轴承寿命回归", "RMSE", "MAE", "越低越好"],
            ["发动机寿命回归", "RMSE", "MAE NASA非对称评分", "误差与NASA越低越好"],
        ],
        [3.8, 3.5, 5.3, 3.0],
    )
    doc.add_paragraph(
        "镜像14依据任务合同处理分类和回归，不根据数据集名称加载另一套模型。不同任务仍可由Qwen选择不同父兼容训练强度。"
    )

    add_heading(doc, "五 数据与检查点约束")
    add_bullets(
        doc,
        [
            "平台是当前轮数据、父checkpoint和宿主模型服务的唯一正式来源。",
            "训练器只接收当前运行上下文提供的数据和历史状态；正式镜像不携带A B C数据。",
            "候选从父checkpoint继续优化，保留模型拓扑、标准化状态、优化器状态和输出协议。",
            "最终预测入口独立于训练入口，输出平台规定的id和outputs。",
            "隐藏测试标签不可见，不参与训练、参数选择或模型回选。",
        ],
    )

    add_heading(doc, "六 Docker与供应链")
    add_table(
        doc,
        ["项目", "镜像14值"],
        [
            ["标签", IMAGE_TAG],
            ["架构", "linux/amd64"],
            ["运行用户", "10001:10001 非root"],
            ["Docker save大小", "81,208,320字节 约77.45 MiB"],
            ["SHA 256", ARCHIVE_SHA256],
            ["镜像ID", IMAGE_ID],
            ["源码提交", SOURCE_COMMIT],
            ["正式镜像禁入", "数据 父权重 测试 模拟器 报告 私有SDK SwanLab Tokenizer Sampler 密钥"],
        ],
        [4.3, 11.7],
    )

    add_heading(doc, "七 平台试运行结果")
    doc.add_paragraph(
        "2026年11月20日的官方平台试运行完成14,773条隐藏预测，输入Token 72,038、输出Token 2,380、合计74,418。"
        "A B C均完成10轮，证明镜像可被平台启动、调用模型、训练、产生checkpoint并执行隐藏预测。"
    )
    add_table(
        doc,
        ["任务", "隐藏样本", "最终隐藏指标", "CPU秒", "墙钟秒"],
        [
            ["Gas", "4,886", "Accuracy 0.866558  Macro F1 0.861027", "194.071", "3360.169"],
            ["Bearing", "200", "MAE 230.506729  RMSE 354.669933", "139.098", "3024.992"],
            ["Engine", "9,687", "MAE 41.087548  RMSE 56.187077  NASA 59,556,459,480.10695", "1358.918", "4056.783"],
        ],
        [2.1, 2.2, 7.4, 2.2, 2.2],
    )

    add_heading(doc, "八 安全与回滚")
    add_bullets(
        doc,
        [
            "模型调用文本不能直接执行任意Shell或Python，只能选择注册的训练Recipe。",
            "产物不可加载、指标非有限、任务schema错误、父链错误或模型过大时拒绝候选。",
            "Qwen可要求retain或rollback；失败时选中父checkpoint，避免破坏稳定模型。",
            "每轮保存宿主model_call_id和模型血缘，支持定位训练、选择和回滚过程。",
            "API Key只由平台注入，不进入源码、镜像、日志或公开记录。",
        ],
    )

    add_heading(doc, "九 已知边界与诚实披露")
    doc.add_paragraph(
        "镜像14取得了较好的Gas和Bearing隐藏结果，但Engine提升有限。平台逐轮报告中还出现Gas第5轮、Bearing第2轮和Engine第4轮的数值关系与部署动作冲突。"
        "这说明大模型自然语言判断可能算错指标方向，而当时Harness主要校验结构化决定和硬安全约束。"
    )
    add_bullets(
        doc,
        [
            "本材料不把其他版本新增的选择、漂移统计或验收能力写成镜像14功能。",
            "SwanLab链接是项目公开研发记录；镜像14精确运行事实以随包官方试运行报告为准。",
            "隐藏试运行不计正式成绩，也不能用于继续对隐藏集调参。",
            "平台没有提供镜像14运行期间的峰值RSS和逐阶段等待耗时，因此不虚构这些数据。",
        ],
    )

    add_heading(doc, "十 复现与材料索引")
    add_table(
        doc,
        ["材料", "入口"],
        [
            ["Docker归档", str(IMAGE_TAR)],
            ["源码", SOURCE_URL],
            ["SwanLab研发记录", SWANLAB_URL],
            ["正式本地验收", "docs/results/FORMAL-EVERY-ROUND-TRAIN-001.md"],
            ["平台试运行原文", "随包05 镜像14官方试运行报告目录"],
        ],
        [4.5, 11.5],
    )
    add_footer(doc, "BRACE MSI 镜像14 0.10.6rc1 项目说明书")
    doc.save(path)


def write_text(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def build_source_zip(path: Path) -> None:
    paths = [
        "Dockerfile.formal",
        "README.md",
        "pyproject.toml",
        "requirements.formal.lock",
        "src/brace_formal",
        "src/contest_harness",
        "scripts/build_formal_release.py",
        "docs/results/FORMAL-EVERY-ROUND-TRAIN-001.md",
    ]
    subprocess.run(
        ["git", "archive", "--format=zip", f"--output={path}", SOURCE_COMMIT, *paths],
        cwd=ROOT,
        check=True,
    )


def pdf_styles() -> dict[str, ParagraphStyle]:
    if not FONT_REGULAR.is_file() or not FONT_BOLD.is_file():
        raise SystemExit("Microsoft YaHei fonts are required for PDF generation")
    pdfmetrics.registerFont(TTFont("MSYH", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("MSYH-Bold", str(FONT_BOLD)))
    return {
        "title": ParagraphStyle(
            "TitleCN",
            fontName="MSYH-Bold",
            fontSize=22,
            leading=30,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleCN",
            fontName="MSYH-Bold",
            fontSize=12,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#333333"),
            spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "H1CN",
            fontName="MSYH-Bold",
            fontSize=15,
            leading=22,
            textColor=colors.black,
            spaceBefore=10,
            spaceAfter=7,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "BodyCN",
            fontName="MSYH",
            fontSize=9.5,
            leading=15,
            textColor=colors.black,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "BulletCN",
            fontName="MSYH",
            fontSize=9.3,
            leading=14.5,
            leftIndent=14,
            firstLineIndent=-9,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "SmallCN",
            fontName="MSYH",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#444444"),
        ),
    }


def pdf_table(styles, headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    data = [[Paragraph(str(value), styles["small"]) for value in headers]]
    for row in rows:
        data.append([Paragraph(str(value), styles["small"]) for value in row])
    table = Table(data, colWidths=[value * cm for value in widths], repeatRows=1, hAlign="CENTER")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9D9D9")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#EEF4F8")))
    table.setStyle(TableStyle(commands))
    return table


def pdf_bullets(story, styles, items: list[str]) -> None:
    for item in items:
        story.append(Paragraph(f"• {item}", styles["bullet"]))


def pdf_footer(canvas, doc, text: str) -> None:
    canvas.saveState()
    canvas.setFont("MSYH", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawCentredString(A4[0] / 2, 1.0 * cm, f"{text}   第 {doc.page} 页")
    canvas.restoreState()


def build_run_guide_pdf(path: Path) -> None:
    styles = pdf_styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=2.0 * cm,
        leftMargin=2.0 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.6 * cm,
        title="BRACE MSI 镜像14系统运行说明",
    )
    story = [
        Paragraph("BRACE MSI 镜像14系统运行说明", styles["title"]),
        Paragraph("正式绑定版本 0.10.6rc1  官方平台已完成十轮试运行", styles["subtitle"]),
        Paragraph(
            "本说明用于上传、选择和运行平台镜像14。项目负责人已确认镜像14对应本地归档brace-msi:0.10.6rc1。"
            "Docker归档、源码提交和平台试运行证据按同一版本绑定，不混入其他版本的镜像或材料。",
            styles["body"],
        ),
        Paragraph("一 版本与文件身份", styles["h1"]),
        pdf_table(
            styles,
            ["项目", "固定值"],
            [
                ["平台镜像", "镜像14"],
                ["Docker标签", IMAGE_TAG],
                ["归档文件", str(IMAGE_TAR)],
                ["归档大小", "81,208,320字节 约77.45 MiB"],
                ["归档SHA 256", ARCHIVE_SHA256],
                ["镜像ID", IMAGE_ID],
                ["源码提交", SOURCE_COMMIT],
                ["运行协议", "contest.harness.workspace.v2  SDK 1.0.2"],
            ],
            [4.0, 12.4],
        ),
        Spacer(1, 8),
        Paragraph("二 平台提交步骤", styles["h1"]),
    ]
    pdf_bullets(
        story,
        styles,
        [
            "原平台选择状态为镜像可用的镜像14；其他平台重新上传时直接上传本说明列出的harness.tar。",
            "模型类型选择基础模型，基础模型选择Qwen/Qwen3.8-27B。镜像经官方宿主rnd.model调用模型服务，不携带Qwen权重。",
            "PyTRiO API Key只填写在平台受保护字段，不写入镜像、源码、文档、日志或SwanLab。",
            f"源码仓库填写 {SOURCE_URL}。",
            "训练记录字段填写材料包中的记录链接；镜像14精确十轮证据以随包官方试运行报告为准。",
            "保存新版本后先执行平台校验，再启动试运行。不要把材料ZIP、源码ZIP或Dockerfile改名为tar上传。",
        ],
    )
    story.extend(
        [
            PageBreak(),
            Paragraph("三 运行环境与接口", styles["h1"]),
            Paragraph(
                "镜像为linux/amd64、非root用户10001:10001。正式运行仅包含官方SDK、NumPy工业模型训练和固定入口；"
                "不包含训练数据、父checkpoint、隐藏数据、API Key、PyTRiO私有客户端、SwanLab客户端或大模型权重。",
                styles["body"],
            ),
            pdf_table(
                styles,
                ["阶段", "平台输入", "镜像行为", "平台输出"],
                [
                    ["轮次开始", "当前数据 父checkpoint 历史状态", "读取任务合同和历史 通过宿主模型提出训练Recipe", "训练提案与调用ID"],
                    ["候选训练", "当前合法数据", "从父checkpoint执行CPU续训并计算主辅指标", "候选checkpoint及指标"],
                    ["部署决策", "父候选指标 资源 历史", "第二次宿主调用决定部署 保留或回滚 硬约束失败关闭", "选中产物和轮收据"],
                    ["预测", "最终checkpoint 隐藏输入", "独立预测入口输出id和outputs", "预测结果"],
                ],
                [2.4, 3.6, 6.5, 3.8],
            ),
            Spacer(1, 8),
            Paragraph("四 本地装载与只读核验", styles["h1"]),
            Paragraph("以下命令只用于核对Docker归档身份，不替代平台评测：", styles["body"]),
            Paragraph("docker load -i harness.tar", styles["small"]),
            Paragraph("docker image inspect brace-msi:0.10.6rc1 --format {{.Id}}", styles["small"]),
            Paragraph("docker run --rm brace-msi:0.10.6rc1 describe", styles["small"]),
            Paragraph(
                "装载后镜像ID应与第一页一致。平台提供数据和父checkpoint；不得把本地测试数据或模型权重打入正式归档。",
                styles["body"],
            ),
            Paragraph("五 异常处理与回滚", styles["h1"]),
        ]
    )
    pdf_bullets(
        story,
        styles,
        [
            "模型调用失败或结构化响应无效时记录失败收据并保持父checkpoint，不执行任意代码。",
            "候选不可加载、指标非有限、父链错误或产物超限时拒绝候选并保留父模型。",
            "训练或预测异常时保留workspace和轮收据，定位后上传新镜像，不反复重跑不兼容版本。",
            "正式产物为checkpoint.npz，模型产物总量遵循平台64 MiB限制。",
        ],
    )
    story.extend(
        [
            PageBreak(),
            Paragraph("六 已确认平台运行结果", styles["h1"]),
            Paragraph(
                "镜像14于2026年11月20日完成一次不计正式成绩的试运行：A B C各10轮，共14,773条隐藏预测，"
                "输入Token 72,038、输出Token 2,380。该结果证明平台能够启动镜像、调用宿主模型、完成真实候选训练、父链和隐藏预测。",
                styles["body"],
            ),
            pdf_table(
                styles,
                ["任务", "隐藏指标", "CPU用时", "运行用时"],
                [
                    ["Gas", "Accuracy 0.866558  Macro F1 0.861027", "194.070664秒", "3360.169072秒"],
                    ["Bearing", "MAE 230.506729  RMSE 354.669933", "139.098379秒", "3024.992483秒"],
                    ["Engine", "MAE 41.087548  RMSE 56.187077  NASA 59,556,459,480.10695", "1358.917803秒", "4056.782814秒"],
                ],
                [2.3, 7.2, 3.2, 3.2],
            ),
            Spacer(1, 8),
            Paragraph(
                "上述为历史试运行事实，不是正式成绩。平台报告也显示部分轮次的大模型数值比较与部署动作存在冲突；"
                "材料保留该已知边界，不把后续版本修复写入镜像14。",
                styles["body"],
            ),
        ]
    )
    footer = lambda canvas, current_doc: pdf_footer(canvas, current_doc, "BRACE MSI 镜像14 0.10.6rc1 运行说明")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def build_project_description_pdf(path: Path) -> None:
    styles = pdf_styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=2.0 * cm,
        leftMargin=2.0 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.6 * cm,
        title="BRACE MSI 项目说明书 镜像14",
    )
    story = [
        Paragraph("BRACE MSI 项目说明书", styles["title"]),
        Paragraph("镜像14历史正式候选 0.10.6rc1", styles["subtitle"]),
        Paragraph(
            "BRACE MSI面向工业模型漂移场景，使用Qwen实验决策与确定性Harness协同完成父模型续训、候选评估、部署或回滚。"
            "本说明只描述平台镜像14及其可核验试运行，不混入其他版本的功能、测试结果或镜像哈希。",
            styles["body"],
        ),
        Paragraph("一 赛题问题与系统目标", styles["h1"]),
        Paragraph(
            "工业传感器、轴承和发动机数据会随设备老化、工况和环境变化发生分布漂移。静态模型无法持续适应，人工调参也难以在封闭CPU环境中无人值守完成。"
            "系统从平台父checkpoint开始，在每轮合法数据上自主提出实验、执行续训、评价候选并决定部署、保留或回滚，同时记录模型调用、指标和资源。",
            styles["body"],
        ),
    ]
    pdf_bullets(
        story,
        styles,
        [
            "不替换官方父模型，不从头训练另一套模型冒充续训。",
            "Qwen负责读历史、选择受控Recipe和解释决策；Harness负责真实执行和硬安全边界。",
            "平台逐轮不向策略返回隐藏成绩；系统使用当前合法数据自行计算主辅指标。",
            "最终隐藏测试只由平台在完整流程结束后执行。",
        ],
    )
    story.extend(
        [
            Paragraph("二 系统架构", styles["h1"]),
            pdf_table(
                styles,
                ["组件", "职责", "边界"],
                [
                    ["官方Workspace SDK", "接收当前数据 父checkpoint 状态及宿主模型服务", "协议contest.harness.workspace.v2"],
                    ["Qwen实验决策", "训练前选择Recipe 训练后决定deploy retain rollback", "结构化意图 不直接执行代码"],
                    ["工业训练器", "基于父checkpoint执行NumPy Adam续训", "CPU运行 checkpoint保持父兼容"],
                    ["本地评估", "计算分类或回归主辅指标", "不使用平台隐藏标签"],
                    ["SafetyGate", "检查产物可加载 指标有限 父链和大小", "只做不可违反的硬约束"],
                    ["状态与审计", "保存轮次 调用ID 指标 资源和选择", "不记录密钥或逐样本私有内容"],
                ],
                [3.4, 7.1, 5.4],
            ),
            PageBreak(),
            Paragraph("三 每轮自主优化流程", styles["h1"]),
        ]
    )
    pdf_bullets(
        story,
        styles,
        [
            "读取平台提供的父checkpoint、当前合法数据和历史实验摘要。",
            "第一次Qwen调用提出受控训练Recipe及参数；Harness校验结构和允许范围。",
            "从父checkpoint执行一次真实候选训练，并计算父模型与候选模型同作用域指标。",
            "第二次Qwen调用综合主指标、辅助指标、资源和历史，决定部署候选、保留父模型或回滚。",
            "SafetyGate核验checkpoint、指标有限性、父链和64 MiB产物限制。",
            "原子保存选中模型、调用ID、参数、指标、资源和理由，再进入下一轮。",
        ],
    )
    story.extend(
        [
            Paragraph("镜像14每个任务完成10轮，每轮训练一个候选，因此平台报告形成30次真实训练和双阶段模型调用记录。", styles["body"]),
            Paragraph("四 三任务指标合同", styles["h1"]),
            pdf_table(
                styles,
                ["任务类型", "主指标", "辅助指标", "方向"],
                [
                    ["六类气体分类", "Macro F1", "Accuracy", "越高越好"],
                    ["轴承寿命回归", "RMSE", "MAE", "越低越好"],
                    ["发动机寿命回归", "RMSE", "MAE NASA非对称评分", "误差与NASA越低越好"],
                ],
                [4.0, 3.5, 5.4, 3.0],
            ),
            Paragraph(
                "镜像14依据任务合同处理分类和回归，不根据数据集名称加载另一套模型。不同任务仍可由Qwen选择不同父兼容训练强度。",
                styles["body"],
            ),
            Paragraph("五 数据与检查点约束", styles["h1"]),
        ]
    )
    pdf_bullets(
        story,
        styles,
        [
            "平台是当前轮数据、父checkpoint和宿主模型服务的唯一正式来源。",
            "训练器只接收当前运行上下文数据和历史状态；正式镜像不携带A B C数据。",
            "候选从父checkpoint继续优化，保留模型拓扑、标准化状态、优化器状态和输出协议。",
            "最终预测入口独立于训练入口，输出平台规定的id和outputs。",
            "隐藏测试标签不可见，不参与训练、参数选择或模型回选。",
        ],
    )
    story.extend(
        [
            PageBreak(),
            Paragraph("六 Docker与供应链", styles["h1"]),
            pdf_table(
                styles,
                ["项目", "镜像14值"],
                [
                    ["标签", IMAGE_TAG],
                    ["架构", "linux/amd64"],
                    ["运行用户", "10001:10001 非root"],
                    ["Docker save大小", "81,208,320字节 约77.45 MiB"],
                    ["SHA 256", ARCHIVE_SHA256],
                    ["镜像ID", IMAGE_ID],
                    ["源码提交", SOURCE_COMMIT],
                    ["正式镜像禁入", "数据 父权重 测试 模拟器 报告 私有SDK SwanLab Tokenizer Sampler 密钥"],
                ],
                [4.2, 12.2],
            ),
            Spacer(1, 8),
            Paragraph("七 平台试运行结果", styles["h1"]),
            Paragraph(
                "2026年11月20日官方平台试运行完成14,773条隐藏预测，输入Token 72,038、输出Token 2,380、合计74,418。"
                "A B C均完成10轮，证明镜像可被平台启动、调用模型、训练、产生checkpoint并执行隐藏预测。",
                styles["body"],
            ),
            pdf_table(
                styles,
                ["任务", "隐藏样本", "最终隐藏指标", "CPU秒", "墙钟秒"],
                [
                    ["Gas", "4,886", "Accuracy 0.866558  Macro F1 0.861027", "194.071", "3360.169"],
                    ["Bearing", "200", "MAE 230.506729  RMSE 354.669933", "139.098", "3024.992"],
                    ["Engine", "9,687", "MAE 41.087548  RMSE 56.187077  NASA 59,556,459,480.10695", "1358.918", "4056.783"],
                ],
                [2.0, 2.0, 7.5, 2.3, 2.3],
            ),
            PageBreak(),
            Paragraph("八 安全与回滚", styles["h1"]),
        ]
    )
    pdf_bullets(
        story,
        styles,
        [
            "模型调用文本不能直接执行任意Shell或Python，只能选择注册的训练Recipe。",
            "产物不可加载、指标非有限、任务schema错误、父链错误或模型过大时拒绝候选。",
            "Qwen可要求retain或rollback；失败时选中父checkpoint，避免破坏稳定模型。",
            "每轮保存宿主model_call_id和模型血缘，支持定位训练、选择和回滚过程。",
            "API Key只由平台注入，不进入源码、镜像、日志或公开记录。",
        ],
    )
    story.extend(
        [
            Paragraph("九 已知边界与诚实披露", styles["h1"]),
            Paragraph(
                "镜像14取得较好的Gas和Bearing隐藏结果，但Engine提升有限。逐轮报告还出现Gas第5轮、Bearing第2轮和Engine第4轮的数值关系与部署动作冲突。"
                "这说明大模型自然语言判断可能算错指标方向，而当时Harness主要校验结构化决定和硬安全约束。",
                styles["body"],
            ),
        ]
    )
    pdf_bullets(
        story,
        styles,
        [
            "不把其他版本新增的选择、漂移统计或验收能力写成镜像14功能。",
            "SwanLab链接是项目公开研发记录；镜像14精确运行事实以随包官方试运行报告为准。",
            "隐藏试运行不计正式成绩，也不能用于继续对隐藏集调参。",
            "平台没有提供峰值RSS和逐阶段等待耗时，因此不虚构这些数据。",
        ],
    )
    story.extend(
        [
            Paragraph("十 复现与材料索引", styles["h1"]),
            pdf_table(
                styles,
                ["材料", "入口"],
                [
                    ["Docker归档", str(IMAGE_TAR)],
                    ["源码", SOURCE_URL],
                    ["SwanLab研发记录", SWANLAB_URL],
                    ["本地验收", "docs/results/FORMAL-EVERY-ROUND-TRAIN-001.md"],
                    ["平台试运行原文", "随包05 镜像14官方试运行报告目录"],
                ],
                [4.3, 12.1],
            ),
        ]
    )
    footer = lambda canvas, current_doc: pdf_footer(canvas, current_doc, "BRACE MSI 镜像14 0.10.6rc1 项目说明书")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def copy_platform_reports(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    gas = Path(r"C:\Users\Administrator\.codex\attachments\a99d01f4-516f-42d2-929b-94ec8c6967e2\已粘贴的文本.txt")
    bearing_engine = Path(r"C:\Users\Administrator\.codex\attachments\2c87ffd9-2634-48dd-b513-bedf93bf8910\已粘贴的文本.txt")
    shutil.copy2(gas, target / "镜像14-官方试运行报告-Gas及总览.txt")
    shutil.copy2(bearing_engine, target / "镜像14-官方试运行报告-Bearing-Engine.txt")
    write_text(
        target / "报告摘要与边界.txt",
        """
运行类型：官方平台试运行，不计正式成绩
平台备注：镜像14v16
镜像绑定：用户于2026-11-24确认镜像14对应brace-msi:0.10.6rc1
完成情况：A/B/C各10轮，预测14,773条
Token：输入72,038；输出2,380；合计74,418
Gas：Accuracy 0.866558；Macro-F1 0.861027
Bearing：MAE 230.506729；RMSE 354.669933
Engine：MAE 41.087548；RMSE 56.187077；NASA 59,556,459,480.10695
边界：以上是历史试运行事实，不是正式成绩；不得用于继续对隐藏集调参。
""",
    )


def finalize_bundle() -> Path:
    files = sorted(
        path for path in OUT_ROOT.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt"
    )
    checksum_lines = []
    for path in files:
        relative = path.relative_to(OUT_ROOT).as_posix()
        checksum_lines.append(f"{sha256(path)}  {relative}")
    write_text(OUT_ROOT / "SHA256SUMS.txt", "\n".join(checksum_lines))

    zip_path = OUT_ROOT.parent / "BRACE-MSI-镜像14-0.10.6rc1-最终完整提交包-不含PPT.zip"
    if zip_path.exists():
        raise SystemExit(f"refusing to overwrite existing bundle: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(path for path in OUT_ROOT.rglob("*") if path.is_file()):
            if path.suffix.lower() in {".ppt", ".pptx"}:
                raise SystemExit(f"PPT unexpectedly present: {path}")
            archive.write(path, arcname=str(Path(OUT_ROOT.name) / path.relative_to(OUT_ROOT)))
    return zip_path


def main() -> None:
    if OUT_ROOT.exists():
        raise SystemExit(f"refusing to overwrite existing directory: {OUT_ROOT}")
    if not IMAGE_TAR.is_file() or not RELEASE_MANIFEST.is_file():
        raise SystemExit("image14 archive or release manifest is missing")
    actual = sha256(IMAGE_TAR)
    if actual != ARCHIVE_SHA256:
        raise SystemExit(f"archive hash mismatch: {actual}")

    OUT_ROOT.mkdir(parents=True)
    evidence_dir = OUT_ROOT / "05-镜像14官方试运行报告"
    audit_dir = OUT_ROOT / "06-版本清单与本地验收"
    audit_dir.mkdir()

    write_text(
        OUT_ROOT / "00-提交材料索引.txt",
        f"""
BRACE-MSI 镜像14 0.10.6rc1 提交材料 不含PPT

1. 01-模型配置.txt：平台模型和工业模型配置。
2. 02-云端实验记录与边界.txt：SwanLab研发记录及镜像14精确报告边界。
3. 03-Harness镜像14说明.txt：镜像14归档、标签、哈希和独立上传位置。
4. 04-源码仓库与版本.txt：与镜像14绑定的源码提交和源码ZIP。
5. BRACE-MSI-镜像14-系统运行说明.pdf：上传、运行、输入输出和异常处理。
6. BRACE-MSI-镜像14-项目说明书.pdf：架构、流程、安全、试运行结果和边界。
7. BRACE-MSI-镜像14-源代码-{SOURCE_COMMIT[:7]}.zip：镜像14对应源码。
8. 05-镜像14官方试运行报告：平台原文及摘要。
9. 06-版本清单与本地验收：release manifest和本地验收报告。
10. 开源依赖与合规清单.md：依赖、许可证和数据边界。
11. SHA256SUMS.txt：包内文件校验值。

Harness镜像tar不放入本材料ZIP。另一平台上传请单独选择：
{IMAGE_TAR}
SHA-256：{ARCHIVE_SHA256}

本包不含PPT、数据、checkpoint、模型权重、API Key、Sampler路径或隐藏测试标签。
""",
    )
    write_text(
        OUT_ROOT / "01-模型配置.txt",
        f"""
项目名称：BRACE-MSI
平台镜像：镜像14
Harness版本：0.10.6rc1
Docker标签：{IMAGE_TAG}
模型类型：基础模型
Agent基础模型：Qwen/Qwen3.8-27B
模型调用：官方SDK rnd.model 宿主网关
SDK协议：contest.harness.workspace.v2
SDK版本：1.0.2
工业模型：平台父checkpoint.npz开始的NumPy Adam CPU续训
工业模型产物：checkpoint.npz
任务类型：数值表格分类与回归
运行方式：每轮训练候选并由第二次Qwen调用决定deploy retain或rollback
API Key：只在平台受保护字段填写，不写入本文件或镜像
持久化Sampler路径：不填写，本版本使用平台基础模型
Docker归档SHA-256：{ARCHIVE_SHA256}
源码提交：{SOURCE_COMMIT}
""",
    )
    write_text(
        OUT_ROOT / "02-云端实验记录与边界.txt",
        f"""
SwanLab公开研发记录：{SWANLAB_URL}

边界说明：该SwanLab项目是BRACE-MSI三任务聚合研发记录，不声称由镜像14官方试运行容器直接同步。
镜像14的精确十轮训练、Token、资源和隐藏测试结果以本包“05-镜像14官方试运行报告”中的平台原文为准。
两类证据分开提供，不把其他版本的SwanLab运行或镜像结果混入镜像14。
""",
    )
    write_text(
        OUT_ROOT / "03-Harness镜像14说明.txt",
        f"""
平台镜像：镜像14
确认版本：0.10.6rc1
Docker标签：{IMAGE_TAG}
镜像ID：{IMAGE_ID}
归档文件：{IMAGE_TAR}
归档大小：81,208,320字节，约77.45 MiB
归档SHA-256：{ARCHIVE_SHA256}
平台上传显示：77.4 MiB，镜像可用

另一平台上传时请直接上传上述harness.tar。它是docker save归档。
不要上传源码ZIP、材料ZIP、项目目录、Dockerfile或docker export产物，也不要把其他文件改名为tar。
本材料ZIP不重复包含harness.tar，避免把镜像上传入口与作品文档入口混淆。
""",
    )
    write_text(
        OUT_ROOT / "04-源码仓库与版本.txt",
        f"""
源码仓库：https://github.com/nanmo-max/rengongzhineng
镜像14固定提交：{SOURCE_COMMIT}
固定提交链接：{SOURCE_URL}
本包源码归档：BRACE-MSI-镜像14-源代码-{SOURCE_COMMIT[:7]}.zip

镜像14的19个正式运行文件已在历史本地审计中与该提交逐文件哈希匹配。
请勿用当前分支最新源码替代镜像14源码，也不要把其他版本新增功能写成镜像14能力。
""",
    )
    write_text(
        OUT_ROOT / "开源依赖与合规清单.md",
        """
# BRACE-MSI 镜像14开源依赖与合规清单

## 正式运行依赖

- Python 3.11运行环境。
- NumPy，用于工业MLP续训、指标计算和checkpoint处理。
- 官方contest_harness SDK 1.0.2，按比赛提供接口随源码固定。

依赖版本以随包`requirements.formal.lock`和源码提交为准。正式镜像不包含PyTorch、工业数据、父checkpoint、Qwen权重、Tokenizer、Sampler、SwanLab客户端或PyTRiO私有客户端。

## 模型与数据

- Agent模型由平台选择并托管，本提交配置为`Qwen/Qwen3.8-27B`基础模型。
- 工业模型必须从平台提供的父`checkpoint.npz`继续训练。
- 正式镜像不包含A/B/C公开数据或隐藏数据。
- 隐藏标签不可见，不用于训练或参数选择。

## 凭据与隐私

- PyTRiO API Key只填写在平台受保护字段。
- 源码、镜像、材料和公开记录均不得包含API Key、Sampler完整路径、逐样本标签、可逆特征或工业模型权重。

## 项目源码许可边界

依赖许可证与项目源码许可证分开处理。本材料不擅自声明项目采用MIT或Apache等未由权利人确认的许可证；提交时按赛事来源声明填写实际权利和第三方依赖信息。
""",
    )

    build_run_guide_pdf(OUT_ROOT / "BRACE-MSI-镜像14-系统运行说明.pdf")
    build_project_description_pdf(OUT_ROOT / "BRACE-MSI-镜像14-项目说明书.pdf")
    build_source_zip(OUT_ROOT / f"BRACE-MSI-镜像14-源代码-{SOURCE_COMMIT[:7]}.zip")
    copy_platform_reports(evidence_dir)
    shutil.copy2(RELEASE_MANIFEST, audit_dir / "release-manifest.json")
    shutil.copy2(ROOT / "docs" / "results" / "FORMAL-EVERY-ROUND-TRAIN-001.md", audit_dir / "FORMAL-EVERY-ROUND-TRAIN-001.md")

    metadata = {
        "format": "brace-msi.image14.submission-bundle.v1",
        "platform_image": "镜像14",
        "version": "0.10.6rc1",
        "docker_tag": IMAGE_TAG,
        "docker_archive": str(IMAGE_TAR),
        "docker_archive_bytes": IMAGE_TAR.stat().st_size,
        "docker_archive_sha256": ARCHIVE_SHA256,
        "image_id": IMAGE_ID,
        "source_commit": SOURCE_COMMIT,
        "source_url": SOURCE_URL,
        "agent_model": "Qwen/Qwen3.8-27B",
        "ppt_included": False,
        "docker_archive_in_bundle": False,
        "official_trial": {
            "rounds_per_task": 10,
            "predictions": 14773,
            "input_tokens": 72038,
            "output_tokens": 2380,
            "total_tokens": 74418,
        },
    }
    (audit_dir / "image14-binding.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finalize_bundle()


if __name__ == "__main__":
    main()
