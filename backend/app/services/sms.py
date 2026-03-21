"""SMS service using AWS SNS for OTP delivery."""
import boto3
from app.core.config import settings

_sns = boto3.client("sns", region_name=settings.AWS_REGION)


async def send_otp_sms(phone_e164: str, otp: str) -> None:
    """Send a 6-digit OTP via AWS SNS SMS."""
    _sns.publish(
        PhoneNumber=phone_e164,
        Message=f"Your JobAimer verification code is: {otp}\nExpires in 10 minutes. Do not share this code.",
        MessageAttributes={
            "AWS.SNS.SMS.SenderID": {"DataType": "String", "StringValue": "JobAimer"},
            "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"},
        },
    )
