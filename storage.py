import boto3
from config import ENDPOINT, BUCKET, ACCESS_KEY, SECRET_KEY

session = boto3.session.Session()

s3 = session.client(
    "s3",
    endpoint_url=ENDPOINT,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

def generate_signed_get_url(
    key: str,
    expires_in: int = 3600
) -> str:
    """
    Generate a temporary signed URL for GET access.
    """
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": BUCKET,
            "Key": key,
        },
        ExpiresIn=expires_in,
    )
