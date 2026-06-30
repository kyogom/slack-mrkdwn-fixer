#!/usr/bin/env python3
"""Slack MCP 下書き/送信用に Markdown を正規化する。

Slack の MCP (slack_send_message_draft / slack_send_message) は本文を
標準 Markdown として解釈する。日本語チャットで装飾を確実に効かせるため、
強調表記をすべて太字 (**bold**) に統一する。

- *x*   -> **x**   単一アスタリスクは Markdown だとイタリックになるため太字へ
- _x_   -> **x**   アンダースコアのイタリックは日本語隣接で壊れる/読みづらい
- __x__ -> **x**   表記ゆれを ** に統一
  ただし snake_case / user_id / URL などの識別子（アンダースコア対の外側が
  両方とも ASCII 英数字）は対象外。
- **x**            既に太字なので変更しない。
- ~x~ -> ~~x~~      単一チルダは GFM 取り消し線でないため `~~` に統一。
- `code`           この経路で正常に効くため変更しない。
- 三連バッククォートのコードブロック、インラインコードの中身は変更しない。

【重要・実機検証で確定した境界条件】
MCP は **bold** を mrkdwn の *bold*（単一アスタリスク）へ、~~strike~~ を ~strike~
へ変換する。Slack は *bold* / ~strike~ を「開き記号の直前」「閉じ記号の直後」の
両方が空白か行境界のときだけ装飾描画する。全角文字（・ 、 を （ など）が記号に
直接接触すると無効化される（太字も取り消し線も同じ）。
  例) ・**作成数**       -> ・*作成数*  ・が直前で密着 -> 太字にならない
      そこで、**作成数**を -> 、と を が密着       -> 太字にならない
      取り消しは~~これ~~と -> は と と が密着       -> 取り消し線にならない
そのため正規化後、各 **...** / ~~...~~ スパンの外側が非空白なら半角スペースを
挿入して境界を作る（行頭・行末・既存の空白のときは挿入しない）。

stdin から読み、正規化後を stdout に出力する。
"""
import re
import sys

ASCII_ALNUM = re.compile(r"[A-Za-z0-9]")


def _underscore_to_bold(text: str, marker: str) -> str:
    """marker (_ または __) で囲まれた強調を **bold** に変換する。識別子は除外。"""
    esc = re.escape(marker)
    pat = re.compile(esc + r"([^_\n]+?)" + esc)
    out = []
    pos = 0
    for m in pat.finditer(text):
        s, e = m.span()
        before = text[s - 1] if s > 0 else ""
        after = text[e] if e < len(text) else ""
        # 外側が両方とも ASCII 英数字なら識別子とみなしてスキップ
        if before and after and ASCII_ALNUM.match(before) and ASCII_ALNUM.match(after):
            continue
        out.append(text[pos:s])
        out.append("**" + m.group(1) + "**")
        pos = e
    out.append(text[pos:])
    return "".join(out)


def _pad_emphasis(text: str) -> str:
    """**...** / ~~...~~ スパンの外側が非空白なら半角スペースを挿入して境界を作る。

    Slack の *bold* / ~strike~ は、開き記号の直前・閉じ記号の直後が空白か行境界で
    ないと描画されない。前後の文字は元テキスト基準で判定する（re.sub は左から処理し
    置換結果には触れないため、近傍判定は元位置で安定）。
    """
    def repl(m):
        s, e = m.span()
        before = text[s - 1] if s > 0 else ""
        after = text[e] if e < len(text) else ""
        left = " " if (before and not before.isspace()) else ""
        right = " " if (after and not after.isspace()) else ""
        return left + m.group(0) + right

    return re.sub(r"\*\*[^*\n]+?\*\*|~~[^~\n]+?~~", repl, text)


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

    # 3. 強調を ** に統一
    text = _underscore_to_bold(text, "__")   # __x__ -> **x**
    text = _underscore_to_bold(text, "_")    # _x_   -> **x**
    # 単一アスタリスク *x* -> **x**（既存の ** には触れない）
    text = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)", r"**\1**", text)
    # 単一チルダ ~x~ -> ~~x~~（GFM 取り消し線に統一。既存の ~~ には触れない）
    text = re.sub(r"(?<!~)~(?!~)([^~\n]+?)~(?!~)", r"~~\1~~", text)

    # 3.5 太字・取り消し線スパンの外側に境界（半角スペース）を確保
    text = _pad_emphasis(text)

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
