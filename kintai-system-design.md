# Slack勤怠報告システム 設計書

## 1. システム概要

本システムは、AWS LambdaとSlack APIを連携して社内の勤怠報告をSlackから簡単に行えるようにするものです。Slackのスラッシュコマンド（`/kintai`）を使用して勤怠報告フォームを呼び出し、入力された情報を指定したSlackチャンネルに通知する仕組みです。

## 2. システム構成

### 2.1 使用技術・サービス
- AWS Lambda
- Amazon API Gateway (Lambdaへのエンドポイント提供)
- Slack API
  - スラッシュコマンド
  - インタラクティブコンポーネント
  - Webhook
- Python 3.x

### 2.2 アーキテクチャ図
```
[Slack] --- スラッシュコマンド(/kintai) ---> [API Gateway] ---> [Lambda] ---> [Slack Webhook]
                                                                  |
                                                                  v
                                                          [Slack Direct Message]
```

## 3. 処理フロー

1. ユーザーがSlackで `/kintai` コマンドを実行
2. API GatewayがリクエストをLambda関数に転送
3. Lambda関数がSlack APIを呼び出して入力フォーム（モーダル）を表示
4. ユーザーがフォームに情報を入力して送信
5. Lambda関数が送信内容を処理
6. 指定したSlackチャンネルに勤怠報告内容をWebhook経由で通知
7. 報告したユーザーに完了メッセージをDMで送信

## 4. 機能詳細

### 4.1 勤怠報告フォーム
- 日付選択（デフォルトは当日）
- 報告種類選択
  - 遅刻
  - 早退
  - 有給休暇
  - 体調不良
  - その他
- 詳細情報入力欄（任意）

### 4.2 通知機能
- 勤怠報告内容をSlackチャンネルに通知
  - 提出者
  - 日付
  - 報告種類
  - 詳細情報
- 報告完了をユーザーにDMで通知

## 5. セキュリティ考慮事項

- SlackのBot Token、Webhook URLはAWS環境変数として管理
- リクエストの簡易検証機能を実装
- AWS Lambdaのアクセス権限を必要最小限に設定
