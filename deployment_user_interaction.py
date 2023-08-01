
from flask import Flask, render_template, request
import boto3
import pymysql
import json
import requests
import os
import uuid

aws_access_key_id="AKIAY6JUIRL5VH35BTIW"
aws_secret_access_key="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"

# Getting dynamic instance parametters
with open('InstanceParameter.json', 'r') as jsonfile:
    # Reading from json file
    InstanceParameters = json.load(jsonfile)

APIGatewayURL = InstanceParameters.get("APIGateway").get("APIGatewayURL")
RDSParams = InstanceParameters.get("RDS")
HOSTNAME = RDSParams["HOSTNAME"]
PORT = RDSParams["PORT"]
USER = RDSParams["USER"]
PASSWORD = RDSParams["PASSWORD"]
SNSARN = InstanceParameters.get("SNS").get("SNSTopicARN")

SentimentLambdaURL = APIGatewayURL + "sentiment"
TextractLambdaURL = APIGatewayURL + "texttract"

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
    print("bucket operation doone")

    if s3_status.get("status") == 200:

        bucket_name = s3_status.get("data").get("bucket_name")
        file_at_bucket = s3_status.get("data").get("file_name")
        print("file stored in bucket")

        extracted_text_data = extract_image_text(bucket_name, file_at_bucket)
        print("data extraction completed")
        image_text_information = extract_text_info(extracted_text_data)

        caption_text_information = extract_text_info(caption_text)
        print("text analysis done")
        uniques_entity_extracted = combine_text_image_entity(image_text_information, caption_text_information)
        sentiment = image_text_information.get("sentiment_details").get("sentiment")
        if sentiment == "negative" or caption_text_information.get("sentiment_details").get("sentiment") == "negative":


            negative_post_notification(activity_uuid, user_name, uniques_entity_extracted)
            message = "Your post has some negative sentiment. We have sent you an email notification."
            print("Email sent")

        else:

            message = "Your post is good to go!"

        store_data_to_rds(activity_uuid, user_name, caption_text, bucket_name, file_at_bucket, sentiment, uniques_entity_extracted)

    os.remove(file_path)
    return render_template('message.html', message=message)


def store_image_to_s3(activity_uuid, image_path):

    response = {
        "status" : 400
    }
    try:
        s3 = boto3.client('s3',region_name="us-east-1",aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key)

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

def store_data_to_rds(activity_uuid, user_name, caption_image, bucket_name, file_at_bucket, sentiment, uniques_entity_extracted):

    response = {
        "status" : 400
    }

    try:

        # Connect to the database
        connection = pymysql.connect(
            host=HOSTNAME,
            port=PORT,
            user=USER,
            password=PASSWORD
        )

        # Create a cursor object
        cursor = connection.cursor()

        query = f"""INSERT INTO `user_activity_information`.`activity_data`
                                (`activity_id`,
                                `user_name`,
                                `bucket_name`,
                                `file_ name`,
                                `user_text`,
                                `sentiment`,
                                `user_text_info`)
                                VALUES
                                ("{activity_uuid}",
                                "{user_name}",
                                "{bucket_name}",
                                "{file_at_bucket}",
                                "{caption_image}",
                                "{sentiment}",
                                "{uniques_entity_extracted}");
                                """

        cursor.execute(query)
        connection.commit()

        # Close the cursor and connection
        cursor.close()
        connection.close()
        print("data entry done")
        response = {
            "status": 200,
            "data": {
                "activity_uuid" : activity_uuid
            },
            "message": "Image stored to S3",
        }

    except Exception as e:
        print("error in db  : "+str(e))
        response = {
            "Status": 400,
            "message": "Error occured : " + str(e)
        }

    return response


def extract_image_text(bucket_name, file_name):

    request_data = {
            "bucket_name" : bucket_name,
            "file_name" : file_name
        }

    extracted_text = requests.post(TextractLambdaURL, json=request_data)
    text_data = extracted_text.text
    extracted_image_text = json.loads(text_data)["body"]

    return extracted_image_text

def extract_text_info(extracted_text_data):

    request_data = {
        "text_data" : extracted_text_data
    }

    extracted_info = requests.post(SentimentLambdaURL, json=request_data)
    extracted_text_info = json.loads(extracted_info.text)
    text_info = json.loads(extracted_text_info["body"])

    return text_info

def negative_post_notification(uuid, user_name, uniques_entity_extracted):

    email_entity_data = ''
    for entity in uniques_entity_extracted:
        email_entity_data += "\tKey: " + entity["entity"]  + "  (Probable Type: "+entity["entity_type"] +")\n"

    email_body = f"There is negative post found on SocialMe! \nActivity UUID : {uuid}\nPosted By : {user_name}\nKeywords Found in Activity : \n{email_entity_data}"

    sns = boto3.client('sns', region_name="us-east-1", aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key)
    response = sns.publish(
        TopicArn=SNSARN,
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
        s3 = boto3.client('s3', region_name="us-east-1", aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key)
        bucket_name = "articles-image"
        file_name_at_bucket = "uploaded_image/" + str("test") + ".jpg"
        s3.upload_file(file_path, bucket_name, file_name_at_bucket)

    return 'Invalid request'

# Function to check if the file has an allowed extension (e.g., only images)
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.run(host="0.0.0.0" , port = 5003)
