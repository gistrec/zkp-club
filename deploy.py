import argparse
import boto3
import hashlib
import os
import requests
import zipfile


dynamodb_client = boto3.resource('dynamodb')
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


def update_function_code(function_name, directory_path):
    zip_path_current = os.path.join(directory_path, "lambda_function_current.zip")
    zip_path_previous = os.path.join(directory_path, "lambda_function_previous.zip")

    if os.path.exists(zip_path_current):
        os.rename(zip_path_current, zip_path_previous)

    print(f"Create zip archive for function: {function_name}")
    zip_directory(directory_path, zip_path_current)

    if hash_file(zip_path_current) == hash_file(zip_path_previous):
        print("Code wasn't change - skip uploading\n")
        return

    with open(zip_path_current, 'rb') as f:
        zipped_code = f.read()

    lambda_client.update_function_code(
        FunctionName=function_name,
        ZipFile=zipped_code,
        Publish=True,
    )
    print(f"Function was updated\n")


def update_functions_layer(layer_name, layer_arn, layer_version, functions):
    updated_layer_name = f"{layer_arn}:{layer_version}"

    for function_name in functions:
        layer_arns = [updated_layer_name]

        response = lambda_client.get_function_configuration(FunctionName=function_name)
        for current_layer in response["Layers"]:
            if layer_name not in current_layer["Arn"]:
                layer_arns.append(current_layer["Arn"])

        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Layers=layer_arns,
        )


def update_layer_code(layer_name, directory_path, functions):
    library_path = os.path.join(directory_path, "python")

    zip_path_current = os.path.join(directory_path, "lambda_layer_current.zip")
    zip_path_previous = os.path.join(directory_path, "lambda_layer_previous.zip")

    if os.path.exists(zip_path_current):
        os.rename(zip_path_current, zip_path_previous)

    print(f"Create zip archive for layer: {layer_name}")
    zip_directory(library_path, zip_path_current)

    if hash_file(zip_path_current) == hash_file(zip_path_previous):
        print("Code wasn't change - skip uploading\n")
        return
    
    with open(zip_path_current, 'rb') as f:
        zipped_code = f.read()

    response = lambda_client.publish_layer_version(
        LayerName=layer_name,
        Content={
            "ZipFile": zipped_code
        },
        CompatibleRuntimes=["python3.6", "python3.7", "python3.8", "python3.9", "python3.10", "python3.11"],
        CompatibleArchitectures=["x86_64"]
    )
    print("Layer was uploaded\n")

    update_functions_layer(layer_name, response["LayerArn"], response["Version"], functions)
    lambda_client.delete_layer_version(
        LayerName=layer_name,
        VersionNumber=(response["Version"] - 1)
    )


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



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set-webhook", action="store_true")
    parser.add_argument("--erase-database", action="store_true")
    args = parser.parse_args()

    update_function_code('zkp-club-avatar-uploader', '/home/akovalko/Desktop/zkp-club/avatar-uploader')
    update_function_code('zkp-club-rest-api',        '/home/akovalko/Desktop/zkp-club/rest-api')
    update_function_code('zkp-club-telegram-bot',    '/home/akovalko/Desktop/zkp-club/telegram-bot')

    update_s3_file('zkp-club-telegram-bot', 'pages/admission.html',    '/home/akovalko/Desktop/zkp-club/pages/admission.html')
    update_s3_file('zkp-club-telegram-bot', 'pages/applications.html', '/home/akovalko/Desktop/zkp-club/pages/applications.html')
    update_s3_file('zkp-club-telegram-bot', 'pages/vote.html',         '/home/akovalko/Desktop/zkp-club/pages/vote.html')

    lambda_function = ['zkp-club-avatar-uploader', 'zkp-club-rest-api', 'zkp-club-telegram-bot']
    update_layer_code('zkp-club-utils', '/home/akovalko/Desktop/zkp-club/layer-utils/', lambda_function)
    update_layer_code('zkp-club-python', '/home/akovalko/Desktop/zkp-club/layer-python/', lambda_function)

    if args.set_webhook:
        token = os.getenv('TELEGRAM_TOKEN')
        callback_url = "https://id94y26uyi.execute-api.eu-central-1.amazonaws.com/production/zkp-club-telegram-bot"

        print("Setting up Telegram WebHook")
        response = requests.get(f"https://api.telegram.org/bot{token}/setWebHook?url={callback_url}", timeout=5)
        response.raise_for_status()
        print("Done\n")

    if args.erase_database:
        print("Erasing DynamoDB table")

        table = dynamodb_client.Table("zkp-club-telegram-bot")
        scan = table.scan()

        with table.batch_writer() as batch:
            for item in scan['Items']:
                batch.delete_item({
                    "user_id": item["user_id"]
                })
        print("Done\n")


main()