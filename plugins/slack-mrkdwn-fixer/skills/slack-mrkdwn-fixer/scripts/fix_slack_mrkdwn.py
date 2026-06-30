#!/usr/bin/env python3
"""Slack MCP 下書き/送信用に Markdown を正規化する。

Slack の MCP (slack_send_message_draft / slack_send_message) は本文を
標準 Markdown として解釈し、内部で mrkdwn へ変換してから表示する。
日本語チャットで装飾を確実に効かせるために、太字・イタリック・取り消し線を
それぞれ一つの記法に揃え、各スパンの外側に境界の半角スペースを確保する。

- 太字   : **x** はそのまま。__x__ -> **x** に統一。
           ただし snake_case / user_id のような識別子（__ 対の外側が両方とも
           ASCII 英数字）は対象外。
- イタリック: *x* -> _x_ に統一。_x_ はそのまま残す（太字に変換しない）。
- 取り消し線: ~x~ -> ~~x~~ に統一。~~x~~ はそのまま。
- `code`            この経路で正常に効くため変更しない。
- 三連バッククォートのコードブロック、インラインコードの中身は変更しない。

【重要・実機検証で確定した境界条件】
MCP は **bold** を mrkdwn の *bold* へ、_italic_ を _italic_ へ、~~strike~~ を
~strike~ へ変換する。Slack はこれらを「開き記号の直前」「閉じ記号の直後」の
両方が空白か行境界のときだけ装飾描画する。全角文字（・ 、 を （ など）が記号に
直接接触すると無効化される（太字・イタリック・取り消し線のいずれも同じ）。
そのため正規化後、各スパンの外側が非空白なら半角スペースを挿入して境界を作る
（行頭・行末・既存の空白のときは挿入しない）。イタリックの _..._ は識別子を
誤装飾しないよう、両端が識別子文字（英数字・アンダースコア）のときは触らない。

stdin から読み、正規化後を stdout に出力する。
"""
import re
import sys

ASCII_ALNUM = re.compile(r"[A-Za-z0-9]")
IDENT = re.compile(r"[A-Za-z0-9_]")


def _dunder_to_bold(text: str) -> str:
    """__x__ -> **x**。両端が ASCII 英数字の識別子はスキップする。"""
    pat = re.compile(r"__([^_\n]+?)__")
    out = []
    pos = 0
    for m in pat.finditer(text):
        s, e = m.span()
        before = text[s - 1] if s > 0 else ""
        after = text[e] if e < len(text) else ""
        if before and after and ASCII_ALNUM.match(before) and ASCII_ALNUM.match(after):
            continue
        out.append(text[pos:s])
        out.append("**" + m.group(1) + "**")
        pos = e
    out.append(text[pos:])
    return "".join(out)


def _pad(text: str) -> str:
    """**bold** / _italic_ / ~~strike~~ の外側が非空白なら半角スペースを挿入する。

    Slack の *bold* / _italic_ / ~strike~ は、開き記号の直前・閉じ記号の直後が
    空白か行境界でないと描画されない。前後の文字は元テキスト基準で判定する。
    _italic_ は snake_case などを誤って装飾しないよう、両端が識別子文字なら触らない。
    """
    pat = re.compile(r"\*\*[^*\n]+?\*\*|~~[^~\n]+?~~|_[^_\n]+?_")

    def repl(m):
        s, e = m.span()
        tok = m.group(0)
        before = text[s - 1] if s > 0 else ""
        after = text[e] if e < len(text) else ""
        if tok[0] == "_":
            if before and after and IDENT.match(before) and IDENT.match(after):
                return tok
        left = " " if (before and not before.isspace()) else ""
        right = " " if (after and not after.isspace()) else ""
        return left + tok + right

    return pat.sub(repl, text)


def fix(text: str) -> str:
    # 1. 三連バッククォートのコードブロックを退避（中身は触らない）
    fences = []

    def _stash_fence(m):
        fences.append(m.group(0))
        return f"\x00F{len(fences) - 1}\x00"

    text = re.sub(r"```.*?```", _stash_fence, text, flags=re.DOTALL)

    # 2. インラインコードを退避（中身を後続の変換から守る）
    codes = []

    def _stash_code(m):
        codes.append(m.group(0))
        return f"\x00C{len(codes) - 1}\x00"

    text = re.sub(r"`[^`\n]+?`", _stash_code, text)

    # 3. 各装飾を一つの記法に統一
    text = _dunder_to_bold(text)                 # __x__ -> **x**（**x** は維持）
    # 一重アスタリスク *x* -> _x_（イタリックを _ に寄せる。** には触れない）
    text = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)", r"_\1_", text)
    # 一重チルダ ~x~ -> ~~x~~（取り消し線に統一。~~ には触れない）
    text = re.sub(r"(?<!~)~(?!~)([^~\n]+?)~(?!~)", r"~~\1~~", text)

    # 3.5 太字・イタリック・取り消し線スパンの外側に境界（半角スペース）を確保
    text = _pad(text)

    # 4. 退避を復元
    for i, c in enumerate(codes):
        text = text.replace(f"\x00C{i}\x00", c)
    for i, f in enumerate(fences):
        text = text.replace(f"\x00F{i}\x00", f)

    return text


def main():
    sys.stdout.write(fix(sys.stdin.read()))


if __name__ == "__main__":
    main()
