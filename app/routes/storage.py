import os
import boto3
from botocore.exceptions import ClientError
from flask import Blueprint, request
from werkzeug.utils import secure_filename
import uuid

from ..utils.responses import make_response
from ..utils.auth import jwt_required, admin_required

bp = Blueprint("storage", __name__)

# NCP Object Storage 설정
NCP_ACCESS_KEY = os.environ.get("NCP_ACCESS_KEY")
NCP_SECRET_KEY = os.environ.get("NCP_SECRET_KEY")
NCP_REGION = os.environ.get("NCP_REGION", "kr-standard")
NCP_ENDPOINT = os.environ.get("NCP_ENDPOINT", "https://kr.object.ncloudstorage.com")
NCP_BUCKET_NAME = os.environ.get("NCP_BUCKET_NAME")

# S3 클라이언트 생성 (NCP Object Storage는 S3 호환)
s3_client = boto3.client(
    's3',
    aws_access_key_id=NCP_ACCESS_KEY,
    aws_secret_access_key=NCP_SECRET_KEY,
    region_name=NCP_REGION,
    endpoint_url=NCP_ENDPOINT
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename):
    """허용된 파일 확장자인지 확인"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_file_to_ncp(file, folder_name="test"):
    """NCP Object Storage에 파일 업로드"""
    if not file or file.filename == '':
        return None, "파일이 선택되지 않았습니다"
    
    if not allowed_file(file.filename):
        return None, f"허용되지 않는 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # 파일 크기 체크
    file.seek(0, 2)  # 파일 끝으로 이동
    file_size = file.tell()
    file.seek(0)  # 파일 처음으로 되돌아가기
    
    if file_size > MAX_FILE_SIZE:
        return None, f"파일 크기가 너무 큽니다. 최대 {MAX_FILE_SIZE // (1024*1024)}MB"
    
    # 안전한 파일명 생성
    filename = secure_filename(file.filename)
    file_extension = filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
    object_key = f"{folder_name}/{unique_filename}"
    
    try:
        # NCP Object Storage에 업로드
        s3_client.upload_fileobj(
            file,
            NCP_BUCKET_NAME,
            object_key,
            ExtraArgs={
                'ContentType': file.content_type or 'application/octet-stream'
            }
        )
        
        # 업로드된 파일의 URL 생성
        file_url = f"{NCP_ENDPOINT}/{NCP_BUCKET_NAME}/{object_key}"
        return file_url, None
        
    except ClientError as e:
        return None, f"파일 업로드 실패: {str(e)}"
    except Exception as e:
        return None, f"알 수 없는 오류: {str(e)}"


@bp.route("/upload", methods=["POST"])
@jwt_required
def upload_file():
    """
    NCP Object Storage 파일 업로드
    ---
    tags:
      - Storage
    summary: NCP Object Storage 파일 업로드
    description: NCP Object Storage에 파일을 업로드합니다.
    security:
      - JWT: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: 업로드할 이미지 파일
      - in: formData
        name: folder
        type: string
        required: false
        description: 업로드할 폴더명 (기본값 test)
        default: test
    responses:
      200:
        description: 파일 업로드 성공
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "OK"
            data:
              type: object
              properties:
                file_url:
                  type: string
                  example: "https://kr.object.ncloudstorage.com/bucket-name/test/abc123.jpg"
                original_filename:
                  type: string
                  example: "photo.jpg"
                file_size:
                  type: integer
                  example: 1024000
                folder:
                  type: string
                  example: "test"
      400:
        description: 잘못된 요청
        schema:
          type: object
          properties:
            error:
              type: string
              example: "파일이 선택되지 않았습니다"
      401:
        description: 인증 실패
      500:
        description: 서버 설정 오류
        schema:
          type: object
          properties:
            error:
              type: string
              example: "NCP Object Storage 설정이 완료되지 않았습니다"
    """
    # NCP 설정 확인
    if not all([NCP_ACCESS_KEY, NCP_SECRET_KEY, NCP_BUCKET_NAME]):
        return make_response({
            "error": "NCP Object Storage 설정이 완료되지 않았습니다"
        }, 500)
    
    # 파일 확인
    if 'file' not in request.files:
        return make_response({"error": "파일이 업로드되지 않았습니다"}, 400)
    
    file = request.files['file']
    folder = request.form.get('folder', 'test')
    
    # 파일 업로드
    file_url, error = upload_file_to_ncp(file, folder)
    
    if error:
        return make_response({"error": error}, 400)
    
    return make_response({
        "file_url": file_url,
        "original_filename": file.filename,
        "file_size": file.content_length or 0,
        "folder": folder
    })


@bp.route("/files", methods=["GET"])
@admin_required
def list_files():
    """
    NCP Object Storage 파일 목록 조회
    ---
    tags:
      - Storage
    summary: NCP Object Storage 파일 목록 조회 (관리자)
    description: NCP Object Storage에 저장된 파일 목록을 조회합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: query
        name: folder
        type: string
        required: false
        description: 조회할 폴더명 (기본값 test)
        default: test
      - in: query
        name: limit
        type: integer
        required: false
        description: 조회할 파일 개수 (기본값 10)
        default: 10
    responses:
      200:
        description: 파일 목록 조회 성공
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "OK"
            data:
              type: object
              properties:
                files:
                  type: array
                  items:
                    type: object
                    properties:
                      key:
                        type: string
                        example: "test/abc123.jpg"
                      url:
                        type: string
                        example: "https://kr.object.ncloudstorage.com/bucket-name/test/abc123.jpg"
                      size:
                        type: integer
                        example: 1024000
                      last_modified:
                        type: string
                        example: "2025-01-01T12:00:00Z"
                folder:
                  type: string
                  example: "test"
                total_count:
                  type: integer
                  example: 5
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
      500:
        description: 서버 설정 오류
    """
    # NCP 설정 확인
    if not all([NCP_ACCESS_KEY, NCP_SECRET_KEY, NCP_BUCKET_NAME]):
        return make_response({
            "error": "NCP Object Storage 설정이 완료되지 않았습니다"
        }, 500)
    
    folder = request.args.get('folder', 'test')
    limit = int(request.args.get('limit', 10))
    
    try:
        # 파일 목록 조회
        response = s3_client.list_objects_v2(
            Bucket=NCP_BUCKET_NAME,
            Prefix=f"{folder}/",
            MaxKeys=limit
        )
        
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                file_url = f"{NCP_ENDPOINT}/{NCP_BUCKET_NAME}/{obj['Key']}"
                files.append({
                    "key": obj['Key'],
                    "url": file_url,
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'].isoformat()
                })
        
        return make_response({
            "files": files,
            "folder": folder,
            "total_count": len(files)
        })
        
    except ClientError as e:
        return make_response({"error": f"파일 목록 조회 실패: {str(e)}"}, 500)
    except Exception as e:
        return make_response({"error": f"알 수 없는 오류: {str(e)}"}, 500)


@bp.route("/files/<path:object_key>", methods=["DELETE"])
@admin_required
def delete_file(object_key):
    """
    NCP Object Storage 파일 삭제
    ---
    tags:
      - Storage
    summary: NCP Object Storage 파일 삭제 (관리자)
    description: NCP Object Storage에서 파일을 삭제합니다.
    security:
      - JWT: []
      - AdminHeader: []
    parameters:
      - in: path
        name: object_key
        type: string
        required: true
        description: 삭제할 파일의 object key (예. test/abc123.jpg)
    responses:
      200:
        description: 파일 삭제 성공
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "OK"
            data:
              type: object
              properties:
                deleted_key:
                  type: string
                  example: "test/abc123.jpg"
      401:
        description: 인증 실패
      403:
        description: 관리자 권한 필요
      404:
        description: 파일을 찾을 수 없음
      500:
        description: 서버 설정 오류
    """
    # NCP 설정 확인
    if not all([NCP_ACCESS_KEY, NCP_SECRET_KEY, NCP_BUCKET_NAME]):
        return make_response({
            "error": "NCP Object Storage 설정이 완료되지 않았습니다"
        }, 500)
    
    try:
        # 파일 존재 확인
        s3_client.head_object(Bucket=NCP_BUCKET_NAME, Key=object_key)
        
        # 파일 삭제
        s3_client.delete_object(Bucket=NCP_BUCKET_NAME, Key=object_key)
        
        return make_response({
            "deleted_key": object_key
        })
        
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return make_response({"error": "파일을 찾을 수 없습니다"}, 404)
        return make_response({"error": f"파일 삭제 실패: {str(e)}"}, 500)
    except Exception as e:
        return make_response({"error": f"알 수 없는 오류: {str(e)}"}, 500)
