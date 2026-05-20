#!/usr/bin/env python3
"""从 .docx 论文模板中提取格式规范，输出 JSON。

用法:
    python extract_format.py 模板.docx              # 输出 JSON 到终端
    python extract_format.py 模板.docx -o spec.json  # 输出到文件
    python extract_format.py 模板.docx --markdown     # 输出 Markdown 表格

依赖: pip install python-docx
"""

import json
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, Cm, Inches, Emu
    from docx.enum.text import WD_ALIGN_PARAGRAPH
except ImportError:
    print("请先安装 python-docx: pip install python-docx")
    sys.exit(1)

# 中文字号换算
CN_FONT_SIZE = {
    "初号": 42, "小初": 36, "一号": 26, "小一": 24,
    "二号": 22, "小二": 18, "三号": 16, "小三": 15,
    "四号": 14, "小四": 12, "五号": 10.5, "小五": 9,
    "六号": 7.5, "小六": 6.5, "七号": 5.5, "八号": 5,
}

ALIGN_MAP = {
    WD_ALIGN_PARAGRAPH.CENTER: "居中",
    WD_ALIGN_PARAGRAPH.LEFT: "左对齐",
    WD_ALIGN_PARAGRAPH.RIGHT: "右对齐",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "两端对齐",
}


def pt_to_cn(pt_value):
    """将磅值转换为中文习惯字号"""
    if not pt_value:
        return "未知"
    pt = round(float(pt_value), 1)
    closest = min(CN_FONT_SIZE.items(), key=lambda x: abs(x[1] - pt))
    diff = abs(closest[1] - pt)
    if diff <= 0.5:
        return f"{closest[0]}（{pt}pt）"
    return f"{pt}pt"


def extract_line_spacing(paragraph_format):
    """提取行距信息"""
    spacing = paragraph_format.line_spacing
    if spacing is None:
        return "未设置"
    if isinstance(spacing, float):
        return f"{spacing}倍行距"
    try:
        return f"{spacing / 12700:.0f}磅固定值"
    except Exception:
        return f"{spacing}"


def extract_section_format(doc):
    """提取页面设置（所有节取第一节）"""
    sections = doc.sections
    specs = {}

    if not sections:
        return specs

    sec = sections[0]

    # 纸张大小
    specs["纸张大小"] = f"{sec.page_width.cm:.1f}cm × {sec.page_height.cm:.1f}cm" if sec.page_width else "A4"

    # 页边距
    specs["页边距_上"] = f"{sec.top_margin.cm:.1f}cm" if sec.top_margin else "未知"
    specs["页边距_下"] = f"{sec.bottom_margin.cm:.1f}cm" if sec.bottom_margin else "未知"
    specs["页边距_左"] = f"{sec.left_margin.cm:.1f}cm" if sec.left_margin else "未知"
    specs["页边距_右"] = f"{sec.right_margin.cm:.1f}cm" if sec.right_margin else "未知"

    # 页眉页脚
    specs["页眉距离"] = f"{sec.header_distance.cm:.1f}cm" if sec.header_distance else "未知"
    specs["页脚距离"] = f"{sec.footer_distance.cm:.1f}cm" if sec.footer_distance else "未知"

    return specs


def extract_style_info(doc):
    """提取核心样式信息"""
    styles_info = {}

    target_styles = ["Normal", "Title", "Heading 1", "Heading 2", "Heading 3",
                     "正文", "标题", "标题 1", "标题 2", "标题 3", "摘要", "目录"]

    # 也检查中文样式名称映射
    style_map = {}
    for s in doc.styles:
        if s.name and s.type is not None:
            style_map[s.name] = s

    # 尝试匹配
    for name in target_styles:
        s = style_map.get(name)
        if s and s.font:
            info = {
                "中文字体": s.font.name or "未设置",
                "西文字体": s.font.name or "未设置",
                "字号": pt_to_cn(s.font.size.pt) if s.font.size else "未设置",
                "加粗": str(s.font.bold) if s.font.bold is not None else "未设置",
            }
            if hasattr(s, "paragraph_format"):
                info["行间距"] = extract_line_spacing(s.paragraph_format)
                if s.paragraph_format.alignment is not None:
                    info["对齐方式"] = ALIGN_MAP.get(s.paragraph_format.alignment, "未知")
                if s.paragraph_format.first_line_indent:
                    indent_cm = s.paragraph_format.first_line_indent.cm
                    info["首行缩进"] = f"{indent_cm:.1f}cm（约{indent_cm/0.74:.0f}字符）"
                info["段前间距"] = f"{s.paragraph_format.space_before.pt:.0f}pt" if s.paragraph_format.space_before else "0pt"
                info["段后间距"] = f"{s.paragraph_format.space_after.pt:.0f}pt" if s.paragraph_format.space_after else "0pt"
            styles_info[name] = info

    return styles_info


