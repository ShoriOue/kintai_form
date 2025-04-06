# kintai_form

Slackで勤怠報告を行うためのLambda関数

## セットアップ方法

1. 必要なライブラリをインストール:
```
pip install -r requirements.txt -t .
```

2. デプロイパッケージの作成:
```
zip -r deployment_package.zip . -x "*.git*"
```

3. AWS Lambdaにデプロイ

4. 環境変数の設定:
   - SLACK_BOT_TOKEN: Slack Bot Token
   - WEBHOOK_URL: Slackの通知用Webhook URL

## 機能
- Slackスラッシュコマンド `/kintai` で勤怠報告フォームを表示
- 遅刻、早退、有給休暇などの報告が可能
- 報告後に自動でチャンネルに通知およびユーザーに完了メッセージを送信
 
