import boto3
import pymysql
import json
import time
# Code to get API Gateway

aws_access_key_id="AKIAY6JUIRL5VH35BTIW"
aws_secret_access_key="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"


client = boto3.client('secretsmanager', region_name="us-east-1", aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key)
APIGatewayURL = client.get_secret_value(SecretId="APIGatewayURL")["SecretString"]

# Code to get RDS info of new instance
client = boto3.client('rds', region_name="us-east-1", aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key)
response = client.describe_db_instances()
for db_instance in response['DBInstances']:
    db_instance_name = db_instance['DBInstanceIdentifier']
    print(db_instance_name)
    if db_instance_name == "userdatadb":
        print(db_instance)
        HOSTNAME = db_instance["Endpoint"]["Address"]
        PORT = db_instance["Endpoint"]["Port"]
        USER = "admin"
        PASSWORD = "password"

client = boto3.client('sns', region_name='us-east-1', aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key)
response = client.list_topics()

for each_reg in response['Topics']:
        if each_reg['TopicArn'].split(":")[-1] == "negative-alert":
                SNSTopicARN = each_reg['TopicArn']

def create_db():
    connection = pymysql.connect(
        host=HOSTNAME,
        port=PORT,
        user=USER,
        password=PASSWORD
    )

    # Create a cursor object
    cursor = connection.cursor()
    create_db_query = "CREATE DATABASE user-activity-information;"
    cursor.execute(create_db_query)
    connection.commit()

    query = f"""CREATE TABLE `user-activity-information`.`activity_data` (
						  `activity_id` INT NOT NULL AUTO_INCREMENT,
						  `user_name` VARCHAR(45) NOT NULL,
						  `bucket_name` VARCHAR(45) NULL,
						  `file_ name` VARCHAR(45) NULL,
						  `user_text` VARCHAR(45) NULL,
						  `sentiment` VARCHAR(45) NULL,
						  `user_text_info` VARCHAR(45) NULL,
						  PRIMARY KEY (`activity_id`));
                            """

    cursor.execute(query)
    connection.commit()

create_db()

parameter_json = {
    "APIGateway" : {
        "APIGatewayURL" : APIGatewayURL
    },
    "RDS" : {
        "HOSTNAME" : HOSTNAME,
        "PORT" : PORT,
        "USER" : USER,
        "PASSWORD" :PASSWORD
    },
    "SNS" : {
        "SNSTopicARN" : SNSTopicARN
    }
}

json_object = json.dumps(parameter_json, indent=4)
with open("InstanceParameter.json", "w") as outfile:
    outfile.write(json_object)
