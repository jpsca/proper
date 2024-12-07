from unittest.mock import MagicMock

import pytest

from proper.mail import AmazonSES2Mailer, AmazonSESMailer, EmailMessage


@pytest.fixture
def text_message():
    return EmailMessage(
        from_email="from@example.com",
        to=["to@example.com"],
        subject="Test Subject",
        body="Test Body",
        encoding="utf-8",
        cc=["cc1@example.com", "cc2@example.com"],
        bcc=["bcc@example.com"],
        reply_to=["reply@example.com"],
        tags={"tag1": "value1", "tag2": "value2"},
        headers={"header1": "value1", "header2": "value2"},
    )


@pytest.fixture
def html_message():
    return EmailMessage(
        from_email="from@example.com",
        to=["to@example.com"],
        subject="Test Subject",
        body="Test Body",
        html=True,
        encoding="utf-8",
        cc=["cc1@example.com", "cc2@example.com"],
        bcc=["bcc@example.com"],
        reply_to=["reply@example.com"],
        tags={"tag1": "value1", "tag2": "value2"},
        headers={"header1": "value1", "header2": "value2"},
    )


def test_amazon_ses_mailer_send_text_emails(text_message):
    mailer = AmazonSESMailer(
        aws_access_key_id="fake_access_key",
        aws_secret_access_key="fake_secret_key",
        region_name="us-east-1",
        return_email="return@example.com",
    )

    mailer.client = MagicMock()
    response = {"MessageId": "fake_message_id"}
    mailer.client.send_email.return_value = response

    responses = mailer.send_emails(text_message)

    expected_data = {
        "Source": "from@example.com",
        "Destination": {
            "ToAddresses": ["to@example.com"],
            "CcAddresses": ["cc1@example.com", "cc2@example.com"],
            "BccAddresses": ["bcc@example.com"],
        },
        "Message": {
            "Subject": {"Data": "Test Subject", "Charset": "utf-8"},
            "Body": {
                "Text": {"Data": "Test Body", "Charset": "utf-8"},
            },
        },
        "ReplyToAddresses": ["reply@example.com"],
        "ReturnPath": "return@example.com",
        "Tags": [
            {"Name": "tag1", "Value": "value1"},
            {"Name": "tag2", "Value": "value2"},
        ],
    }

    assert len(responses) == 1
    assert responses[0] == response
    mailer.client.send_email.assert_called_with(**expected_data)


def test_amazon_ses_mailer_send_html_emails(html_message):
    mailer = AmazonSESMailer(
        aws_access_key_id="fake_access_key",
        aws_secret_access_key="fake_secret_key",
        region_name="us-east-1",
        return_email="return@example.com",
    )

    mailer.client = MagicMock()
    response = {"MessageId": "fake_message_id"}
    mailer.client.send_email.return_value = response

    mailer.send_emails(html_message)

    expected_data = {
        "Source": "from@example.com",
        "Destination": {
            "ToAddresses": ["to@example.com"],
            "CcAddresses": ["cc1@example.com", "cc2@example.com"],
            "BccAddresses": ["bcc@example.com"],
        },
        "Message": {
            "Subject": {"Data": "Test Subject", "Charset": "utf-8"},
            "Body": {
                "Html": {"Data": "Test Body", "Charset": "utf-8"}
            },
        },
        "ReplyToAddresses": ["reply@example.com"],
        "ReturnPath": "return@example.com",
        "Tags": [
            {"Name": "tag1", "Value": "value1"},
            {"Name": "tag2", "Value": "value2"},
        ],
    }

    mailer.client.send_email.assert_called_with(**expected_data)


def test_amazon_ses2_mailer_send_text_emails(text_message):
    mailer = AmazonSES2Mailer(
        aws_access_key_id="fake_access_key",
        aws_secret_access_key="fake_secret_key",
        region_name="us-east-1",
        return_email="return@example.com",
    )

    mailer.client = MagicMock()
    response = {"MessageId": "fake_message_id"}
    mailer.client.send_email.return_value = response

    responses = mailer.send_emails(text_message)

    expected_data = {
        "FromEmailAddress": "from@example.com",
        "Destination": {
            "ToAddresses": ["to@example.com"],
            "CcAddresses": ["cc1@example.com", "cc2@example.com"],
            "BccAddresses": ["bcc@example.com"],
        },
        "ReplyToAddresses": ["reply@example.com"],
        "FeedbackForwardingEmailAddress": "return@example.com",
        "Content": {
            "Simple": {
                "Subject": {"Data": "Test Subject", "Charset": "utf-8"},
                "Body": {
                    "Text": {"Data": "Test Body", "Charset": "utf-8"},
                },
                "Headers": [
                    {"Name": "header1", "Value": "value1"},
                    {"Name": "header2", "Value": "value2"},
                ],
            }
        },
        "EmailTags": [
            {"Name": "tag1", "Value": "value1"},
            {"Name": "tag2", "Value": "value2"},
        ],
    }

    assert len(responses) == 1
    assert responses[0] == response
    mailer.client.send_email.assert_called_with(**expected_data)



def test_amazon_ses2_mailer_send_html_emails(html_message):
    mailer = AmazonSES2Mailer(
        aws_access_key_id="fake_access_key",
        aws_secret_access_key="fake_secret_key",
        region_name="us-east-1",
        return_email="return@example.com",
    )

    mailer.client = MagicMock()
    response = {"MessageId": "fake_message_id"}
    mailer.client.send_email.return_value = response

    mailer.send_emails(html_message)

    expected_data = {
        "FromEmailAddress": "from@example.com",
        "Destination": {
            "ToAddresses": ["to@example.com"],
            "CcAddresses": ["cc1@example.com", "cc2@example.com"],
            "BccAddresses": ["bcc@example.com"],
        },
        "ReplyToAddresses": ["reply@example.com"],
        "FeedbackForwardingEmailAddress": "return@example.com",
        "Content": {
            "Simple": {
                "Subject": {"Data": "Test Subject", "Charset": "utf-8"},
                "Body": {
                    "Html": {"Data": "Test Body", "Charset": "utf-8"},
                },
                "Headers": [
                    {"Name": "header1", "Value": "value1"},
                    {"Name": "header2", "Value": "value2"},
                ],
            }
        },
        "EmailTags": [
            {"Name": "tag1", "Value": "value1"},
            {"Name": "tag2", "Value": "value2"},
        ],
    }

    mailer.client.send_email.assert_called_with(**expected_data)
