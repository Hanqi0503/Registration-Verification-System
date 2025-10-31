import boto3
from app.config.config import Config
from app.utils.image_utils import fetch_image_bytes
class AWSService:
    """
    AWS Service class to handle interactions with AWS services like S3 and AWS Textract.
    """

    def __init__(self):
        # Initialize clients only when enabled to avoid accidental external usage
        self.s3 = None
        self.bucket_name = Config.S3_BUCKET_NAME
        self.textract = None

        if getattr(Config, 'USE_S3', False):
            self.s3 = boto3.client(
                's3',
                aws_access_key_id=Config.AWS_ACCESS_KEY,
                aws_secret_access_key=Config.AWS_SECRET_KEY,
                region_name=Config.REGION_NAME
            )

        if getattr(Config, 'USE_EXTERNAL_OCR', False):
            self.textract = boto3.client(
                'textract',
                aws_access_key_id=Config.AWS_ACCESS_KEY,
                aws_secret_access_key=Config.AWS_SECRET_KEY,
                region_name=Config.REGION_NAME
            )

    def upload_file(self, local_path, s3_key):
        """
        Upload a local file from disk to S3.

        Args:
            local_path (str): Path to the local file to upload.
            s3_key (str): The destination key (path) inside the S3 bucket.

        Returns:
            bool: True if upload was successful, False otherwise.
        """
        if not self.s3:
            print("S3 is not enabled in Config.USE_S3")
            return False
        try:
            self.s3.upload_file(local_path, self.bucket_name, s3_key)
        except Exception as e:
            print(f"Error uploading to S3: {e}")
            return False
        return True
    
    def upload_object(self, file_obj, s3_key, mime_type):
        """
        Upload an in-memory file-like object (e.g., BytesIO) to S3.

        Args:
            file_obj (BytesIO): The in-memory file-like object to upload.
            s3_key (str): The destination key (path) inside the S3 bucket.
            mime_type (str): MIME type (Content-Type) of the uploaded object.

        Returns:
            bool: True if upload was successful, False otherwise.
        """
        if not self.s3:
            print("S3 is not enabled in Config.USE_S3")
            return False
        try:
            self.s3.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': mime_type}
            )
        except Exception as e:
            print(f"Error uploading file object to S3: {e}")
            return False
        return True

    def download_file(self, s3_url):
        """
        Downloads a file from S3.

        Args:
        except Exception as e:
            print(f"Error uploading file object to S3: {e}")
            return False
        return True
    
        """
        if not self.s3:
            raise RuntimeError("S3 is not enabled in Config.USE_S3")
        s3_bucket = s3_url.split('/')[2]
        file_key = '/'.join(s3_url.split('/')[3:])
        response = self.s3.get_object(Bucket=s3_bucket, Key=file_key)
        return response['Body'].read()

    def generate_presigned_url(self, key, filename, expiration=3600):
        """
        Generate a presigned URL to share an S3 object.
        Args:
            key (str): S3 object key.
            filename (str): Suggested filename for download.
            expiration (int): Time in seconds for the presigned URL to remain valid.
        Returns:
            str: Presigned URL as a string. If error, returns None.
        """
        if not self.s3:
            raise RuntimeError("S3 is not enabled in Config.USE_S3")
        return self.s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': key,
                'ResponseContentDisposition': f'attachment; filename="{filename}"'
            },
            ExpiresIn=expiration
        )

    def extract_text_from_image(self, imgURL):
        """
        Converts the image at img_url to text using aws textract.
        Args:
            imgURL (str): URL of the image to process.
        Returns:
            list: List of detected text elements.
        """

        if not self.textract:
            raise RuntimeError("AWS Textract is not enabled in Config.USE_EXTERNAL_OCR")
        image = fetch_image_bytes(imgURL)
        response = self.textract.detect_document_text(
            Document={'Bytes': image}
        )
        result = [{'text': word} for block in response['Blocks'] if block['BlockType'] == 'LINE'
                for word in block.get('Text', '').split()]
        return result

    def extract_text_from_bytes(self, image_bytes: bytes):
        """Run Textract on in-memory image bytes and return an ordered list of LINE texts."""
        if not self.textract:
            raise RuntimeError("AWS Textract is not enabled in Config.USE_EXTERNAL_OCR")
        response = self.textract.detect_document_text(Document={'Bytes': image_bytes})
        lines = [block.get('Text', '') for block in response.get('Blocks', []) if block.get('BlockType') == 'LINE']
        return lines