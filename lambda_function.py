import json
import os
import logging
import datetime
import base64
import requests
from urllib.parse import parse_qs

# 環境変数の設定
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']
# SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
WEBHOOK_URL = os.environ['WEBHOOK_URL']

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def verify_slack_request(event):
    # ヘッダーにSlack関連のものがあるか確認するだけの簡易チェック
    headers = event.get('headers', {})
    return 'x-slack-signature' in headers

def lambda_handler(event, context):
    # 簡易的なリクエスト検証
    if not verify_slack_request(event):
        return {
            'statusCode': 403,
            'body': json.dumps('Invalid request')
        }
    
    logger.debug(event)

    body = event['body']

    if event['isBase64Encoded']:
        body = base64.b64decode(body).decode("utf-8")

    # リクエストのボディをパース
    body = parse_qs(body) if isinstance(body, str) else body

    logger.debug(body)

    # スラッシュコマンドの処理
    if 'command' in body and body['command'][0] == '/kintai':
        return handle_slash_command(body)
    
    # インタラクティブペイロードの処理
    if 'payload' in body:
        payload = json.loads(body['payload'][0])
        if payload['type'] == 'view_submission':
            return handle_submission(payload)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Unknown request type')
    }

def handle_slash_command(body):
    logger.info("Handling slash command")
    
    trigger_id = body['trigger_id'][0]
    modal = open_modal(trigger_id)
    
    # Slack APIを呼び出してモーダルを開く
    response = call_slack_api("views.open", modal)
    
    return {
        'statusCode': 200,
        'body': ""  # Slackは空のレスポンスを期待
    }

def open_modal(trigger_id):
    # モーダルフォームを定義する
    today = (datetime.datetime.now() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
    
    modal = {
        "trigger_id": trigger_id,
        "view": {
            "type": "modal",
            "callback_id": "kintai_report",
            "title": {"type": "plain_text", "text": "勤怠報告"},
            "submit": {"type": "plain_text", "text": "送信"},
            "blocks": [
                # 日付選択
                {
                    "type": "section",
                    "block_id": "date_block",
                    "text": {"type": "mrkdwn", "text": "*取得日*"},
                    "accessory": {
                        "type": "datepicker",
                        "action_id": "date_picker",
                        "initial_date": today,
                        "placeholder": {"type": "plain_text", "text": "日付を選択"}
                    }
                },
                # 報告種類の選択
                {
                    "type": "input",
                    "block_id": "report_type_block",
                    "element": {
                        "type": "static_select",
                        "action_id": "report_type",
                        "placeholder": {"type": "plain_text", "text": "報告種類を選択"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "体調不良"}, "value": "sick"},
                            {"text": {"type": "plain_text", "text": "遅刻"}, "value": "late"},
                            {"text": {"type": "plain_text", "text": "早退"}, "value": "early_leave"},
                            {"text": {"type": "plain_text", "text": "遅刻+早退"}, "value": "late_early_leave"},
                            {"text": {"type": "plain_text", "text": "有給休暇(全休)"}, "value": "paid_leave"},
                            {"text": {"type": "plain_text", "text": "有給休暇(午前休)"}, "value": "paid_leave_am"},
                            {"text": {"type": "plain_text", "text": "有給休暇(午後休)"}, "value": "paid_leave_pm"},
                            {"text": {"type": "plain_text", "text": "特別休暇"}, "value": "special_leave"},
                            {"text": {"type": "plain_text", "text": "欠勤"}, "value": "absent"},
                            {"text": {"type": "plain_text", "text": "その他"}, "value": "other"}
                        ]
                    },
                    "label": {"type": "plain_text", "text": "報告種類"}
                },
                # 詳細情報
                {
                    "type": "input",
                    "block_id": "details_block",
                    "optional": True,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "details",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "詳細な情報を入力してください（任意）"}
                    },
                    "label": {"type": "plain_text", "text": "詳細"}
                }
            ]
        }
    }
    return modal

def handle_submission(payload):
    logger.info("Handling form submission")
    
    # 送信されたフォームの値を取得
    values = payload['view']['state']['values']
    user = payload['user']['name']
    user_id = payload['user']['id']
    
    # 日付の取得
    date = values['date_block']['date_picker']['selected_date']
    
    # 報告種類の取得
    report_type_value = values['report_type_block']['report_type']['selected_option']['value']
    report_type_text = values['report_type_block']['report_type']['selected_option']['text']['text']
    
    # 詳細の取得
    details = values['details_block']['details']['value'] if 'value' in values['details_block']['details'] else "詳細なし"
    
    # Webhook経由でSlackチャンネルに通知を送信
    response = send_webhook_notification(user, date, report_type_text, details)
    
    # Webhook送信の成否で分岐
    if response is not None and response.status_code >= 200 and response.status_code < 300:
        # ユーザーに完了メッセージを送信（detailsも渡す）
        send_completion_message(user_id, date, report_type_text, details)
    else:
        # エラー時はSlackのレスポンス内容もログに記録
        logger.error(f"Webhook送信エラー: {response.status_code if response else 'No Response'} - {response.text if response else 'No Response Text'}")
        # エラー通知を送信
        send_error_message(user_id)
    
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            "response_action": "clear"
        })
    }

def send_webhook_notification(user, date, report_type, details):
    # 申請日（現在の日時）を取得
    submit_date = (datetime.datetime.now() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
    
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "勤怠報告が提出されました"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*提出者:*\n{user}"},
                    {"type": "mrkdwn", "text": f"*申請日:*\n{submit_date}"},
                    {"type": "mrkdwn", "text": f"*取得日:*\n{date}"},
                    {"type": "mrkdwn", "text": f"*報告種類:*\n{report_type}"},
                    {"type": "mrkdwn", "text": f"*詳細:*\n{details}"}
                ]
            }
        ]
    }
    
    # Webhookを使って通知を送信
    response = requests.post(
        WEBHOOK_URL,
        json=message,
        headers={'Content-Type': 'application/json'}
    )
    return response

def send_completion_message(user_id, date, report_type, details):
    message = {
        "channel": user_id,
        "text": (
            "勤怠報告が正常に送信されました。\n\n" +
            f"取得日: {date}, " +
            f"報告種類: {report_type}, " +
            f"詳細: {details}"
        )
    }
    call_slack_api("chat.postMessage", message)
    return

def send_error_message(user_id):
    message = {
        "channel": user_id,
        "text": "勤怠報告の送信中にエラーが発生しました。管理者にご連絡ください。"
    }
    call_slack_api("chat.postMessage", message)
    return

def call_slack_api(api_method, data):
    url = f"https://slack.com/api/{api_method}"
    
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {SLACK_BOT_TOKEN}'
    }
    
    response = requests.post(url, json=data, headers=headers)
    return response.json()