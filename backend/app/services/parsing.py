from pathlib import Path

import pymupdf


class ParsingError(Exception):
    pass


def extract_txt(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParsingError("无法识别 TXT 编码，请使用 UTF-8 或 GBK")


def extract_pdf_pages(path: Path) -> list[tuple[int, str]]:
    try:
        pdf = pymupdf.open(path)
    except Exception as error:
        raise ParsingError(f"无法打开 PDF：{error}") from error

    try:
        pages = []
        for index, page in enumerate(pdf):
            text = page.get_text("text").strip()
            if text:
                pages.append((index + 1, text))
        return pages
    finally:
        pdf.close()
