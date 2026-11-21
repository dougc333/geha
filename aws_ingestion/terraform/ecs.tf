locals {
  common_environment = [
    { name = "AWS_REGION", value = var.aws_region },
    { name = "INGESTION_BUCKET", value = aws_s3_bucket.artifacts.id },
    { name = "INGESTION_QUEUE_URL", value = aws_sqs_queue.jobs.url },
    { name = "INGESTION_STATE_TABLE", value = aws_dynamodb_table.run_state.name },
    { name = "SQS_VISIBILITY_TIMEOUT", value = "900" },
    { name = "APP_BUILD_REVISION", value = var.image_tag },
  ]
  model_secret_arns = merge({ for name, secret in aws_secretsmanager_secret.model : name => secret.arn }, var.model_secret_arns)
  model_secrets     = [for name, arn in local.model_secret_arns : { name = name, valueFrom = arn }]
}

resource "aws_ecs_cluster" "ingestion" {
  name = var.project_name
}

resource "aws_ecs_task_definition" "api" {
  count                    = var.runtime_enabled ? 1 : 0
  family                   = "${var.project_name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.api.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.container_architecture
  }
  container_definitions = jsonencode([{
    name         = "api"
    image        = local.image_uri
    essential    = true
    command      = ["python", "-m", "document_ingestion_workflow.backend"]
    portMappings = [{ containerPort = 8510, hostPort = 8510, protocol = "tcp" }]
    environment = concat(local.common_environment, [
      { name = "HOST", value = "0.0.0.0" },
      { name = "PORT", value = "8510" },
    ])
    secrets = local.model_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  count                    = var.runtime_enabled ? 1 : 0
  family                   = "${var.project_name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.worker.arn
  ephemeral_storage {
    size_in_gib = var.worker_ephemeral_gib
  }
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.container_architecture
  }
  container_definitions = jsonencode([{
    name        = "worker"
    image       = local.image_uri
    essential   = true
    command     = ["python", "-m", "document_ingestion_workflow.worker"]
    environment = local.common_environment
    secrets     = local.model_secrets
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "worker"
      }
    }
  }])
}

resource "aws_lb" "api" {
  count              = var.runtime_enabled ? 1 : 0
  name               = substr("${var.project_name}-alb", 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb[0].id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 300
}

resource "aws_lb_target_group" "api" {
  count       = var.runtime_enabled ? 1 : 0
  name        = substr("${var.project_name}-api", 0, 32)
  port        = 8510
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.ingestion.id
  health_check {
    path                = "/api/health"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
    timeout             = 5
  }
}

resource "aws_lb_listener" "http" {
  count             = var.runtime_enabled ? 1 : 0
  load_balancer_arn = aws_lb.api[0].arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api[0].arn
  }
}

resource "aws_ecs_service" "api" {
  count           = var.runtime_enabled ? 1 : 0
  name            = "${var.project_name}-api"
  cluster         = aws_ecs_cluster.ingestion.id
  task_definition = aws_ecs_task_definition.api[0].arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.api[0].id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api[0].arn
    container_name   = "api"
    container_port   = 8510
  }
  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "worker" {
  count           = var.runtime_enabled ? 1 : 0
  name            = "${var.project_name}-worker"
  cluster         = aws_ecs_cluster.ingestion.id
  task_definition = aws_ecs_task_definition.worker[0].arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = true
  }
}
