import os
import zipfile
import boto3
import hashlib


lambda_client = boto3.client('lambda')
s3_client = boto3.client('s3')


def hash_file(path):
    if not os.path.exists(path):
        return 0

    with open(path, 'rb') as file:
        data = file.read()
        return hashlib.md5(data).hexdigest()


def zip_directory(directory_path, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(directory_path):
            for file in files:
                if ".py" not in file:
                    continue

                file_path = os.path.join(root, file)
                zipf.write(file_path, arcname=os.path.relpath(file_path, directory_path))


def update_lambda_function(function_name, directory_path):
    zip_path_current = os.path.join(directory_path, "lambda_function_current.zip")
    zip_path_previous = os.path.join(directory_path, "lambda_function_previous.zip")

    if os.path.exists(zip_path_current):
        os.rename(zip_path_current, zip_path_previous)

    print(f"Create zip archive for lambda function: {function_name}")
    zip_directory(directory_path, zip_path_current)

    if hash_file(zip_path_current) == hash_file(zip_path_previous):
        print("Code wasn't change - skip uploading\n")
        return
    
    with open(zip_path_current, 'rb') as f:
        zipped_code = f.read()

    response = lambda_client.update_function_code(
        FunctionName=function_name,
        ZipFile=zipped_code,
        Publish=True,
    )

    print(f"Lambda function was updated\n")


def update_s3_file(bucket, s3_file_path, local_file_path):
    print(f"Check updates for file: {s3_file_path}")

    s3_response = s3_client.get_object(
        Bucket=bucket,
        Key=s3_file_path
    )
    s3_file_content = s3_response.get('Body').read()

    if hashlib.md5(s3_file_content).hexdigest() == hash_file(local_file_path):
        print("File wasn't change - skip uploading\n")
        return
    
    with open(local_file_path, 'rb') as file:
        data = file.read()
        s3_client.put_object(Bucket=bucket, Key=s3_file_path, Body=data, ContentType='text/html')
        print(f"File was updated\n")


update_lambda_function('zkp-club-avatar-uploader', '/home/akovalko/Desktop/zkp-club/avatar-uploader')
update_lambda_function('zkp-club-rest-api',        '/home/akovalko/Desktop/zkp-club/rest-api')
update_lambda_function('zkp-club-telegram-bot',    '/home/akovalko/Desktop/zkp-club/telegram-bot')


update_s3_file('zkp-club-telegram-bot', 'pages/admission.html',    '/home/akovalko/Desktop/zkp-club/pages/admission.html')
update_s3_file('zkp-club-telegram-bot', 'pages/applications.html', '/home/akovalko/Desktop/zkp-club/pages/applications.html')
update_s3_file('zkp-club-telegram-bot', 'pages/vote.html',         '/home/akovalko/Desktop/zkp-club/pages/vote.html')
