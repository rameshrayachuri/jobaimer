"""Notification utilities for SMS (SNS) and email (SES)."""
import boto3
from agent.config import settings


async def send_sms(phone: str, message: str) -> bool:
    try:
        sns = boto3.client("sns", region_name=settings.AWS_REGION)
        sns.publish(PhoneNumber=phone, Message=message,
                    MessageAttributes={"AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}})
        return True
    except Exception:
        return False


async def send_email(to: str, subject: str, body: str) -> bool:
    try:
        ses = boto3.client("ses", region_name=settings.AWS_REGION)
        ses.send_email(
            Source="noreply@jobaimer.com",
            Destination={"ToAddresses": [to]},
            Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}},
        )
        return True
    except Exception:
        return False
