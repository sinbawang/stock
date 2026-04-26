from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

from send_wechat_native import send_message


def render_svg(svg_path: Path, output_png: Path) -> Path:
    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        raise RuntimeError(f"无法解析 SVG: {svg_path}")
    output_png.parent.mkdir(parents=True, exist_ok=True)
    renderPM.drawToFile(drawing, str(output_png), fmt="PNG")
    return output_png


def make_sendable_jpg(
    input_png: Path,
    output_jpg: Path,
    max_width: int = 1280,
    max_height: int = 800,
    quality: int = 92,
) -> Path:
    image = Image.open(input_png).convert("RGB")
    image.thumbnail((max_width, max_height))
    output_jpg.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_jpg, format="JPEG", quality=quality, optimize=True)
    return output_jpg


def derive_output_paths(svg_path: Path) -> tuple[Path, Path]:
    stem = svg_path.stem
    parent = svg_path.parent
    return parent / f"{stem}_full.png", parent / f"{stem}_wechat.jpg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an SVG chart into a complete PNG/JPG and optionally send it to WeChat.")
    parser.add_argument("svg", help="Input SVG chart path")
    parser.add_argument("--contact", default=None, help="WeChat contact to send to")
    parser.add_argument("--message", default=None, help="Optional text message to send after the image")
    parser.add_argument("--visible-row-index", type=int, default=None, help="1-based visible session row to click directly")
    parser.add_argument("--current-chat-only", action="store_true", help="Only send to the chat that is already open; do not switch chats")
    parser.add_argument("--result-index", type=int, default=1, help="1-based search result row when using contact search")
    parser.add_argument("--max-width", type=int, default=1280, help="Max width for the sendable JPG")
    parser.add_argument("--max-height", type=int, default=800, help="Max height for the sendable JPG")
    parser.add_argument("--quality", type=int, default=92, help="JPEG quality for the sendable image")
    parser.add_argument("--render-only", action="store_true", help="Only render PNG/JPG, do not send to WeChat")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    svg_path = Path(args.svg).resolve()
    if not svg_path.exists():
        raise FileNotFoundError(f"SVG 文件不存在: {svg_path}")

    output_png, output_jpg = derive_output_paths(svg_path)
    render_svg(svg_path, output_png)
    make_sendable_jpg(
        output_png,
        output_jpg,
        max_width=args.max_width,
        max_height=args.max_height,
        quality=args.quality,
    )

    print(f"完整 PNG: {output_png}")
    print(f"微信 JPG: {output_jpg}")

    if args.render_only:
        return

    if not args.contact:
        raise ValueError("非 render-only 模式必须提供 --contact")
    if not args.current_chat_only and args.visible_row_index is None:
        raise ValueError("默认禁止自动切会话。请先手动打开目标聊天并使用 --current-chat-only，或明确提供 --visible-row-index。")

    if args.message:
        send_message(
            args.contact,
            message=args.message,
            result_index=args.result_index,
            visible_row_index=args.visible_row_index,
            filepaths=None,
            current_chat_only=args.current_chat_only,
        )
        print(f"已尝试发送文本到 {args.contact}")

    send_message(
        args.contact,
        message=None,
        result_index=args.result_index,
        visible_row_index=args.visible_row_index,
        filepaths=[str(output_jpg)],
        current_chat_only=args.current_chat_only,
    )
    print(f"已尝试发送图片到 {args.contact}")


if __name__ == "__main__":
    main()