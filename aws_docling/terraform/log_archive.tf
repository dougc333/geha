data "archive_file" "log_archiver" {
  type        = "zip"
  source_file = "${path.module}/../lambda/archive_logs.py"
  output_path = "${path.module}/log_archiver.zip"
}

resource "aws_iam_role" "log_archiver" {
  name = "${var.project_name}-log-archiver"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "log_archiver_basic" {
  role       = aws_iam_role.log_archiver.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "log_archiver_access" {
  name = "${var.project_name}-archive-logs"
  role = aws_iam_role.log_archiver.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["logs:GetLogEvents"], Resource = "${trimsuffix(aws_cloudwatch_log_group.docling.arn, ":*")}:log-stream:*" },
      { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${aws_s3_bucket.documents.arn}/jobs/logs/*" }
    ]
  })
}

resource "aws_lambda_function" "log_archiver" {
  function_name    = "${var.project_name}-archive-logs"
  role             = aws_iam_role.log_archiver.arn
  runtime          = "python3.12"
  handler          = "archive_logs.handler"
  filename         = data.archive_file.log_archiver.output_path
  source_code_hash = data.archive_file.log_archiver.output_base64sha256
  timeout          = 60
  memory_size      = 128
  environment {
    variables = {
      LOG_GROUP     = aws_cloudwatch_log_group.docling.name
      OUTPUT_BUCKET = aws_s3_bucket.documents.id
    }
  }
  depends_on = [aws_iam_role_policy_attachment.log_archiver_basic, aws_iam_role_policy.log_archiver_access]
}

resource "aws_cloudwatch_event_rule" "docling_stopped" {
  name = "${var.project_name}-task-stopped"
  event_pattern = jsonencode({
    source        = ["aws.ecs"]
    "detail-type" = ["ECS Task State Change"]
    detail = {
      clusterArn = [aws_ecs_cluster.docling.arn]
      lastStatus = ["STOPPED"]
    }
  })
}

resource "aws_cloudwatch_event_target" "log_archiver" {
  rule = aws_cloudwatch_event_rule.docling_stopped.name
  arn  = aws_lambda_function.log_archiver.arn
}

resource "aws_lambda_permission" "eventbridge_log_archiver" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.log_archiver.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.docling_stopped.arn
}
