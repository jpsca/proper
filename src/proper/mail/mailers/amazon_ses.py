"""
Mailer for Amazon Simple Email Server (SES) v1 & v2.
"""
from proper.helpers import logger

from ..message import EmailMessage
from .base import BaseMailer


class AmazonSESMailer(BaseMailer):
    """A mailer for Amazon Simple Email Server v1.
    Requires the `boto3` python library.
    """

    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str = "us-east-1",
        feedback_email: str | None = None,
        **kwargs
    ):
        """ """
        import boto3  # type: ignore

        super().__init__(**kwargs)
        self.client = boto3.client(
            "ses",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        assert self.client
        self.feedback_email = feedback_email

    def send_emails(self, *email_messages: EmailMessage) -> list[dict]:
        """ """
        if not email_messages:
            logger.debug("No email messages to send")
            return []

        responses = []

        for msg in email_messages:
            data = {**msg.extra_data}

            data["Source"] = msg.from_email

            destination_data = {"ToAddresses": msg.to}
            if msg.cc:
                destination_data["CcAddresses"] = msg.cc
            if msg.bcc:
                destination_data["BccAddresses"] = msg.bcc
            data["Destination"] = destination_data

            if msg.reply_to:
                data["ReplyToAddresses"] = msg.reply_to

            if self.feedback_email:
                data["ReturnPath"] = self.feedback_email

            body = {"Data": msg.body, "Charset": msg.encoding}
            if msg.content_subtype == "html":
                body_data = {"Html": body}
            else:
                body_data = {"Text": body}

            data["Message"] = {
                "Subject": {"Data": msg.subject, "Charset": msg.encoding},
                "Body": body_data,
            }

            if msg.tags:
                data["Tags"] = [
                    {"Name": key, "Value": value}
                    for key, value in msg.tags.items()
                ]

            logger.debug("Sending email from %s to %s", msg.from_email, msg.to)
            response = self.client.send_email(**data)
            responses.append(response)

        return responses


class AmazonSES2Mailer(BaseMailer):
    """A mailer for Amazon Simple Email Server v2.
    Requires the `boto3` python library.
    """

    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str = "us-east-1",
        feedback_email: str | None = None,
        **kwargs
    ):
        """ """
        import boto3  # type: ignore

        super().__init__(**kwargs)
        self.client = boto3.client(
            "sesv2",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )
        assert self.client
        self.feedback_email = feedback_email

    def send_emails(self, *email_messages: EmailMessage) -> list[dict]:
        """ """
        if not email_messages:
            logger.debug("No email messages to send")
            return []

        responses = []

        for msg in email_messages:
            data = {**msg.extra_data}

            data["FromEmailAddress"] = msg.from_email

            destination_data = {"ToAddresses": msg.to}
            if msg.cc:
                destination_data["CcAddresses"] = msg.cc
            if msg.bcc:
                destination_data["BccAddresses"] = msg.bcc
            data["Destination"] = destination_data

            if msg.reply_to:
                data["ReplyToAddresses"] = msg.reply_to

            if self.feedback_email:
                data["FeedbackForwardingEmailAddress"] = self.feedback_email

            body = {"Data": msg.body, "Charset": msg.encoding}
            if msg.content_subtype == "html":
                body_data = {"Html": body}
            else:
                body_data = {"Text": body}

            data["Content"] = {
                "Simple": {
                    "Subject": {"Data": msg.subject, "Charset": msg.encoding},
                    "Body": body_data,
                }
            }

            if msg.headers:
                data["Content"]["Simple"]["Headers"] = [
                    {"Name": key, "Value": value}
                    for key, value in msg.headers.items()
                ]

            if msg.tags:
                data["EmailTags"] = [
                    {"Name": key, "Value": value}
                    for key, value in msg.tags.items()
                ]

            logger.debug("Sending email from %s to %s", msg.from_email, msg.to)
            response = self.client.send_email(**data)
            responses.append(response)

        return responses
