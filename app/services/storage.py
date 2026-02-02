import boto3
import json
from typing import Dict, Any
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

def upload_json_to_storage(
    key: str,
    data: Dict[Any, Any]
) -> str:
    """
    Upload JSON data to object storage
    
    Args:
        key: The S3 object key (path) where the JSON will be stored
        data: Dictionary to be stored as JSON
        
    Returns:
        The object key where the data was stored
    """
    json_bytes = json.dumps(data, indent=2).encode('utf-8')
    
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json_bytes,
        ContentType='application/json'
    )
    
    return key

def download_json_from_storage(key: str) -> Dict[Any, Any]:
    """
    Download and parse JSON data from object storage
    
    Args:
        key: The S3 object key to retrieve
        
    Returns:
        Parsed JSON data as a dictionary
    """
    response = s3.get_object(
        Bucket=BUCKET,
        Key=key
    )
    
    json_data = json.loads(response['Body'].read().decode('utf-8'))
    return json_data

def delete_from_storage(key: str) -> bool:
    """
    Delete an object from storage
    
    Args:
        key: The S3 object key to delete
        
    Returns:
        True if deletion was successful
    """
    try:
        s3.delete_object(
            Bucket=BUCKET,
            Key=key
        )
        return True
    except Exception as e:
        # Log error but don't fail if object doesn't exist
        print(f"Warning: Failed to delete {key}: {str(e)}")
        return False
