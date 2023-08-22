import os
import logging

import sentry_sdk

from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration


logging.getLogger().setLevel(logging.DEBUG)


def init():
    assert os.getenv("SENTRY_DSN")

    aws_lambda = AwsLambdaIntegration(
        timeout_warning=True
    )
    sentry_logging = LoggingIntegration(
        level=logging.DEBUG,
        event_level=logging.WARNING
    )

    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            aws_lambda,
            sentry_logging,
        ],
        traces_sample_rate=1.0,
    )


def set_telegram_user(id, username = None):
    sentry_sdk.set_user({
        "id": id,
        "username": username,
    })
