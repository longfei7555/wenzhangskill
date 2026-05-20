#!/usr/bin/env python3
"""GB/T 7714-2015 参考文献格式化工具。

用法:
    # 交互模式：逐项输入文献信息
    python gb7714_formatter.py

    # JSON 输入模式
    python gb7714_formatter.py --from-json refs.json

    # 输出示例
    python gb7714_formatter.py --example

JSON 输入格式:
[
  {
    "type": "journal",
    "authors": ["HE K", "ZHANG X", "REN S", "SUN J"],
    "title": "Deep residual learning for image recognition",
    "journal": "Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition",
    "year": "2016",
    "volume": "",
    "issue": "",
    "pages": "770-778",
    "doi": ""
  },
  {
    "type": "book",
    "authors": ["周志华"],
    "title": "机器学习",
    "publisher": "清华大学出版社",
    "city": "北京",
    "year": "2016"
  }
]
"""

import json
import sys
import re
from typing import Optional


SUPPORTED_TYPES = {
    "journal":    "J",       # 期刊论文 [J]
    "book":       "M",       # 专著 [M]
    "thesis":     "D",       # 学位论文 [D]
    "conference": "C",       # 会议论文 [C]
    "patent":     "P",       # 专利 [P]
    "standard":   "S",       # 标准 [S]
    "online":     "EB/OL",   # 电子文献 [EB/OL]
    "report":     "R",       # 报告 [R]
    "newspaper":  "N",       # 报纸 [N]
}


def format_authors_cn(authors: list[str]) -> str:
    """格式化中文作者列表（3人以上用',等'）"""
    if not authors:
        return "[佚名]"
    if len(authors) == 1:
        return authors[0]
    if len(authors) <= 3:
        return ", ".join(authors)
    return f"{authors[0]}, {authors[1]}, {authors[2]}, 等"


def format_authors_en(authors: list[str]) -> str:
    """格式化英文作者列表（3人以上用'et al'）"""
    if not authors:
        return "[Anon]"
    if len(authors) == 1:
        return authors[0]
    if len(authors) <= 3:
        return ", ".join(authors)
    return f"{authors[0]}, {authors[1]}, {authors[2]}, et al"


def is_chinese(text: str) -> bool:
    """判断文本是否为中文"""
    return bool(re.search(r'[一-鿿]', text))


def detect_language(authors: list[str], title: str) -> str:
    """检测文献语言（cn/en），用于决定作者列表格式"""
    all_text = " ".join(authors) + " " + title
    if is_chinese(all_text):
        return "cn"
    return "en"


def format_authors(authors: list[str], lang: str) -> str:
    """根据语言选择作者列表格式"""
    if lang == "cn":
        return format_authors_cn(authors)
    return format_authors_en(authors)


def capitalize_title_en(title: str) -> str:
    """英文标题首字母大写（保留专有名词）"""
    # 简单规则：首字母大写，保留缩写
    if not title:
        return title
    # 不处理包含已知缩写的标题
    return title[0].upper() + title[1:] if title else title


# ---- 各类型的格式化函数 ----


def format_journal(ref: dict) -> str:
    """[J] 期刊论文"""
    lang = detect_language(ref.get("authors", []), ref.get("title", ""))
    authors = format_authors(ref.get("authors", []), lang)
    title = ref.get("title", "")
    journal = ref.get("journal", "")
    year = ref.get("year", "")
    volume = ref.get("volume", "")
    issue = ref.get("issue", "")

    vol_issue = ""
    if volume:
        vol_issue = volume
        if issue:
            vol_issue += f"({issue})"

    pages = ref.get("pages", "")
    page_part = f": {pages}" if pages else ""

    doi = ref.get("doi", "")

    if lang == "cn":
        ref_str = f"{authors}. {title}[J]. {journal}, {year}, {vol_issue}{page_part}."
    else:
        ref_str = f"{authors}. {title}[J]. {journal}, {year}, {vol_issue}{page_part}."

    if doi:
        ref_str += f" DOI: {doi}"

    return ref_str


def format_book(ref: dict) -> str:
    """[M] 专著"""
    lang = detect_language(ref.get("authors", []), ref.get("title", ""))
    authors = format_authors(ref.get("authors", []), lang)
    title = ref.get("title", "")
    city = ref.get("city", "")
    publisher = ref.get("publisher", "")
    year = ref.get("year", "")

    edition = ref.get("edition", "")
    ed_str = f". {edition}版" if edition else ""

    if lang == "cn":
        return f"{authors}. {title}[M]{ed_str}. {city}: {publisher}, {year}."
    else:
        return f"{authors}. {title}[M]{ed_str}. {city}: {publisher}, {year}."


def format_thesis(ref: dict) -> str:
    """[D] 学位论文"""
    lang = detect_language(ref.get("authors", []), ref.get("title", ""))
    authors = format_authors(ref.get("authors", []), lang)
    title = ref.get("title", "")
    city = ref.get("city", "")
    school = ref.get("school", "")
    year = ref.get("year", "")

    if lang == "cn":
        return f"{authors}. {title}[D]. {city}: {school}, {year}."
    else:
        return f"{authors}. {title}[D]. {city}: {school}, {year}."


