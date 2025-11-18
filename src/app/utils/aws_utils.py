from io import BytesIO
import boto3
import cv2
import numpy as np
from PIL import Image
from app.config.config import Config
from app.utils.image_utils import image_preprocess
class AWSService:
    """
    AWS Service class to handle interactions with AWS services like S3 and AWS Textract.
    """

    def __init__(self):
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY,
            aws_secret_access_key=Config.AWS_SECRET_KEY,
            region_name=Config.REGION_NAME
        )
        self.bucket_name = Config.S3_BUCKET_NAME
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
        return self.s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': key,
                'ResponseContentDisposition': f'attachment; filename="{filename}"'
            },
            ExpiresIn=expiration
        )
    
    def textract_to_items(self, response, img_width: int, img_height: int) -> list:
        items = []
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                text = block.get('Text', '').strip()
                bbox = block.get('Geometry', {}).get('BoundingBox', {})
                left = bbox.get("Left", 0.0)
                top = bbox.get("Top", 0.0)
                width = bbox.get("Width", 0.0)
                height = bbox.get("Height", 0.0)
                if text and bbox and width > 0 and height > 0:
                    center_x = (left + width / 2.0) * img_width
                    center_y = (top + height / 2.0) * img_height
                    items.append({
                        'text': text,
                        'confidence': block.get('Confidence', 0),
                        'bounding_box': {
                            'x1': int(left * img_width),
                            'y1': int(top * img_height),
                            'x2': int((left + width) * img_width),
                            'y2': int((top + height) * img_height)
                        },
                        'center_x': int(round(center_x)),
                        'center_y': int(round(center_y))
                    })
        return items

    def extract_text_from_image(self, image):
        """
        Converts the image at image to text using aws textract.
        Args:
            image: cv2 image.
        Returns:
            list: List of detected text elements and corresponding normalized bounding boxes.
        """

        #image = image_preprocess(image)
        image_width = image.shape[1]
        image_height = image.shape[0]

        if isinstance(image, np.ndarray):
            image = np.ascontiguousarray(image)
            ok, buf = cv2.imencode('.jpg', image)
            if not ok:
                raise RuntimeError("Failed to encode image for OCR API")
            image_bytes = buf.tobytes()
        elif isinstance(image, bytes):
            image_bytes = image
        elif isinstance(image, Image.Image):
            bio = BytesIO()
            image.save(bio, format='JPEG')
            image_bytes = bio.getvalue()
        else:
            # fallback: try reading imgPath if provided
            raise RuntimeError("No image bytes available for OCR API call")

        response = self.textract.detect_document_text(
            Document={'Bytes': image_bytes}
        )
        
        result = self.textract_to_items(response, image_width, image_height)
    
        return result