import os
import io
import cgi
import time
import json
import boto3
import base64
import asyncio


import hmac
import hashlib

from urllib.parse import unquote, parse_qs
import telegram

from zkpclub.templates import Application, UserData, from_json, to_json
from zkpclub.sentry import init as init_sentry


init_sentry()


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv('TABLE_NAME'))

s3 = boto3.resource("s3")
s3_bucket = s3.Bucket(os.getenv('BUCKET_NAME'))


def parse_form_data(event):
    body = base64.b64decode(event['body'])
    fp = io.BytesIO(body)

    pdict = cgi.parse_header(event['headers']['Content-Type'])[1]
    if 'boundary' in pdict:
        pdict['boundary'] = pdict['boundary'].encode('utf-8')
    pdict['CONTENT-LENGTH'] = len(body)
    return cgi.parse_multipart(fp, pdict)


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


async def process(event):
    form_data = parse_form_data(event)
    
    init_data = form_data['initData'][0]
    extension = form_data['extension'][0]
    image = form_data['image'][0]
    application = json.loads(form_data['application'][0])

    # Сравниваем hash из данных в initData с хэшем токена бота.
    if not validate_init_data(init_data):
        return {
            'statucCode': 401,
            'body': 'Unauthorized',
        }

    user_id = json.loads(parse_qs(init_data)['user'][0])['id']
    avatar_url = f"{user_id}.{extension}"

    db_response = table.get_item(Key={"user_id": user_id})
    if "Item" not in db_response:
        return {
            'statucCode': 403,
            'body': 'Forbidden',
        }
    database_user = from_json(db_response["Item"])

    database_user.application = Application(status="processing", data=UserData(**application, avatar_url=avatar_url))

    s3_bucket.put_object(
        Key=f"avatars/{avatar_url}",
        Body=image,
        ContentType="image/${extension}",
    )

    table.put_item(Item=to_json(database_user))

    # Отправляем сообщение боту от имени пользователя
    query_id = parse_qs(init_data)['query_id'][0]
    telegram_token = os.getenv('TELEGRAM_TOKEN')
    bot = telegram.Bot(telegram_token)
    await bot.answer_web_app_query(
        web_app_query_id=query_id,
        result=telegram.InlineQueryResultArticle(
            id=str(time.time()),
            title="Заявка на вступление в клуб ЗКП",
            input_message_content=telegram.InputTextMessageContent(
                message_text="<b>ФИО</b> " + application['full_name'] + "\n"
                             "<b>Телефон</b> " + application['phone'] + "\n\n"
                             "<b>Ссылки на сайты</b>\n" + "\n".join(application['sites_links']) + "\n\n"
                             "<b>Ссылки на соц. сети</b>\n" + "\n".join(application['social_links']) + "\n\n"
                             "<b>Цифровые показатели бизнеса</b>\n" + application['achievements'] + "\n\n"
                             "<b>О себе</b>\n" + application['bio'],
                parse_mode=telegram.constants.ParseMode.HTML,
                disable_web_page_preview=True,
            ),
            thumbnail_url="https://id94y26uyi.execute-api.eu-central-1.amazonaws.com/production/avatar/" + avatar_url,
        ),
    )

    return {
        'statusCode': 200,
        'body': 'Multipart data processed successfully'
    }


def lambda_handler(event, context):
    print(event)

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(process(event))