def format_conference(ref: dict) -> str:
    """[C] 会议论文"""
    lang = detect_language(ref.get("authors", []), ref.get("title", ""))
    authors = format_authors(ref.get("authors", []), lang)
    title = ref.get("title", "")
    proceedings = ref.get("proceedings", "")
    city = ref.get("city", "")
    publisher = ref.get("publisher", "")
    year = ref.get("year", "")
    pages = ref.get("pages", "")
    page_part = f": {pages}" if pages else ""

    if lang == "cn":
        return f"{authors}. {title}[C]// {proceedings}. {city}: {publisher}, {year}{page_part}."
    else:
        return f"{authors}. {title}[C]// {proceedings}. {city}: {publisher}, {year}{page_part}."


def format_patent(ref: dict) -> str:
    """[P] 专利"""
    lang = detect_language(ref.get("authors", []), ref.get("title", ""))
    owner = format_authors(ref.get("authors", []), lang)
    title = ref.get("title", "")
    patent_no = ref.get("patent_no", "")
    date = ref.get("date", "")

    if lang == "cn":
        return f"{owner}. {title}: {patent_no}[P]. {date}."
    else:
        return f"{owner}. {title}: {patent_no}[P]. {date}."


def format_standard(ref: dict) -> str:
    """[S] 标准"""
    org = ref.get("org", "")
    std_no = ref.get("std_no", "")
    title = ref.get("title", "")
    city = ref.get("city", "")
    publisher = ref.get("publisher", "")
    year = ref.get("year", "")

    return f"{org}. {std_no} {title}[S]. {city}: {publisher}, {year}."


def format_online(ref: dict) -> str:
    """[EB/OL] 电子文献"""
    lang = detect_language(ref.get("authors", []), ref.get("title", ""))
    authors = format_authors(ref.get("authors", []), lang) if ref.get("authors") else ""
    title = ref.get("title", "")
    pub_date = ref.get("pub_date", "")
    cited_date = ref.get("cited_date", "")
    url = ref.get("url", "")

    ref_str = f"{authors}. " if authors else ""
    ref_str += f"{title}[EB/OL]."
    if pub_date:
        ref_str += f" ({pub_date})"
    ref_str += f" [{cited_date}]" if cited_date else ""
    ref_str += f". {url}" if url else ""
    ref_str += "."

    return ref_str


FORMATTERS = {
    "J":  format_journal,
    "M":  format_book,
    "D":  format_thesis,
    "C":  format_conference,
    "P":  format_patent,
    "S":  format_standard,
    "EB/OL": format_online,
    "R":  lambda r: f"{format_authors(r.get('authors',[]), 'cn')}. {r.get('title','')}[R]. {r.get('city','')}: {r.get('publisher','')}, {r.get('year','')}.",
    "N":  lambda r: f"{format_authors(r.get('authors',[]), 'cn')}. {r.get('title','')}[N]. {r.get('newspaper','')}, {r.get('date','')}({r.get('edition','')}).",
}


def format_one(ref: dict, index: Optional[int] = None) -> str:
    """格式化单条参考文献"""
    ref_type = ref.get("type", "journal")
    type_id = SUPPORTED_TYPES.get(ref_type, "J")

    formatter = FORMATTERS.get(type_id)
    if not formatter:
        return f"[警告] 不支持的文献类型: {ref_type}"

    try:
        ref_str = formatter(ref)
    except Exception as e:
        return f"[格式化错误] {e}"

    if index is not None:
        ref_str = f"[{index}] {ref_str}"

    return ref_str


