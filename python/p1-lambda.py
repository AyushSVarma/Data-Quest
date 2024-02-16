#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from io import TextIOWrapper, BytesIO
from botocore.exceptions import ClientError
import requests
import boto3
from bs4 import BeautifulSoup
import json

s3_client = boto3.client("s3")
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)
bls_headers = {  # simplify header?
    "Sec-CH-UA": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": "Windows",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def lambda_handler(event, context):

    session = requests.Session()

    url = "https://download.bls.gov/pub/time.series/pr/"

    response = session.get(url, headers=bls_headers)
    soup = BeautifulSoup(response.content, "html.parser")
    links = soup.find_all("a")  # Find all elements with the tag <a>
    bucket_name = "ayush-data-quest-tf"
    keys = []
    last_modified_dates = {}
    last_etags = {}

    keys = check_last_modified_date_helper(
        s3_client, bucket_name, "last_modified_dates.txt", links, session
    )
    delete_outdated_files(keys, bucket_name)
    pt2_download(bucket_name)

    return "Function Success!!"


def pt2_download(bucket_name):
    req = requests.get(
        "https://datausa.io/api/data?drilldowns=Nation&measures=Population"
    )

    json_data = req.json()
    data_part = json_data["data"]

    json_str = json.dumps(data_part, indent=4)
    s3_client.put_object(Bucket=bucket_name, Key="api_output.json", Body=json_str)


def delete_outdated_files(keys, bucket_name):
    if keys:
        try:
            paginator = s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(Bucket=bucket_name)
            for page in page_iterator:
                if "Contents" in page:  # Check if the page has any contents
                    for obj in page["Contents"]:
                        key = obj["Key"]
                        if key in keys:
                            print(f"Match found: {key}")
                        else:
                            if (
                                key != "last_modified_dates.txt"
                                and key != "last_etags.txt"
                                and key != "api_output.json"
                            ):
                                s3_client.delete_object(Bucket=bucket_name, Key=key)
                                print(f"{key} has been deleted")
        except Exception as e:
            print(f"An error occurred: {e}")
            return "done w/ fail.."


def save_dates_to_s3(s3_client, bucket_name, last_modified_dates):
    body_content = "\n".join(
        f"{url}: {date}" for url, date in last_modified_dates.items()
    )
    body_bytes = body_content.encode("utf-8")
    s3_client.put_object(
        Bucket=bucket_name, Key="last_modified_dates.txt", Body=body_bytes
    )


def fetch_current_dates(links, session):
    logger.info("fetching current dates..")
    keys = []
    last_modified_dates = {}
    for link in links:
        if "Parent Directory" not in link.string:
            keys.append(link.string)
            response_metadata_ = session.head(
                f"https://download.bls.gov/pub/time.series/pr/{link.string}",
                headers=bls_headers,
            )
            if "Last-Modified" in response_metadata_.headers:
                last_modified = response_metadata_.headers["Last-Modified"]
                last_modified_dates[link.string] = last_modified
            # body_content = "\n".join(f"{url}: {date}" for url, date in last_modified_dates.items())
    return last_modified_dates, keys


def check_last_modified_date_helper(s3_client, bucket_name, object_key, links, session):
    file_exists = None
    try:
        # Attempt to retrieve the object's metadata

        s3_client.head_object(Bucket=bucket_name, Key=object_key)
        file_exists = True
    except ClientError as e:
        # If a ClientError is caught, set file_exists to False

        file_exists = False
    if file_exists:
        logger.info(f"The file '{object_key}' exists in '{bucket_name}'.")
    else:
        logger.info(f"The file '{object_key}' does not exist in '{bucket_name}'.")
        # download here..

        for link in links:
            if "Parent Directory" not in link.string:
                response_url = session.get(
                    f"https://download.bls.gov/pub/time.series/pr/{link.string}",
                    headers=bls_headers,
                )
                s3_client.put_object(
                    Bucket=bucket_name, Key=link.string, Body=response_url.content
                )
        dates, _ = fetch_current_dates(links, session)
        save_dates_to_s3(s3_client, bucket_name, dates)
        return
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    file_content = response["Body"].read().decode("utf-8")
    file_lines = file_content.splitlines()
    file_dates = {line.split(": ")[0]: line.split(": ")[1] for line in file_lines}

    current_dates, full_keys = fetch_current_dates(links, session)
    for url, file_date in file_dates.items():
        current_date = current_dates.get(url)
        if current_date and current_date != file_date:
            print(
                f"Date mismatch for {url}! File date: {file_date}, Current date: {current_date}"
            )
            response_url = session.get(
                f"https://download.bls.gov/pub/time.series/pr/{url}",
                headers=bls_headers,
            )
            s3_client.put_object(Bucket=bucket_name, Key=url, Body=response_url.content)
    return full_keys
