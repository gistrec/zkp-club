import os
import json
import time
import boto3 
import asyncio
import decimal

import hmac
import hashlib

from boto3.dynamodb.conditions import Attr
from urllib.parse import unquote, parse_qs


from telegram import Bot, helpers
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv('TABLE_NAME'))


def validate_init_data(init_data, c_str="WebAppData"):
    hash = parse_qs(init_data)['hash'][0]

    # Удаляем hash из строки initData
    init_data = sorted([
        chunk.split("=") 
        for chunk in unquote(init_data).split("&") 
        if chunk[:len("hash=")]!="hash="],
        key=lambda x: x[0])
    init_data = "\n".join([f"{rec[0]}={rec[1]}" for rec in init_data])

    telegram_token = os.getenv('TELEGRAM_TOKEN')
    secret_key = hmac.new(c_str.encode(), telegram_token.encode(), hashlib.sha256 ).digest()
    data_check = hmac.new(secret_key, init_data.encode(), hashlib.sha256)

    return data_check.hexdigest() == hash


def default_type_error_handler(obj):
    if isinstance(obj, decimal.Decimal):
        return int(obj)
    raise TypeError


async def update_vote_message(telegram_bot, user_data):
    message_id = int(user_data["application"]["message_id"])
    full_name = helpers.escape_markdown(user_data["application"]["data"]["full_name"], version=2)
    user_id = user_data["user_id"]
    positive_count = len(user_data["application"]["positive_reviews"])
    negative_count = len(user_data["application"]["negative_reviews"])

    # NOTE: Не забыть поменять текст в zkp-club-telegram-bot в функции, где это сообщение обновляется
    await telegram_bot.edit_message_text(
        chat_id=os.getenv("GROUP_ID"),
        message_id=message_id,
        text=f"Уважаемые участники клуба ЗКП, [{full_name}](tg://user?id={user_id}) заполнил заявку на вступление в наш клуб\\. Прошу проголосовать за его кандидатуру\\.\n\n"
            "Если положительных голосов будет больше 50%, то заявка будет одобрена и новый участник будет приглашен в этот чат\\.\n"
            "Голосование анонимное, но при голосовании вам будет предложено заполнить отзыв, который могут посмотреть другие участники клуба",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text=f"За ({positive_count})", url=f"https://t.me/zkpclubbot/vote?startapp=positive_{user_id}"), InlineKeyboardButton(text=f"Против ({negative_count})", url=f"https://t.me/zkpclubbot/vote?startapp=negative_{user_id}")],
            [InlineKeyboardButton(text="Посмотреть анкету", url=f"https://t.me/zkpclubbot/vote?startapp=positive_{user_id}")],
        ]))


# Change message after voting finished
async def finish_vote_message(telegram_bot, user_data):
    # Проверяем, что с момента отправки сообщения прошло не более 47 часов (через 48 часов его нельзя больше редактировать)
    message_timestamp = int(user_data["application"]["message_id"])
    if time.time() > message_timestamp + 60 * 60 * 47:
        print("Не изменяем сообщение, т.к. прошло более 47 часов")
        return

    message_id = int(user_data["application"]["message_id"])
    full_name = user_data["application"]["data"]["full_name"]
    user_id = user_data["user_id"]
    
    text = helpers.escape_markdown(
        f"Голосование за вступление участника [{full_name}](tg://user?id={user_id}) в наш клуб завершено\\.\n\n"
        "Спасибо всем за Ваши голоса и комментарии\\.",
        version=2
    )

    await telegram_bot.edit_message_text(
        chat_id=os.getenv("GROUP_ID"),
        message_id=message_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN_V2
    )


# Send invite link to user
async def invite_user_to_chat(telegram_bot, user_id):
    await telegram_bot.send_message(
        chat_id=user_id,
        text=f"Ваша заявка на вступление в клуб ЗКП была одобрена\\.\n\n"
            "Вы можете перейти в нашу группу, нажав на кнопку ниже.\n",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="Подать заявку на вступление", url=os.getenv("INVITE_LINK"))],
        ]
    ))


async def decline_user(telegram_bot, user_id):
    await telegram_bot.send_message(
        chat_id=user_id,
        text=f"Извините, но ваша заявка на вступление в клуб ЗКП была отклонена\\.\n"
             "По всем вопросам вы можете написать администратору"
    )


