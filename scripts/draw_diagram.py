#!/usr/bin/env python3
"""
论文配图生成工具 —— 从 JSON 配置生成出版级图表。

支持的图表类型:
  flowchart       算法流程图 / 系统流程图
  architecture    系统架构框图
  comparison      对比柱状图（带误差棒）
  training_curve  训练曲线（loss / accuracy）
  ablation        消融实验对比图
  table           学术三线表（渲染为图片）

用法:
  python draw_diagram.py flowchart   config.json -o output.png
  python draw_diagram.py comparison  config.json -o output.png --dpi 300
  python draw_diagram.py table       config.json -o output.png

依赖: pip install matplotlib numpy
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import numpy as np

# ---------------------------------------------------------------------------
# 中文字体配置（自动检测可用的中文字体）
# ---------------------------------------------------------------------------
def _find_cn_font() -> str:
    """自动寻找可用的中文字体"""
    from matplotlib.font_manager import FontManager
    fm = FontManager()
    candidates = [
        "SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei",
        "Noto Sans CJK SC", "Source Han Sans SC", "STHeiti",
        "Heiti SC", "PingFang SC", "AR PL UMing CN",
    ]
    available = {f.name for f in fm.ttflist}
    for c in candidates:
        if c in available:
            return c
    return "sans-serif"


CN_FONT = _find_cn_font()
plt.rcParams["font.family"]       = CN_FONT
plt.rcParams["font.sans-serif"]   = [CN_FONT, "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 论文用配色（色盲友好 + 黑白打印兼容）
COLORS = ["#2c3e50", "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]
GRAY   = "#7f8c8d"
LIGHT_GRAY = "#ecf0f1"

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _save_and_close(path: str, dpi: int = 300) -> None:
    """保存图片并关闭 figure"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(pad=1.0)
    plt.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close()
    print(f"[OK] Saved: {path}")