def extract_all_body_paragraphs(doc):
    """收集正文段落样式以统计实际使用的格式"""
    body_styles = {}
    style_count = {}

    for para in doc.paragraphs:
        style_name = para.style.name if para.style else "无样式"
        style_count[style_name] = style_count.get(style_name, 0) + 1

        if style_name not in body_styles and para.runs:
            run = para.runs[0]
            body_styles[style_name] = {
                "字体": run.font.name or "继承样式",
                "字号": pt_to_cn(run.font.size.pt) if run.font.size else "继承样式",
                "加粗": str(run.font.bold) if run.font.bold is not None else "继承样式",
                "行间距": extract_line_spacing(para.paragraph_format),
                "首行缩进": (
                    f"{para.paragraph_format.first_line_indent.cm:.1f}cm"
                    if para.paragraph_format and para.paragraph_format.first_line_indent
                    else "未设置"
                ),
            }

    return body_styles, style_count


def summarize_specs(section_specs, style_info, body_styles, style_count):
    """整理成最终格式规范表"""
    result = {}

    # 页面设置
    result["页面设置"] = section_specs

    # 正文样式（从 Normal 样式 + 高频使用样式推断）
    normal = style_info.get("Normal", style_info.get("正文", {}))
    result["正文样式"] = {
        "中文字体": normal.get("中文字体", "未识别"),
        "西文字体": normal.get("西文字体", "未识别"),
        "字号": normal.get("字号", "未识别"),
        "行间距": normal.get("行间距", "未识别"),
        "首行缩进": normal.get("首行缩进", "未识别"),
    }

    # 标题样式
    result["标题样式"] = {}
    for level_name, h_style in [("一级标题", "Heading 1"), ("二级标题", "Heading 2"), ("三级标题", "Heading 3")]:
        info = style_info.get(h_style)
        if info and info.get("字号") not in ("未设置", None):
            result["标题样式"][level_name] = info

    # 样式使用统计
    result["样式使用统计"] = dict(sorted(style_count.items(), key=lambda x: x[1], reverse=True)[:10])

    return result


def format_markdown(specs):
    """输出 Markdown 格式"""
    output = []
    output.append("## 页面设置\n")
    for k, v in specs.get("页面设置", {}).items():
        output.append(f"| {k} | {v} |")
    output.append("")

    output.append("## 正文样式\n")
    for k, v in specs.get("正文样式", {}).items():
        output.append(f"| {k} | {v} |")
    output.append("")

    output.append("## 标题样式\n")
    for level, info in specs.get("标题样式", {}).items():
        output.append(f"### {level}\n")
        for k, v in info.items():
            output.append(f"| {k} | {v} |")
        output.append("")

    return "\n".join(output)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="从 .docx 论文模板提取格式规范")
    parser.add_argument("input", help="输入的 .docx 模板文件路径")
    parser.add_argument("-o", "--output", help="输出 JSON 文件路径")
    parser.add_argument("--markdown", action="store_true", help="以 Markdown 表格格式输出")
    args = parser.parse_args()

    doc_path = Path(args.input)
    if not doc_path.exists():
        print(f"文件不存在: {args.input}")
        sys.exit(1)

    print(f"正在解析: {doc_path.name} ...")
    doc = Document(str(doc_path))

    # 提取
    section_specs = extract_section_format(doc)
    style_info = extract_style_info(doc)
    body_styles, style_count = extract_all_body_paragraphs(doc)

    # 汇总
    specs = summarize_specs(section_specs, style_info, body_styles, style_count)

    if args.markdown:
        print(format_markdown(specs))
    else:
        json_str = json.dumps(specs, ensure_ascii=False, indent=2)
        print(json_str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            if args.markdown:
                f.write(format_markdown(specs))
            else:
                json.dump(specs, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {args.output}")


if __name__ == "__main__":
    main()