def lambda_handler(event, context):
    print(event)
    if event["resource"] == "/vote/{voter_id}/{candidate_id}" and event["httpMethod"] == "GET":
        voter_id = str(event["pathParameters"]["voter_id"])  # Строков значение, т.к. ищем в мапе с отзывами
        candidate_id = int(event["pathParameters"]["candidate_id"])

        db_response = table.get_item(Key={"user_id": candidate_id})
        if "Item" in db_response:
            # Ищем проголосовал ли voter_id до этого
            vote = None
            comment = None
            if voter_id in db_response["Item"]["application"]["positive_reviews"]:
                vote = "positive"
                comment = db_response["Item"]["application"]["positive_reviews"][voter_id]
            if voter_id in db_response["Item"]["application"]["negative_reviews"]:
                vote = "negative"
                comment = db_response["Item"]["application"]["negative_reviews"][voter_id]

            return {
                "statusCode": 200,
                "headers": {'Content-Type': 'application/json'},
                "body": json.dumps({
                    "application_data": db_response["Item"]["application"]["data"],
                    "vote": vote,
                    "comment": comment,
                }),
            }
        else:
            return {
                "statusCode": 500,
                "body": "There isn't candidate_id in DynamoDB",           
            }
    if event["resource"] == "/vote/{voter_id}/{candidate_id}" and event["httpMethod"] == "POST":
        voter_id = str(event["pathParameters"]["voter_id"])  # Строков значение, т.к. ищем в мапе с отзывами
        candidate_id = int(event["pathParameters"]["candidate_id"])

        db_response = table.get_item(Key={"user_id": candidate_id})
        if "Item" in db_response:
            body = json.loads(event["body"])
            comment = body["comment"] if body["comment"] else ""
            review_type = body["vote"]
            assert review_type == "positive" or review_type == "negative"

            db_response["Item"]["application"]["positive_reviews"].pop(voter_id, None)
            db_response["Item"]["application"]["negative_reviews"].pop(voter_id, None)

            db_response["Item"]["application"][f"{review_type}_reviews"][voter_id] = {

            }
            table.put_item(Item=db_response["Item"])
            
            loop = asyncio.get_event_loop()
            telegram_bot = Bot(os.getenv("TELEGRAM_TOKEN"))
            loop.run_until_complete(update_vote_message(telegram_bot, db_response["Item"]))

            return {
                "statusCode": 200,
            }
        else:
            return {
                "statusCode": 500,
                "body": "There isn't candidate_id in DynamoDB",           
            }
    if event["resource"] == "/applications" and event["httpMethod"] == "GET":
        filter_expression = Attr('application.status').eq("processing")
        response = table.scan(FilterExpression=filter_expression)
        return {
            "statusCode": 200,
            "headers": {'Content-Type': 'application/json'},
            "body": json.dumps(response['Items'], default=default_type_error_handler)
        }
    if event["resource"] == "/applications/{user_id}/status" and event["httpMethod"] == "PUT":
        user_id = str(event["pathParameters"]["user_id"])
        if str(user_id) not in os.getenv("ADMIN_IDS").split(','):
            return {
                "statusCode": 403,
                "body": "Forbidden",
            }

        status = body["status"]
        assert status == "approve" or status == "reject"

        db_response = table.get_item(Key={"user_id": user_id})
        if "Item" in db_response:
            db_response["Item"]["application"]["status"] == status
            table.put_item(Item=db_response["Item"])

            loop = asyncio.get_event_loop()
            telegram_bot = Bot(os.getenv("TELEGRAM_TOKEN"))

            # Обновляем сообщение о голсовании в общем чате
            loop.run_until_complete(finish_vote_message(telegram_bot, db_response["Item"]))

            if status == "approve":
                # Отправляем пользователю ссылку на чат
                loop.run_until_complete(invite_user_to_chat(telegram_bot, user_id))
            if status == "reject":
                # Отправляем пользвоателю сообщение, что его заявка была отклонена
                loop.run_until_complete(decline_user(telegram_bot, user_id))

            return {
                "statusCode": 200,
            }
        else:
            return {
                "statusCode": 500,
                "body": "There isn't candidate_id in DynamoDB",           
            }

    return {
        "statusCode": 404,
        "body": "There isn't handler in AWS Lambda",
    }