def load_config(path: str) -> dict:
    """加载 JSON 配置文件"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def mm_to_inch(mm: float) -> float:
    """毫米转英寸"""
    return mm / 25.4


# ===================================================================
# 1. 流程图
# ===================================================================
def draw_flowchart(config: dict, output_path: str, dpi: int = 300) -> None:
    """
    JSON 格式:
    {
      "title": "算法流程图",
      "title_fontsize": 14,
      "fontsize": 9,
      "direction": "TB",         // TB (上到下) 或 LR (左到右)
      "box_width": 2.4,
      "box_height": 0.9,
      "arrow_gap": 0.35,
      "row_gap": 0.8,
      "col_gap": 0.6,
      "nodes": [
        {"id": "input",    "label": "输入图像\n(256×256)", "style": "rounded"},
        {"id": "preproc",  "label": "预处理\n(归一化+增强)"},
        {"id": "backbone", "label": "特征提取\n(ResNet-50)"},
        {"id": "neck",     "label": "特征融合\n(FPN)",       "style": "dashed"},
        {"id": "head_cls", "label": "分类头\n(FC+Softmax)"},
        {"id": "head_reg", "label": "回归头\n(FC+Linear)",  "style": "dashed"},
        {"id": "loss",     "label": "联合损失\n(L_cls + λ·L_reg)"},
        {"id": "output",   "label": "检测结果\n(类别+边界框)", "style": "rounded", "bold": true}
      ],
      "edges": [
        {"from": "input",    "to": "preproc"},
        {"from": "preproc",  "to": "backbone"},
        {"from": "backbone", "to": "neck"},
        {"from": "neck",     "to": "head_cls"},
        {"from": "neck",     "to": "head_reg"},
        {"from": "head_cls", "to": "loss"},
        {"from": "head_reg", "to": "loss"},
        {"from": "loss",     "to": "output"}
      ]
    }
    """
    nodes = config["nodes"]
    edges = config["edges"]
    title = config.get("title", "")
    fontsize = config.get("fontsize", 9)

    # 构建网格位置 (简单拓扑排序布局)
    # 计算每个节点的层（拓扑层级）
    node_map = {n["id"]: n for n in nodes}
    in_degree = {n["id"]: 0 for n in nodes}
    adj = {n["id"]: [] for n in nodes}
    for e in edges:
        adj[e["from"]].append(e["to"])
        in_degree[e["to"]] += 1

    # BFS 分层
    levels: Dict[str, int] = {}
    queue = [nid for nid in in_degree if in_degree[nid] == 0]
    for nid in queue:
        levels[nid] = 0
    while queue:
        u = queue.pop(0)
        for v in adj[u]:
            in_degree[v] -= 1
            levels[v] = max(levels.get(v, 0), levels.get(u, 0) + 1)
            if in_degree[v] == 0:
                queue.append(v)

    # 按层分组
    layer_nodes: Dict[int, list] = {}
    for nid, lv in levels.items():
        layer_nodes.setdefault(lv, []).append(nid)

    max_layer = max(layer_nodes.keys())
    max_col = max(len(v) for v in layer_nodes.values())

    bw = config.get("box_width", 2.4)
    bh = config.get("box_height", 0.9)
    ag = config.get("arrow_gap", 0.35)
    rg = config.get("row_gap", 0.8)
    cg = config.get("col_gap", 0.6)

    # 计算画布大小
    nrows = max_layer + 1
    fig_w = max_col * (bw + cg) + cg
    fig_h = nrows * (bh + rg) + rg + 1.2
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    # 计算每个节点的坐标
    positions: Dict[str, Tuple[float, float]] = {}
    for lv, nids in layer_nodes.items():
        n_in_layer = len(nids)
        total_w = n_in_layer * bw + (n_in_layer - 1) * cg
        start_x = (fig_w - total_w) / 2
        y = fig_h - rg - bh - lv * (bh + rg) - 0.6
        for i, nid in enumerate(nids):
            x = start_x + i * (bw + cg)
            positions[nid] = (x, y)

    # 先画边
    for e in edges:
        x1, y1 = positions[e["from"]]
        x2, y2 = positions[e["to"]]
        ax.annotate(
            "", xy=(x2 + bw / 2, y2 + bh), xytext=(x1 + bw / 2, y1),
            arrowprops=dict(
                arrowstyle="->", color=GRAY, lw=1.5,
                connectionstyle="arc3,rad=0"
            ),
        )

    # 再画节点
    for n in nodes:
        x, y = positions[n["id"]]
        style = n.get("style", "normal")
        is_bold = n.get("bold", False)

        if style == "rounded":
            box = FancyBboxPatch(
                (x, y), bw, bh, boxstyle="round,pad=0.15",
                facecolor="white", edgecolor="#2c3e50", linewidth=2 if is_bold else 1.2,
            )
        elif style == "dashed":
            box = FancyBboxPatch(
                (x, y), bw, bh, boxstyle="round,pad=0.05",
                facecolor="#f8f9fa", edgecolor=GRAY, linewidth=1.0,
                linestyle="--",
            )
        else:
            box = FancyBboxPatch(
                (x, y), bw, bh, boxstyle="round,pad=0.05",
                facecolor="white", edgecolor="#2c3e50", linewidth=1.2,
            )
        ax.add_patch(box)
        ax.text(
            x + bw / 2, y + bh / 2, n["label"],
            ha="center", va="center", fontsize=fontsize + (1 if is_bold else 0),
            fontweight="bold" if is_bold else "normal",
        )

    # 标题
    if title:
        ax.text(fig_w / 2, fig_h - 0.3, title, ha="center", va="top",
                fontsize=config.get("title_fontsize", 14), fontweight="bold")

    _save_and_close(output_path, dpi)


# ===================================================================
# 2. 系统架构框图
# ===================================================================
def draw_architecture(config: dict, output_path: str, dpi: int = 300) -> None:
    """
    JSON 格式:
    {
      "title": "系统总体架构",
      "groups": [
        {
          "label": "输入层",
          "color": "#3498db22",
          "items": [
            {"label": "RGB图像", "w": 2.5, "h": 0.8},
            {"label": "深度图", "w": 2.5, "h": 0.8}
          ]
        },
        {
          "label": "特征提取",
          "items": [
            {"label": "ResNet-50\nBackbone", "w": 3.0, "h": 1.2, "bold": true}
          ]
        },
        {
          "label": "输出层",
          "items": [
            {"label": "分类结果", "w": 2.2, "h": 0.8},
            {"label": "分割掩码", "w": 2.2, "h": 0.8}
          ]
        }
      ],
      "arrows": [
        {"from_group": 0, "to_group": 1, "label": "拼接"},
        {"from_group": 1, "to_group": 2, "label": ""}
      ]
    }
    """
    groups = config["groups"]
    title = config.get("title", "")

    # 计算布局
    group_gap = config.get("group_gap", 1.5)
    item_gap = config.get("item_gap", 0.3)
    padding = config.get("padding", 1.0)
    title_h = 0.8 if title else 0

    # 先计算每个 group 的尺寸
    group_sizes = []
    for g in groups:
        items = g["items"]
        max_w = max(it.get("w", 2.5) for it in items)
        total_h = sum(it.get("h", 0.8) for it in items) + item_gap * (len(items) - 1)
        group_sizes.append((max_w, total_h))

    # 画布尺寸
    total_w = sum(w for w, _ in group_sizes) + group_gap * (len(groups) - 1) + padding * 2
    total_h = max(h for _, h in group_sizes) + padding * 2 + title_h + 1.0

    fig, ax = plt.subplots(figsize=(total_w, total_h))
    ax.set_xlim(0, total_w)
    ax.set_ylim(0, total_h)
    ax.axis("off")

    # 绘制每个 group
    group_centers = []
    x_cursor = padding
    for gi, g in enumerate(groups):
        gw, gh = group_sizes[gi]
        items = g["items"]
        max_item_w = max(it.get("w", 2.5) for it in items)

        # Group 背景框
        grp_color = g.get("color", "#f0f0f0")
        grp_rect = FancyBboxPatch(
            (x_cursor, padding + 0.5), gw, gh + 1.0,
            boxstyle="round,pad=0.1",
            facecolor=grp_color, edgecolor=GRAY, linewidth=1.0, alpha=0.6,
        )
        ax.add_patch(grp_rect)

        # Group 标签
        if g.get("label"):
            ax.text(x_cursor + gw / 2, padding + gh + 1.6, g["label"],
                    ha="center", va="center", fontsize=10, fontweight="bold", color=GRAY)

        # Items
        y_cursor = padding + 0.5 + (gh - sum(it.get("h", 0.8) for it in items) - item_gap * (len(items) - 1)) / 2
        for it in items:
            iw = it.get("w", 2.5)
            ih = it.get("h", 0.8)
            ix = x_cursor + (gw - iw) / 2
            weight = "bold" if it.get("bold") else "normal"
            box = FancyBboxPatch(
                (ix, y_cursor), iw, ih,
                boxstyle="round,pad=0.08",
                facecolor="white", edgecolor=COLORS[gi % len(COLORS)], linewidth=1.5,
            )
            ax.add_patch(box)
            ax.text(ix + iw / 2, y_cursor + ih / 2, it["label"],
                    ha="center", va="center", fontsize=9, fontweight=weight)
            y_cursor += ih + item_gap

        group_centers.append((x_cursor + gw / 2, padding + 0.5 + gh / 2))
        x_cursor += gw + group_gap

    # 箭头
    for arrow in config.get("arrows", []):
        fi = arrow["from_group"]
        ti = arrow["to_group"]
        x1, y1 = group_centers[fi]
        x2, y2 = group_centers[ti]
        # 箭头从 group 右边缘到下一个 group 左边缘
        gw1 = group_sizes[fi][0]
        mid_x = x1 + gw1 / 2 + group_gap / 2
        ax.annotate(
            "", xy=(x2 - group_sizes[ti][0] / 2, y2), xytext=(x1 + gw1 / 2, y1),
            arrowprops=dict(arrowstyle="->", color="#2c3e50", lw=2.0),
        )
        if arrow.get("label"):
            ax.text(mid_x, y1 + 0.2, arrow["label"], ha="center", va="bottom",
                    fontsize=8, color=GRAY)

    if title:
        ax.text(total_w / 2, total_h - 0.3, title, ha="center", va="top",
                fontsize=14, fontweight="bold")

    _save_and_close(output_path, dpi)


# ===================================================================
# 3. 对比柱状图（带误差棒）
# ===================================================================
def draw_comparison(config: dict, output_path: str, dpi: int = 300) -> None:
    """
    JSON 格式:
    {
      "title": "不同方法在CIFAR-10上的分类准确率对比",
      "xlabel": "",
      "ylabel": "准确率 (%)",
      "ylim": [80, 100],
      "width": 0.6,
      "methods": ["ResNet-18", "ResNet-50", "VGG-16", "DenseNet", "Ours"],
      "values": [91.2, 93.5, 89.8, 94.1, 96.3],
      "errors": [0.3, 0.4, 0.5, 0.3, 0.2],
      "highlight": [4],
      "value_labels": true
    }
    """
    methods = config["methods"]
    values  = config["values"]
    errors  = config.get("errors")
    title   = config.get("title", "")
    xlabel  = config.get("xlabel", "")
    ylabel  = config.get("ylabel", "")
    ylim    = config.get("ylim")
    width   = config.get("width", 0.6)
    highlight = config.get("highlight", [])
    show_labels = config.get("value_labels", True)
    figsize = config.get("figsize", [len(methods) * 1.2 + 2, 5])

    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(methods))

    colors_list = []
    for i in range(len(methods)):
        if i in highlight:
            colors_list.append("#e74c3c")
        else:
            colors_list.append(COLORS[i % len(COLORS)])

    bars = ax.bar(
        x, values, width, color=colors_list,
        edgecolor="white", linewidth=0.5,
        yerr=errors, capsize=4, error_kw={"linewidth": 1.2, "color": GRAY},
    )

    # 数值标签
    if show_labels:
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                    f"{val}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=10, rotation=config.get("rotation", 0))
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=12)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=12)
    if ylim:
        ax.set_ylim(ylim)
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=GRAY)
    ax.set_axisbelow(True)

    _save_and_close(output_path, dpi)


# ===================================================================
# 4. 训练曲线
# ===================================================================
def draw_training_curve(config: dict, output_path: str, dpi: int = 300) -> None:
    """
    JSON 格式:
    {
      "title": "训练曲线",
      "subplots": ["Loss", "Accuracy"],
      "curves": [
        {"label": "Train Loss",   "subplot": 0, "values": [...], "color": "#3498db"},
        {"label": "Val Loss",     "subplot": 0, "values": [...], "color": "#e74c3c", "dashed": true},
        {"label": "Train Acc",    "subplot": 1, "values": [...], "color": "#3498db"},
        {"label": "Val Acc",      "subplot": 1, "values": [...], "color": "#e74c3c", "dashed": true}
      ],
      "xlabel": "Epoch",
      "epochs": 100
    }
    """
    subplot_names = config.get("subplots", ["Loss", "Accuracy"])
    curves = config["curves"]
    epochs = config.get("epochs")
    title = config.get("title", "")
    figsize = config.get("figsize", [12, 5])

    n = len(subplot_names)
    fig, axes = plt.subplots(1, n, figsize=figsize)
    if n == 1:
        axes = [axes]

    x_vals = list(range(1, epochs + 1)) if epochs else list(range(1, len(curves[0]["values"]) + 1))

    for idx, ax in enumerate(axes):
        for c in curves:
            if c["subplot"] != idx:
                continue
            ls = "--" if c.get("dashed") else "-"
            vals = c["values"]
            ax.plot(x_vals[:len(vals)], vals, color=c.get("color", COLORS[0]),
                    linewidth=1.5, linestyle=ls, label=c["label"], alpha=0.9)

        ax.set_xlabel(config.get("xlabel", "Epoch"), fontsize=11)
        ax.set_ylabel(subplot_names[idx], fontsize=11)
        ax.legend(fontsize=9, framealpha=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, linestyle="--", alpha=0.3, color=GRAY)

    if title:
        fig.suptitle(title, fontsize=14, fontweight="bold", y=1.01)

    _save_and_close(output_path, dpi)


# ===================================================================
# 5. 消融实验图
# ===================================================================
def draw_ablation(config: dict, output_path: str, dpi: int = 300) -> None:
    """
    JSON 格式:
    {
      "title": "消融实验",
      "ylabel": "mAP (%)",
      "variants": [
        {"label": "Baseline\n(ResNet-50)",       "value": 78.3},
        {"label": "+ FPN",                        "value": 81.2},
        {"label": "+ Attention\nModule",          "value": 83.7},
        {"label": "+ Data\nAugmentation",         "value": 84.9},
        {"label": "Full Model\n(Ours)",           "value": 86.5, "highlight": true}
      ],
      "show_diff": true,
      "width": 0.55
    }
    """
    variants = config["variants"]
    labels = [v["label"] for v in variants]
    values = [v["value"] for v in variants]
    title  = config.get("title", "消融实验")
    ylabel = config.get("ylabel", "")
    width  = config.get("width", 0.55)
    show_diff = config.get("show_diff", True)
    figsize = config.get("figsize", [len(variants) * 1.3 + 2, 5.5])

    fig, ax = plt.subplots(figsize=figsize)
    x = np.arange(len(variants))

    colors_list = []
    for i, v in enumerate(variants):
        if v.get("highlight"):
            colors_list.append("#e74c3c")
        else:
            colors_list.append(COLORS[i % len(COLORS)])

    bars = ax.bar(x, values, width, color=colors_list, edgecolor="white", linewidth=0.8)

    # 差值标注
    if show_diff:
        for i in range(1, len(values)):
            diff = values[i] - values[i - 1]
            mid_y = (values[i] + values[i - 1]) / 2
            ax.annotate(
                f"+{diff:.1f}", xy=(i, values[i]), xytext=(i + 0.45, mid_y),
                fontsize=9, color="#27ae60", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#27ae60", lw=0.8),
                ha="left", va="center",
            )

    # 数值标签
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() - 2,
                f"{val}", ha="center", va="top", fontsize=11,
                fontweight="bold", color="white")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=12)
    if title:
        ax.set_title(title, fontsize=14, fontweight="bold", pad=15)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3, color=GRAY)
    ax.set_axisbelow(True)

    _save_and_close(output_path, dpi)


# ===================================================================
# 6. 学术三线表（渲染为图片，适合贴入论文）
# ===================================================================
def draw_table(config: dict, output_path: str, dpi: int = 300) -> None:
    """
    JSON 格式:
    {
      "caption": "表X 不同方法在CIFAR-10上的分类准确率对比",
      "headers": ["方法", "准确率(%)", "参数量(M)", "推理时间(ms)"],
      "rows": [
        ["ResNet-18",  "91.2", "11.7", "12.3"],
        ["ResNet-50",  "93.5", "25.6", "18.7"],
        ["VGG-16",     "89.8", "138.4", "15.2"],
        ["DenseNet-121", "94.1", "8.0", "22.1"],
        ["\\textbf{Ours}", "\\textbf{96.3}", "\\textbf{14.2}", "\\textbf{10.8}"]
      ],
      "col_widths": [3.0, 1.8, 1.8, 2.0],
      "header_color": "#f0f0f0"
    }
    """
    headers = config["headers"]
    rows = config["rows"]
    caption = config.get("caption", "")
    col_widths = config.get("col_widths")
    header_color = config.get("header_color", "#f0f0f0")

    ncols = len(headers)
    nrows = len(rows) + 1  # +1 for header

    if col_widths:
        total_w = sum(col_widths)
    else:
        col_widths = [2.5] * ncols
        total_w = 2.5 * ncols

    row_h = 0.5
    total_h = nrows * row_h + 1.2  # extra for caption

    fig, ax = plt.subplots(figsize=(total_w, total_h))
    ax.set_xlim(0, total_w)
    ax.set_ylim(0, total_h)
    ax.axis("off")

    # --- 三线表绘制 ---
    top_y = total_h - 0.6
    x_positions = [0]
    for w in col_widths[:-1]:
        x_positions.append(x_positions[-1] + w)

    # 顶线（粗）
    ax.plot([0, total_w], [top_y, top_y], color="black", linewidth=1.5)
    # 表头下线（粗）
    ax.plot([0, total_w], [top_y - row_h, top_y - row_h], color="black", linewidth=1.5)
    # 底线（粗）
    bottom_y = top_y - nrows * row_h
    ax.plot([0, total_w], [bottom_y, bottom_y], color="black", linewidth=1.5)

    # 表头背景
    header_rect = Rectangle((0, top_y - row_h), total_w, row_h,
                            facecolor=header_color, edgecolor="none", alpha=0.5)
    ax.add_patch(header_rect)

    # 表头文字
    for ci, h in enumerate(headers):
        cx = x_positions[ci] + col_widths[ci] / 2
        cy = top_y - row_h / 2
        ax.text(cx, cy, h, ha="center", va="center", fontsize=10, fontweight="bold")

    # 数据行
    for ri, row in enumerate(rows):
        cy = top_y - row_h - ri * row_h - row_h / 2
        for ci, cell in enumerate(row):
            cx = x_positions[ci] + col_widths[ci] / 2
            if cell.startswith("\\textbf{"):
                text = cell[9:-1]
                ax.text(cx, cy, text, ha="center", va="center", fontsize=10, fontweight="bold")
            else:
                ax.text(cx, cy, cell, ha="center", va="center", fontsize=10)

    # 标题
    if caption:
        ax.text(total_w / 2, total_h - 0.15, caption, ha="center", va="top",
                fontsize=11, fontweight="normal")

    _save_and_close(output_path, dpi)


# ===================================================================
# CLI
# ===================================================================

TYPE_MAP = {
    "flowchart":      draw_flowchart,
    "architecture":   draw_architecture,
    "comparison":     draw_comparison,
    "training_curve": draw_training_curve,
    "ablation":       draw_ablation,
    "table":          draw_table,
}


def generate_example_configs(out_dir: str = "."):
    """生成所有图表类型的示例 JSON 配置文件"""
    out = Path(out_dir)

    # flowchart
    fc = {
        "title": "图X 算法整体流程图",
        "nodes": [
            {"id": "in",  "label": "输入图像\n(256×256)", "style": "rounded"},
            {"id": "p1",  "label": "预处理\n(归一化+增强)"},
            {"id": "b1",  "label": "特征提取\n(ResNet-50 Backbone)"},
            {"id": "n1",  "label": "特征融合\n(FPN)", "style": "dashed"},
            {"id": "h1",  "label": "分类头\n(FC+Softmax)"},
            {"id": "h2",  "label": "回归头\n(FC+Linear)", "style": "dashed"},
            {"id": "l1",  "label": "联合损失\n(L_cls + λ·L_reg)"},
            {"id": "out", "label": "检测结果\n(类别+边界框)", "style": "rounded", "bold": True},
        ],
        "edges": [
            {"from": "in",  "to": "p1"},
            {"from": "p1",  "to": "b1"},
            {"from": "b1",  "to": "n1"},
            {"from": "n1",  "to": "h1"}, {"from": "n1", "to": "h2"},
            {"from": "h1",  "to": "l1"}, {"from": "h2", "to": "l1"},
            {"from": "l1",  "to": "out"},
        ],
    }
    with open(out / "example_flowchart.json", "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False, indent=2)

    # architecture
    arch = {
        "title": "图X 系统总体架构",
        "groups": [
            {"label": "输入层", "color": "#3498db18",
             "items": [{"label": "RGB图像\n(224×224)", "w": 2.5, "h": 1.0},
                       {"label": "深度图\n(224×224)", "w": 2.5, "h": 1.0}]},
            {"label": "特征提取", "color": "#2ecc7118",
             "items": [{"label": "ResNet-50\nBackbone", "w": 3.2, "h": 1.3, "bold": True}]},
            {"label": "任务头", "color": "#e74c3c18",
             "items": [{"label": "分类头\n(FC+Softmax)", "w": 2.5, "h": 1.0},
                       {"label": "分割头\n(U-Net Decoder)", "w": 2.5, "h": 1.0}]},
            {"label": "输出层", "color": "#f39c1218",
             "items": [{"label": "类别标签", "w": 2.2, "h": 0.8},
                       {"label": "分割掩码", "w": 2.2, "h": 0.8}]},
        ],
        "arrows": [
            {"from_group": 0, "to_group": 1, "label": ""},
            {"from_group": 1, "to_group": 2, "label": ""},
            {"from_group": 2, "to_group": 3, "label": ""},
        ],
    }
    with open(out / "example_architecture.json", "w", encoding="utf-8") as f:
        json.dump(arch, f, ensure_ascii=False, indent=2)

    # comparison
    comp = {
        "title": "图X 不同方法在CIFAR-10上的分类准确率对比",
        "ylabel": "准确率 (%)",
        "ylim": [85, 100],
        "methods": ["ResNet-18", "ResNet-50", "VGG-16", "DenseNet-121", "MobileNet-V3", "Ours"],
        "values": [91.2, 93.5, 89.8, 94.1, 90.3, 96.3],
        "errors": [0.3, 0.4, 0.5, 0.3, 0.6, 0.2],
        "highlight": [5],
        "value_labels": True,
    }
    with open(out / "example_comparison.json", "w", encoding="utf-8") as f:
        json.dump(comp, f, ensure_ascii=False, indent=2)

    # training_curve
    np.random.seed(42)
    epochs = 100
    train_loss = 2.5 * np.exp(-np.linspace(0, 2, epochs)) + 0.15 * np.random.randn(epochs) + 0.3
    val_loss   = 2.8 * np.exp(-np.linspace(0, 1.8, epochs)) + 0.2 * np.random.randn(epochs) + 0.5
    train_acc  = 95 * (1 - 0.7 * np.exp(-np.linspace(0, 1.5, epochs))) + np.random.randn(epochs) * 1.5
    val_acc    = 93 * (1 - 0.8 * np.exp(-np.linspace(0, 1.3, epochs))) + np.random.randn(epochs) * 2.0

    tc = {
        "title": "训练过程曲线",
        "subplots": ["Loss", "Accuracy (%)"],
        "epochs": epochs,
        "curves": [
            {"label": "Train Loss", "subplot": 0, "values": train_loss.tolist(), "color": "#3498db"},
            {"label": "Val Loss",   "subplot": 0, "values": val_loss.tolist(),   "color": "#e74c3c", "dashed": True},
            {"label": "Train Acc",  "subplot": 1, "values": train_acc.tolist(),  "color": "#3498db"},
            {"label": "Val Acc",    "subplot": 1, "values": val_acc.tolist(),    "color": "#e74c3c", "dashed": True},
        ],
    }
    with open(out / "example_training_curve.json", "w", encoding="utf-8") as f:
        json.dump(tc, f, ensure_ascii=False, indent=2)

    # ablation
    ab = {
        "title": "图X 消融实验——各模块对性能的贡献",
        "ylabel": "mAP (%)",
        "variants": [
            {"label": "Baseline\n(ResNet-50)",       "value": 78.3},
            {"label": "+ FPN\n(特征金字塔)",           "value": 81.2},
            {"label": "+ Attention\n(注意力模块)",      "value": 83.7},
            {"label": "+ Multi-scale\n(多尺度训练)",    "value": 84.9},
            {"label": "Full Model\n(Ours)",           "value": 86.5, "highlight": True},
        ],
        "show_diff": True,
    }
    with open(out / "example_ablation.json", "w", encoding="utf-8") as f:
        json.dump(ab, f, ensure_ascii=False, indent=2)

    # table
    tbl = {
        "caption": "表X 不同方法在测试集上的性能对比",
        "headers": ["方法", "准确率(%)", "参数量(M)", "推理时间(ms)", "FPS"],
        "rows": [
            ["ResNet-18",       "91.2", "11.7", "12.3", "81"],
            ["ResNet-50",       "93.5", "25.6", "18.7", "53"],
            ["VGG-16",          "89.8", "138.4", "15.2", "66"],
            ["DenseNet-121",    "94.1", "8.0", "22.1", "45"],
            ["MobileNet-V3",    "90.3", "5.4", "8.2", "122"],
            ["\\textbf{Ours}",  "\\textbf{96.3}", "\\textbf{14.2}", "\\textbf{10.8}", "\\textbf{93}"],
        ],
        "col_widths": [2.8, 1.6, 1.6, 1.8, 1.2],
    }
    with open(out / "example_table.json", "w", encoding="utf-8") as f:
        json.dump(tbl, f, ensure_ascii=False, indent=2)

    print(f"已生成 {6} 个示例配置文件到: {out.absolute()}")
    print(f"  example_flowchart.json")
    print(f"  example_architecture.json")
    print(f"  example_comparison.json")
    print(f"  example_training_curve.json")
    print(f"  example_ablation.json")
    print(f"  example_table.json")


def main():
    parser = argparse.ArgumentParser(
        description="论文配图生成工具 —— 从 JSON 配置生成出版级图表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持的图表类型:
  flowchart        算法流程图 / 系统流程图
  architecture     系统架构框图
  comparison       对比柱状图（带误差棒）
  training_curve   训练曲线（loss / accuracy）
  ablation         消融实验对比图
  table            学术三线表

生成示例配置:
  python draw_diagram.py --examples

使用方法:
  python draw_diagram.py flowchart example_flowchart.json -o output.png
  python draw_diagram.py comparison example_comparison.json -o fig.png --dpi 300
        """,
    )
    parser.add_argument("type", nargs="?", help="图表类型: flowchart/architecture/comparison/training_curve/ablation/table")
    parser.add_argument("config", nargs="?", help="JSON 配置文件路径")
    parser.add_argument("-o", "--output", default="output.png", help="输出图片路径 (默认: output.png)")
    parser.add_argument("--dpi", type=int, default=300, help="输出分辨率 (默认: 300)")
    parser.add_argument("--examples", action="store_true", help="生成所有类型的示例 JSON 配置文件")
    parser.add_argument("--examples-dir", default=".", help="示例配置文件输出目录 (默认: 当前目录)")
    args = parser.parse_args()

    if args.examples:
        generate_example_configs(args.examples_dir)
        return

    if not args.type or not args.config:
        parser.print_help()
        print("\n提示: 使用 --examples 生成示例配置文件")
        sys.exit(1)

    if args.type not in TYPE_MAP:
        print(f"错误: 不支持的图表类型 '{args.type}'")
        print(f"支持的类型: {', '.join(TYPE_MAP.keys())}")
        sys.exit(1)

    config = load_config(Path(args.config))
    TYPE_MAP[args.type](config, args.output, args.dpi)


if __name__ == "__main__":
    main()
