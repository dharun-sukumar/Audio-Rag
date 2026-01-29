import boto3
from app.core.config import ENDPOINT, ACCESS_KEY, SECRET_KEY, BUCKET

session = boto3.session.Session()

s3 = session.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

def generate_signed_upload_url(
    key: str,
    content_type: str,
    expires_in: int = 300
) -> str:
    """
    Signed PUT URL for direct browser upload
    """
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )

def generate_signed_get_url(
    key: str,
    expires_in: int = 3600
) -> str:
    """
    Signed GET URL for reading the object
    """
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
        },
        ExpiresIn=expires_in,
    )
