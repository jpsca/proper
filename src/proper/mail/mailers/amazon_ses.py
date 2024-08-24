"""
Mailer for Amazon Simple Email Server.
"""
import logging

from ..message import EmailMessage
from .base import BaseMailer


class AmazonSESMailer(BaseMailer):
    """A mailer for Amazon Simple Email Server.
    Requires the `boto3` python library.
    """

    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        region_name: str = "us-east-1",
        return_path: str | None = None,
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
        self.return_path = return_path

    def send_messages(self, *email_messages: EmailMessage) -> list[dict]:
        """ """
        logger = logging.getLogger("mailshake:AmazonSESMailer")
        if not email_messages:
            logger.debug("No email messages to send")
            return []

        responses = []

        for msg in email_messages:
            destination_data = {"ToAddresses": msg.to}
            if msg.cc:
                destination_data["CcAddresses"] = msg.cc
            if msg.bcc:
                destination_data["BccAddresses"] = msg.bcc
            if msg.reply_to:
                destination_data["ReplyToAddresses"] = msg.reply_to

            body = {"Data": msg.body, "Charset": msg.encoding}
            if msg.content_subtype == "html":
                body_data = {"Html": body}
            else:
                body_data = {"Text": body}

            data = {
                "Source": msg.from_email,
                "Destination": destination_data,
                "Message": {
                    "Subject": {"Data": msg.subject, "Charset": msg.encoding},
                    "Body": body_data,
                },
            }
            if msg.reply_to:
                data["ReplyToAddresses"] = msg.reply_to
            if msg.tags:
                data["Tags"] = msg.tags
            if self.return_path:
                data["ReturnPath"] = self.return_path

            logger.debug("Sending email from %s to %s", msg.from_email, msg.to)
            response = self.client.send_email(**data)
            responses.append(response)

        return responses
