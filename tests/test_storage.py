import pytest
import io
from unittest.mock import patch, MagicMock

from app import create_app
from app.db import get_db
from tests.test_helpers import get_auth_headers, get_test_jwt_token, get_admin_headers, get_admin_jwt_token


@pytest.fixture
def app():
    app = create_app(
        {"TESTING": True}
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_user(app):
    with app.app_context():
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (kakao_id, username, email, profile_image_url) VALUES (%s, %s, %s, %s) RETURNING id",
                ("test_kakao_id", "testuser", "test@example.com", "https://k.kakaocdn.net/dn/test.jpg"),
            )
            return cur.fetchone()["id"]


def test_storage_upload_success(client, test_user):
    """스토리지 업로드 성공 테스트"""
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    with patch('boto3.client') as mock_boto3:
        # Mock S3 client 설정
        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3
        mock_s3.upload_fileobj.return_value = None
        
        # 파일 업로드 테스트
        res = client.post(
            "/storage/upload",
            data={
                'file': (open(__file__, 'rb'), 'test_file.jpg'),
                'folder': 'test_folder'
            },
            headers=user_headers,
            content_type='multipart/form-data'
        )
        
        assert res.status_code == 200
        data = res.get_json()["data"][0]
        assert "url" in data
        assert "file_name" in data
        assert mock_s3.upload_fileobj.called


def test_storage_upload_missing_file(client, test_user):
    """파일 없이 업로드 시도 테스트"""
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    res = client.post(
        "/storage/upload",
        data={'folder': 'test_folder'},
        headers=user_headers,
        content_type='multipart/form-data'
    )
    
    assert res.status_code == 400
    assert "No file provided" in res.get_json()["message"]


def test_storage_upload_auth_required(client):
    """인증 없이 업로드 시도 테스트"""
    res = client.post(
        "/storage/upload",
        data={
            'file': (open(__file__, 'rb'), 'test_file.jpg'),
            'folder': 'test_folder'
        },
        content_type='multipart/form-data'
    )
    
    assert res.status_code == 401


def test_storage_list_files(client, test_user):
    """스토리지 파일 목록 조회 테스트"""
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    with patch('boto3.client') as mock_boto3:
        # Mock S3 client 설정
        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3
        
        # Mock list_objects_v2 응답
        mock_s3.list_objects_v2.return_value = {
            'Contents': [
                {
                    'Key': 'test_folder/test_file1.jpg',
                    'Size': 1024,
                    'LastModified': '2025-07-09T23:00:00Z'
                },
                {
                    'Key': 'test_folder/test_file2.jpg',
                    'Size': 2048,
                    'LastModified': '2025-07-09T23:01:00Z'
                }
            ]
        }
        
        res = client.get(
            "/storage/files?folder=test_folder",
            headers=user_headers
        )
        
        assert res.status_code == 200
        data = res.get_json()["data"]
        assert len(data) == 2
        assert mock_s3.list_objects_v2.called


def test_storage_delete_file_success(client, test_user):
    """파일 삭제 성공 테스트"""
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    with patch('boto3.client') as mock_boto3:
        # Mock S3 client 설정
        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3
        mock_s3.delete_object.return_value = {}
        
        res = client.delete(
            "/storage/files/test_folder/test_file.jpg",
            headers=user_headers
        )
        
        assert res.status_code == 200
        assert "삭제되었습니다" in res.get_json()["message"]
        assert mock_s3.delete_object.called


def test_storage_delete_file_auth_required(client):
    """인증 없이 파일 삭제 시도 테스트"""
    res = client.delete("/storage/files/test_folder/test_file.jpg")
    assert res.status_code == 401


def test_storage_upload_with_boto3_error(client, test_user):
    """S3 업로드 중 에러 발생 테스트"""
    user_headers = get_auth_headers(get_test_jwt_token(test_user, "testuser", "test@example.com"))
    
    with patch('boto3.client') as mock_boto3:
        # Mock S3 client 설정
        mock_s3 = MagicMock()
        mock_boto3.return_value = mock_s3
        mock_s3.upload_fileobj.side_effect = Exception("S3 Upload Error")
        
        res = client.post(
            "/storage/upload",
            data={
                'file': (open(__file__, 'rb'), 'test_file.jpg'),
                'folder': 'test_folder'
            },
            headers=user_headers,
            content_type='multipart/form-data'
        )
        
        assert res.status_code == 500
        assert "Upload failed" in res.get_json()["message"]


def test_storage_file_list_auth_required(client):
    """인증 없이 파일 목록 조회 시도 테스트"""
    res = client.get("/storage/files")
    assert res.status_code == 401
