import logging
import pandas as pd
import boto3
from io import BytesIO
logger = logging.getLogger()
logger.setLevel(logging.INFO) 
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    bucket_name = 'ayush-data-quest-tf'
    file_key = 'api_output.json'
    csv_file_key = "pr.data.0.Current"
    # Get the JSON file content from S3
    response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
    json_content = response['Body'].read()

    # Load the JSON content into a pandas DataFrame
    df_json = pd.read_json(BytesIO(json_content))
    csv_response = s3_client.get_object(Bucket=bucket_name, Key=csv_file_key)
    csv_content = csv_response['Body'].read()
    
    # Load the CSV content into a pandas DataFrame with tab separator
    df_csv = pd.read_csv(BytesIO(csv_content), sep='\t')
    
    df_json.columns = df_json.columns.str.lower()
    df_csv.columns = df_csv.columns.str.strip()
    logger.info(df_json.iloc[[3,4,5,6,7,8]]["population"].mean())
    logger.info(df_json.iloc[[3,4,5,6,7,8]]["population"].std())
    yearly_sums = df_csv.groupby(['series_id', 'year'])['value'].sum().reset_index()

    indices = (yearly_sums.groupby('series_id')['value']).idxmax()
    best_years = yearly_sums.loc[indices].reset_index()
    best_years_sorted = best_years.sort_values(by='value', ascending=False)
    logger.info(best_years_sorted)
    
    df = pd.merge(df_json, df_csv, on='year')
    df['series_id'] = df['series_id'].str.strip()
    df['period'] = df['period'].str.strip()
    filtered_df = df[(df['series_id'] == 'PRS30006032') & (df['period'] == 'Q01')]
    
    logger.info("filtered_df")
    logger.info(filtered_df)

    return "Function Success!!"