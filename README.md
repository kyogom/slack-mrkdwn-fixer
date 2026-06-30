# slack-mrkdwn-fixer

Claude Code から Slack へ下書き・送信するとき（`slack_send_message_draft` / `slack_send_message`）に、文字装飾が崩れないよう本文の Markdown を正規化する [Claude Code](https://code.claude.com/) スキルです。

## 何を解決するか

Slack のテキストは Markdown ではなく独自記法の mrkdwn で、装飾は一重の記号で書きます（`*bold*`、`_italic_`、`~strike~`）。一方 Slack MCP は渡した本文を標準 Markdown として解釈し、内部で mrkdwn へ変換してから送ります。

- 標準 Markdown の `**x**` は mrkdwn の `*x*`（太字）に、`*x*` は `_x_`（イタリック）に化ける
- 変換後の `*x*` / `~x~` は、開き記号の直前と閉じ記号の直後が空白か行境界のときだけ装飾される
- 日本語は句読点や助詞が記号に密着するため、`・**作成数**を追う` のような文で装飾が効かない

このスキルは強調をすべて `**bold**` に寄せ、各スパンの外側が非空白なら半角スペースを補って境界を作ります。コードブロックとインラインコードの中身、`snake_case` などの識別子は変更しません。

## インストール

### プラグイン経由

```shell
/plugin marketplace add kyogom/slack-mrkdwn-fixer
/plugin install slack-mrkdwn-fixer@kyogom-skills
```

### 手動

```shell
git clone https://github.com/kyogom/slack-mrkdwn-fixer.git
cp -r slack-mrkdwn-fixer/plugins/slack-mrkdwn-fixer/skills/slack-mrkdwn-fixer ~/.claude/skills/
```

## 使い方

Slack に送る本文を生成するときにスキルが発火し、本文を正規化スクリプトに通してから `message` に渡します。スクリプトは単体でも使えます。

```bash
printf '%s' "$DRAFT" | python3 scripts/fix_slack_mrkdwn.py
```

```text
入力                       出力
・**作成数**を追う      →  ・ **作成数** を追う
これは_重要_です        →  これは **重要** です
user_id と auth_id      →  user_id と auth_id      （識別子は維持）
`a_b_c` はそのまま      →  `a_b_c` はそのまま      （コードは保護）
```

送信前の見え方は Slack の下書きプレビューで確認するのが確実です。

## ライセンス

MIT
