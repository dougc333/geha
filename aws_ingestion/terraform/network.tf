data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "ingestion" {
  cidr_block           = "10.57.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "ingestion" {
  vpc_id = aws_vpc.ingestion.id
  tags   = { Name = "${var.project_name}-igw" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.ingestion.id
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  cidr_block              = cidrsubnet(aws_vpc.ingestion.cidr_block, 8, count.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.project_name}-public-${count.index + 1}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.ingestion.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.ingestion.id
  }
  tags = { Name = "${var.project_name}-public" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  count       = var.runtime_enabled ? 1 : 0
  name        = "${var.project_name}-alb"
  description = "Demo browser access from the configured client CIDRs"
  vpc_id      = aws_vpc.ingestion.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "api" {
  count       = var.runtime_enabled ? 1 : 0
  name        = "${var.project_name}-api"
  description = "HTTP traffic from the application load balancer"
  vpc_id      = aws_vpc.ingestion.id
  ingress {
    from_port       = 8510
    to_port         = 8510
    protocol        = "tcp"
    security_groups = [aws_security_group.alb[0].id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "worker" {
  name        = "${var.project_name}-worker"
  description = "Outbound-only processing worker"
  vpc_id      = aws_vpc.ingestion.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
