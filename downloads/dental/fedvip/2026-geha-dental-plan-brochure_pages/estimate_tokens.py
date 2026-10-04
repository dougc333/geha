#!/usr/bin/env python3
"""Count extracted-text tokens by page; PDF image tokens are excluded.

Examples:
  python estimate_tokens.py --extensions md
  python estimate_tokens.py --extensions md pdf html --model gpt-4o
  python estimate_tokens.py --extensions html --html-mode raw

Dependencies: tiktoken; pymupdf for PDFs. Tokenizer vocabulary may download on
first use. Document contents are never sent to an API. HTML defaults to visible
text (no scripts/styles); choose raw to count the actual HTML source instead.
"""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import sys


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif tag in ('p', 'div', 'br', 'tr', 'td', 'th', 'li', 'h1', 'h2', 'h3'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def text_pages(path, html_mode):
    if path.suffix.lower() == '.pdf':
        import pymupdf
        with pymupdf.open(path) as doc:
            return [(i + 1, page.get_text()) for i, page in enumerate(doc)]
    text = path.read_text(encoding='utf-8')
    if path.suffix.lower() == '.html' and html_mode == 'visible':
        parser = VisibleHTML()
        parser.feed(text)
        text = ' '.join(''.join(parser.parts).split())
    return [(1, text)]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('directory', nargs='?', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--extensions', '--ext', nargs='+', default=['md'],
                        help='md pdf html; leading dots and comma-separated values accepted')
    parser.add_argument('--model', default='gpt-4o', help='Tokenizer model name (default: gpt-4o)')
    parser.add_argument('--encoding', help='Explicit tiktoken encoding, overrides --model')
    parser.add_argument('--hf-model', help='Hugging Face text tokenizer, e.g. deepseek-ai/DeepSeek-OCR; overrides --model')
    parser.add_argument('--html-mode', choices=['visible', 'raw'], default='visible')
    args = parser.parse_args()
    extensions = {e.lower().lstrip('.') for value in args.extensions for e in value.split(',')}
    if not extensions or extensions - {'md', 'pdf', 'html'}:
        parser.error('Supported extensions: md, pdf, html')
    if not args.directory.is_dir():
        parser.error('Directory does not exist')
    try:
        if args.hf_model:
            if args.encoding:
                parser.error('--hf-model and --encoding cannot be combined')
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(args.hf_model, trust_remote_code=False)
            tokenizer_name = args.hf_model
            count_tokens = lambda text: len(tokenizer.encode(text, add_special_tokens=False))
        else:
            import tiktoken
            tokenizer = tiktoken.get_encoding(args.encoding) if args.encoding else tiktoken.encoding_for_model(args.model)
            tokenizer_name = tokenizer.name
            count_tokens = lambda text: len(tokenizer.encode(text, disallowed_special=()))
    except Exception as exc:
        parser.exit(2, f'Tokenizer unavailable ({type(exc).__name__}). Install tiktoken or transformers as appropriate and allow the initial tokenizer download.\n')
    files = sorted(p for p in args.directory.iterdir() if p.is_file() and p.suffix.lower().lstrip('.') in extensions)
    if not files:
        parser.exit(2, 'No matching files found.\n')
    print(f'Text-only tokens | tokenizer={tokenizer_name} | HTML={args.html_mode}')
    print(f'{"File":<32} {"PDF page":>8} {"Tokens":>10} {"Characters":>12}')
    totals = {}
    errors = 0
    for path in files:
        try:
            for page, text in text_pages(path, args.html_mode):
                count = count_tokens(text)
                label = str(page) if path.suffix.lower() == '.pdf' else '-'
                print(f'{path.name:<32} {label:>8} {count:>10,} {len(text):>12,}')
                totals[path.suffix.lower()] = totals.get(path.suffix.lower(), 0) + count
        except Exception as exc:
            errors += 1
            print(f'ERROR {path.name}: {type(exc).__name__}: {exc}', file=sys.stderr)
    for extension, count in sorted(totals.items()):
        print(f'Total {extension}: {count:,} tokens')
    print('Totals are per format; MD/PDF/HTML may represent the same pages. Do not sum them as unique content.')
    print('PDF counts exclude image tokens. Prompts, output tokens and API-specific processing are not included.')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
