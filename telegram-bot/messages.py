from telegram import helpers


welcome_message = helpers.escape_markdown("Дорогие предприниматели, для вступления в клуб ЗКП вам необходимо заполнить заявку. Если больше 50% действующих членов проголосуют положительно, то вы будете добавлены в наши чаты, и сможете посещать наши встречи.")

voting_process_message = helpers.escape_markdown("Ваша заявка находится в процессе голосования - обычно этот процесс занимает до двух дней. После завершения голосования Вам будет отправлено сообщение о результате.")

application_already_approved_message = helpers.escape_markdown("Вы уже состоите в клубе ЗКП")

application_already_rejected_message = helpers.escape_markdown("К сожалению, Ваша заявка была отклонена")

after_admission_message = helpers.escape_markdown("Спасибо за вашу заявку. Если большинство участников клуба одобрят ваше вступление (обычно этот процесс занимает до двух дней) в клуб ЗКП, вы будете приглашены в наш чат.")

def build_general_vote_message(user_id, full_name):
    user_mention = helpers.mention_markdown(user_id, full_name)

    return helpers.escape_markdown("Уважаемые участники клуба ЗКП, ") + user_mention + helpers.escape_markdown(" заполнил заявку на вступление в наш клуб. Прошу проголосовать за его кандидатуру.\n") + \
           helpers.escape_markdown("\n") + \
           helpers.escape_markdown("Если положительных голосов будет больше 50%, то заявка будет одобрена и человек будет приглашен в этот чат.\n") + \
           helpers.escape_markdown("Голосование анонимное, но при голосовании вам будет предложено заполнить отзыв, который могут посмотреть другие участники клуба")

def build_admin_vote_message(user_id, full_name):
    user_mention = helpers.mention_markdown(user_id, full_name)

    return helpers.escape_markdown("Новая заявка на вступление в группу от ") + user_mention + helpers.escape_markdown("\n") + \
           helpers.escape_markdown("\n") + \
           helpers.escape_markdown("Одобрить или отклонить все заявки можно по кнопке ниже.\n") + \
           helpers.escape_markdown("В случае одобрения, новому участнику будет отправлена инвайт-ссылка, по которой он сможет перейти в чат")