def interactive_mode():
    """交互式添加文献"""
    print("=" * 50)
    print("GB/T 7714-2015 参考文献格式化工具")
    print("=" * 50)
    print()
    print("支持类型:")
    for key, val in SUPPORTED_TYPES.items():
        print(f"  {key:12s}  [{val}]")
    print()

    refs = []
    i = 1
    while True:
        print(f"\n--- 第 {i} 条参考文献 ---")
        rtype = input(f"类型 (journal/book/thesis/conference/patent/standard/online) [回车结束]: ").strip()
        if not rtype:
            break
        if rtype not in SUPPORTED_TYPES:
            print(f"  错误: 不支持的类型 '{rtype}'")
            continue

        ref = {"type": rtype}

        authors_str = input("  作者 (逗号分隔): ").strip()
        ref["authors"] = [a.strip() for a in authors_str.split(",")] if authors_str else []

        ref["title"] = input("  题名: ").strip()

        if rtype in ("journal",):
            ref["journal"] = input("  刊名: ").strip()
            ref["year"] = input("  年份: ").strip()
            ref["volume"] = input("  卷号 (可选): ").strip()
            ref["issue"] = input("  期号 (可选): ").strip()
            ref["pages"] = input("  页码 (可选): ").strip()
            ref["doi"] = input("  DOI (可选): ").strip()

        elif rtype in ("book",):
            ref["city"] = input("  出版地: ").strip()
            ref["publisher"] = input("  出版社: ").strip()
            ref["year"] = input("  年份: ").strip()
            ref["edition"] = input('  版次 (可选，如"第2版"填2): ').strip()

        elif rtype in ("thesis",):
            ref["city"] = input("  保存地: ").strip()
            ref["school"] = input("  保存单位（学校）: ").strip()
            ref["year"] = input("  年份: ").strip()

        elif rtype in ("conference",):
            ref["proceedings"] = input("  会议录名称: ").strip()
            ref["city"] = input("  出版地: ").strip()
            ref["publisher"] = input("  出版社: ").strip()
            ref["year"] = input("  年份: ").strip()
            ref["pages"] = input("  页码 (可选): ").strip()

        elif rtype in ("patent",):
            ref["patent_no"] = input("  专利号: ").strip()
            ref["date"] = input("  公告日期: ").strip()

        elif rtype in ("standard",):
            ref["org"] = input("  标准制定机构: ").strip()
            ref["std_no"] = input("  标准编号: ").strip()
            ref["city"] = input("  出版地: ").strip()
            ref["publisher"] = input("  出版社: ").strip()
            ref["year"] = input("  年份: ").strip()

        elif rtype in ("online",):
            ref["pub_date"] = input("  发布日期: ").strip()
            ref["cited_date"] = input("  引用日期: ").strip()
            ref["url"] = input("  获取路径: ").strip()

        refs.append(ref)
        print(f"  ✓ 已添加: {format_one(ref)[:80]}...")
        i += 1

    if not refs:
        print("未添加任何文献。")
        return

    print("\n" + "=" * 50)
    print(f"共 {len(refs)} 条参考文献:")
    print("=" * 50)
    for idx, ref in enumerate(refs, 1):
        print(format_one(ref, index=idx))

    save = input("\n保存为 JSON? (输入路径或回车跳过): ").strip()
    if save:
        with open(save, "w", encoding="utf-8") as f:
            json.dump(refs, f, ensure_ascii=False, indent=2)
        print(f"已保存到: {save}")


def show_example():
    """打印所有类型的示例"""
    examples = [
        {
            "type": "journal",
            "authors": ["HE K", "ZHANG X", "REN S", "SUN J"],
            "title": "Deep residual learning for image recognition",
            "journal": "Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition",
            "year": "2016",
            "pages": "770-778",
            "doi": "10.1109/CVPR.2016.90"
        },
        {
            "type": "book",
            "authors": ["周志华"],
            "title": "机器学习",
            "city": "北京",
            "publisher": "清华大学出版社",
            "year": "2016"
        },
        {
            "type": "journal",
            "authors": ["张明", "李华", "王强"],
            "title": "基于深度学习的文本分类方法综述",
            "journal": "计算机学报",
            "year": "2021",
            "volume": "44",
            "issue": "6",
            "pages": "1125-1149"
        },
        {
            "type": "thesis",
            "authors": ["王五"],
            "title": "基于注意力机制的图像分割方法研究",
            "city": "北京",
            "school": "清华大学",
            "year": "2023"
        },
        {
            "type": "conference",
            "authors": ["VASWANI A", "SHAZEER N", "PARMAR N", "et al"],
            "title": "Attention is all you need",
            "proceedings": "Advances in Neural Information Processing Systems",
            "city": "Long Beach",
            "publisher": "NIPS",
            "year": "2017",
            "pages": "5998-6008"
        },
        {
            "type": "online",
            "authors": [],
            "title": "PyTorch Documentation",
            "pub_date": "2024-01-15",
            "cited_date": "2025-03-20",
            "url": "https://pytorch.org/docs/stable/index.html"
        },
    ]

    print("=" * 50)
    print("GB/T 7714-2015 参考文献格式示例")
    print("=" * 50)
    for idx, ref in enumerate(examples, 1):
        print(f"\n[{idx}] {format_one(ref, index=idx)}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="GB/T 7714-2015 参考文献格式化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python gb7714_formatter.py              # 交互模式
  python gb7714_formatter.py --example    # 查看格式示例
  python gb7714_formatter.py --from-json refs.json  # 批量格式化
        """
    )
    parser.add_argument("--from-json", help="从 JSON 文件批量格式化参考文献")
    parser.add_argument("--example", action="store_true", help="显示各类文献的格式化示例")
    parser.add_argument("-o", "--output", help="输出结果到文件")
    args = parser.parse_args()

    if args.example:
        show_example()
        return

    if args.from_json:
        with open(args.from_json, "r", encoding="utf-8") as f:
            refs = json.load(f)

        output_lines = []
        for idx, ref in enumerate(refs, 1):
            output_lines.append(format_one(ref, index=idx))

        result = "\n".join(output_lines)
        print(result)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"\n已保存到: {args.output}")
        return

    interactive_mode()


if __name__ == "__main__":
    main()
