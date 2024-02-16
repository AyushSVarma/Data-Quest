provider "aws" {
  region = "us-east-1"
}

resource "aws_s3_bucket" "my_bucket" {
  bucket = "ayush-data-quest-tf"
}

resource "aws_iam_role" "ayush_lambda_role_quest" {
  name = "ayush_lambda_role_quest_tf"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      },
    ]
  })
}


resource "aws_iam_policy" "ayush_lambda_policy_quest" {
  name        = "av_lambda_policy_quest"
  description = "av quest policy"

  policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:RestoreObject",
                "s3:DeleteBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::ayush-data-quest-tf",
                "arn:aws:s3:::ayush-data-quest-tf/*"
            ]
        }
    ]
}
EOF
}

data "archive_file" "zip_the_python_code" {
 type        = "zip"
 source_dir  = "${path.module}/python/"
 output_path = "${path.module}/python/p1-lambda.zip"
}

resource "aws_iam_role_policy_attachment" "attach_quest_policy_to_iam_role"{
    role = aws_iam_role.ayush_lambda_role_quest.name
    policy_arn = aws_iam_policy.ayush_lambda_policy_quest.arn
}

resource "aws_lambda_function" "ayush_data_quest_lambda_fcn"{

    function_name = "Ayush-Data-Quest-Lambda-TF"
    role = aws_iam_role.ayush_lambda_role_quest.arn
    filename   = "${path.module}/python/p1-lambda.zip"
    handler = "p1-lambda.lambda_handler"
    runtime = "python3.10"
    depends_on   = [aws_iam_role_policy_attachment.attach_quest_policy_to_iam_role]
    timeout = 60
}

####For every message on the queue - execute a Lambda function that
####outputs the reports from Part 3 (just logging the results of the queries would be enough. No .ipynb is required).

resource "aws_sqs_queue" "ayush_sqs_queue" {
  name = "ayush-quest-sqs-queue"
  visibility_timeout_seconds  = 60  # Set the visibility timeout to 60 seconds
}

resource "aws_sqs_queue_policy" "example" {
  queue_url = aws_sqs_queue.ayush_sqs_queue.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = "*"
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.ayush_sqs_queue.arn
      Condition = {
        ArnEquals = { "aws:SourceArn": aws_s3_bucket.my_bucket.arn }
      }
    }]
  })
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.my_bucket.id
  queue {
    queue_arn     = aws_sqs_queue.ayush_sqs_queue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".json" 
    }
}

# Attach the SQS execution role to the Lambda function
resource "aws_iam_role_policy_attachment" "lambda_sqs_policy_attachment" {
  role       = aws_iam_role.ayush_lambda_role_quest.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaSQSQueueExecutionRole"
  }

data "archive_file" "zip_the_python_code_pt4" {
 type        = "zip"
 source_dir  = "${path.module}/python/"
 output_path = "${path.module}/python/pt4-lambda-fcn.zip"
}

##resource "aws_lambda_function" "sqs_processor_lambda" {
  ##function_name = "sqs-processor"
  ##role          = aws_iam_role.ayush_lambda_role_quest.arn
##}

resource "aws_lambda_function" "ayush_data_quest_lambda_fcn_pt4"{
    function_name = "Ayush-Data-Quest-Lambda-4"
    role = aws_iam_role.ayush_lambda_role_quest.arn
    filename   = "${path.module}/python/pt4-lambda-fcn.zip"
    handler = "pt4-lambda-fcn.lambda_handler"
    runtime = "python3.10"
    depends_on   = [aws_iam_role_policy_attachment.attach_quest_policy_to_iam_role]
    timeout = 60
    # source_code_hash = filebase64sha256("${path.module}/python/pt4-lambda-fcn.zip")
    layers  = ["arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python310:10"]
}

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn  = aws_sqs_queue.ayush_sqs_queue.arn
  function_name     = aws_lambda_function.ayush_data_quest_lambda_fcn_pt4.arn
  batch_size        = 10
}

resource "aws_cloudwatch_event_rule" "daily_lambda_trigger" {
  name                = "daily-ayush-lambda-trigger"
  description         = "Triggers Ayush Data Quest Lambda function every day"
  schedule_expression = "rate(1 day)"
}

resource "aws_lambda_permission" "allow_cloudwatch_to_invoke_ayush_lambda" {
  statement_id  = "AllowExecutionFromCloudWatchForAyushLambda"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ayush_data_quest_lambda_fcn.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_lambda_trigger.arn
}

resource "aws_cloudwatch_event_target" "ayush_lambda_daily_target" {
  rule      = aws_cloudwatch_event_rule.daily_lambda_trigger.name
  target_id = "AyushLambdaDailyExecution"
  arn       = aws_lambda_function.ayush_data_quest_lambda_fcn.arn
}
