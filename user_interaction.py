
from flask import Flask, render_template, request
import boto3
import pymysql
import json
import requests
import os
import uuid

app = Flask(__name__)


@app.route('/process_activity', methods=['POST'])
def activity_handler():

    file = request.files['file']

    if file.filename == '':
        return 'No selected file'
    file_path = os.path.join('.', file.filename)
    file.save(file_path)
    print(file_path)
    activity_uuid = uuid.uuid1()
    s3_status = store_image_to_s3(activity_uuid, file_path)
    user_name = request.form['username']
    caption_text = request.form['caption']
    message = "You post is in unknown STATE "

    if s3_status.get("status") == 200:

        bucket_name = s3_status.get("data").get("bucket_name")
        file_at_bucket = s3_status.get("data").get("file_name")
        print("file stored in bucket")
        store_data_to_rds(activity_uuid, user_name, caption_text, bucket_name, file_at_bucket)

        extracted_text_data = extract_image_text(bucket_name, file_at_bucket)
        print("data extraction completed")
        image_text_information = extract_text_info(extracted_text_data)

        caption_text_information = extract_text_info(caption_text)
        print("text analysis done")
        if image_text_information.get("sentiment_details").get("sentiment") == "negative" or caption_text_information.get("sentiment_details").get("sentiment") == "negative":

            uniques_entity_extracted = combine_text_image_entity(image_text_information, caption_text_information)
            negative_post_notification(activity_uuid, user_name, uniques_entity_extracted)
            message = "Your post has some negative sentiment. We have sent you an email notification."
            print("Email sent")

        else:

            message = "Your post is good to go!"

    os.remove(file_path)
    return render_template('message.html', message=message)


def store_image_to_s3(activity_uuid, image_path):

    response = {
        "status" : 400
    }
    try:
        s3 = boto3.client('s3')

        bucket_name = "articles-image"
        file_name_at_bucket = "uploaded_image/" + str(activity_uuid) + ".jpg"
        s3.upload_file(image_path, bucket_name, file_name_at_bucket)

        response = {
            "status" : 200,
            "data" : {
                "bucket_name" : bucket_name,
                "file_name" : file_name_at_bucket
            },
            "message" : "Image stored to S3",

        }

    except Exception as e:

        print(e)
        response = {
            "Status": 400,
            "message" : "Error occured : "+str(e)
        }

    return response

def store_data_to_rds(activity_uuid, user_name, caption_image, bucket_name, file_at_bucket):

    response = {
        "status" : 400
    }

    try:
        host = "user-information-table.c216sqc183hq.us-east-1.rds.amazonaws.com"
        port = 3306
        user = 'admin'
        password = 'password'

        # Connect to the database
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password
        )

        # Create a cursor object
        cursor = connection.cursor()

        query = f"""INSERT INTO `user-activity-information`.`activity_data`
                        (`activity_uuid`,
                        `user_name`,
                        `bucket_name`,
                        `file_ name`,
                        `user_text`)
                        VALUES
                        ({activity_uuid},
                        {user_name},
                        {bucket_name},
                        {file_at_bucket},
                        {caption_image});
                        """

        cursor.execute(query)
        connection.commit()

        # Close the cursor and connection
        cursor.close()
        connection.close()

        response = {
            "status": 200,
            "data": {
                "activity_uuid" : activity_uuid
            },
            "message": "Image stored to S3",
        }

    except Exception as e:

        response = {
            "Status": 400,
            "message": "Error occured : " + str(e)
        }

    return response


def extract_image_text(bucket_name, file_name):

    lambda_url = "https://kgmfmncipi3r4fag7jpwqbirfu0ylijp.lambda-url.us-east-1.on.aws/"
    request_data = {
            "bucket_name" : bucket_name,
            "file_name" : file_name
        }

    extracted_text = requests.post(lambda_url, json=request_data)
    text_data = extracted_text.text

    return text_data

def extract_text_info(extracted_text_data):

    lambda_url = "https://4gt3d5jnm3qrpqskpxezgywjju0dexxg.lambda-url.us-east-1.on.aws/"
    request_data = {
        "text_data" : extracted_text_data
    }

    extracted_info = requests.post(lambda_url, json=request_data)
    extracted_text_info = json.loads(extracted_info.text)

    return extracted_text_info

def negative_post_notification(uuid, user_name, uniques_entity_extracted):

    email_entity_data = ''
    for entity in uniques_entity_extracted:
        email_entity_data += "\tKey: " + entity["entity"]  + "  (Probable Type: "+entity["entity_type"] +")\n"

    email_body = f"There is negative post found on SocialMe! \nActivity UUID : {uuid}\nPosted By : {user_name}\nKeywords Found in Activity : \n{email_entity_data}"

    sns = boto3.client('sns',)
    response = sns.publish(
        TopicArn="arn:aws:sns:us-east-1:614826806011:negative-post-notification",
        Message=email_body,
        Subject='Activity Alert on SocialMe !!'
    )

def combine_text_image_entity(image_text_information, caption_text_information):

    entity_extracted = []
    entity_extracted.extend(image_text_information.get("entity_details"))
    entity_extracted.extend(caption_text_information.get("entity_details"))

    uniques_entity_extracted = []
    entity_value_only = []
    for entity in entity_extracted:
        current_entity = entity["entity"]
        if current_entity not in entity_value_only:
            entity_value_only.append(current_entity)
            uniques_entity_extracted.append(entity)
    return uniques_entity_extracted

@app.route('/image')
def index():
    return render_template('frontend_view.html')


@app.route('/upload', methods=['POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'

        file = request.files['file']

        if file.filename == '':
            return 'No selected file'
        file_path = os.path.join('.', file.filename)
        file.save(file_path)
        s3 = boto3.client('s3')
        bucket_name = "articles-image"
        file_name_at_bucket = "uploaded_image/" + str("test") + ".jpg"
        s3.upload_file(file_path, bucket_name, file_name_at_bucket)

    return 'Invalid request'

# Function to check if the file has an allowed extension (e.g., only images)
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.run(host="0.0.0.0" , port = 5002)
