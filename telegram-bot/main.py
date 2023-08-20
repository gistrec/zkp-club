import asyncio
import boto3
import json
import time
import os

from messages import welcome_message, voting_process_message, application_already_approved_message, \
    application_already_rejected_message, after_admission_message

from messages import build_general_vote_message, build_admin_vote_message

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, ContextTypes, Defaults, CommandHandler, ChatJoinRequestHandler, MessageHandler, TypeHandler, filters
from telegram.constants import ParseMode

from zkpclub.templates import DatabaseUser, TelegramUser, from_json, to_json


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.getenv('TABLE_NAME'))


telegram_token = os.getenv('TELEGRAM_TOKEN')
defaults = Defaults(parse_mode=ParseMode.MARKDOWN)
application = Application.builder().token(telegram_token).defaults(defaults).build()


# Добавляем в context.user_data["database"] информацию о пользователе
async def preprocess_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(update)
    db_response = table.get_item(Key={"user_id": update.effective_user.id})
    if "Item" not in db_response:
        print(f"Добавляем в БД информацию о пользователе {update.effective_user}")

        telegram_user = TelegramUser(
            id=update.effective_user.id,
            first_name=update.effective_user.first_name,
            last_name=update.effective_user.last_name,
            username=update.effective_user.username,
            language_code=update.effective_user.language_code
        )
        database_user = DatabaseUser(user_id=update.effective_user.id, telegram_user=telegram_user)

        context.user_data["database"] = database_user
        table.put_item(Item=to_json(database_user))
    else:
        context.user_data["database"] = from_json(db_response["Item"])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Доступные статусы: idle, processing, accepted, rejected
    # idle - отправляем кнопку на заполнение анкеты
    # processing - пишем, что заявка еще рассматривается
    # accepted - отправляем ссылку на чат
    # rejected - отправляем сообщение, что вы можете связаться с администраторами
    application_status = context.user_data["database"].application.status
    
    if application_status == "idle":
        await update.message.reply_text(
            text=welcome_message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(text="Заполнить заявку", web_app=WebAppInfo(url="https://id94y26uyi.execute-api.eu-central-1.amazonaws.com/production/pages/admission.html"))]
            ]),
        )
        return
    if application_status == "processing":
        await update.message.reply_text(voting_process_message)
        return
    if application_status == "accepted":
        await update.message.reply_text(application_already_approved_message)
        return
    if application_status == "rejected":
        await update.message.reply_text(application_already_rejected_message)
        return


# Handle incoming WebAppData
async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    full_name = context.user_data["database"].application.data["full_name"]
    user_id = context.user_data["database"].user_id

    # Отправляем сообщение вступившему человеку
    await update.effective_user.send_message(after_admission_message)

    # Отправляем сообщение в общую группу
    message = await context.bot.send_message(
        chat_id=os.getenv("GROUP_ID"),
        text=build_general_vote_message(user_id, full_name),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="За (0)", url=f"http://t.me/zkpclubbot/vote?startapp=positive_{user_id}"), InlineKeyboardButton(text="Против (0)", url=f"http://t.me/zkpclubbot/vote?startapp=negative_{user_id}")],
            [InlineKeyboardButton(text="Посмотреть анкету", url=f"https://t.me/zkpclubbot/vote?startapp=positive_{user_id}")],
        ]))

    # Отправляем сообщение админам
    for admin_id in os.getenv("ADMIN_IDS").split(','):
        await context.bot.send_message(
            chat_id=int(admin_id),
            text=build_admin_vote_message(user_id, full_name),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(text="Посмотреть все заявки", web_app=WebAppInfo(url="https://t.me/zkpclubbot/applications"))],
            ]
        ))

    # Обновляем message_id
    context.user_data["database"].application.message_id = message.id
    context.user_data["database"].application.message_timestamp = int(time.time())
    table.put_item(Item=to_json(context.user_data["database"]))



async def join_request(update, context):
    application_status = context.user_data["database"].application.status
    if application_status == "accepted":        
        await context.bot.approve_chat_join_request(
            chat_id=update.effective_chat.id, user_id=update.effective_user.id
        )


application.add_handler(TypeHandler(Update, preprocess_request), -1)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(~filters.VIA_BOT, start))

application.add_handler(MessageHandler(filters.VIA_BOT, web_app_data))

application.add_handler(ChatJoinRequestHandler(join_request))


async def process_telegram_message(telegram_message, context):
    try:
        # Надеемся, что подтянется закешированная версия application, которая уже проинициализирована.
        if not application._initialized:
            await application.initialize()

        update = Update.de_json(json.loads(telegram_message), application.bot)
        await application.process_update(update)
    except Exception as e:
        print(e)
        return {"statusCode": 500}

    return {"statusCode": 200}


def lambda_handler(event, context):
    print(event)
    telegram_message = event["body"]
    print(telegram_message)

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(process_telegram_message(telegram_message, context))


if os.getenv("IS_AWS", "0") != "1":
    application.run_polling()
