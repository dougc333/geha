data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "forms" {
  cidr_block           = "10.43.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "forms" {
  vpc_id = aws_vpc.forms.id
  tags   = { Name = "${var.project_name}-igw" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.forms.id
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  cidr_block              = cidrsubnet(aws_vpc.forms.cidr_block, 8, count.index)
  map_public_ip_on_launch = false
  tags                    = { Name = "${var.project_name}-public-${count.index + 1}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.forms.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.forms.id
  }
  tags = { Name = "${var.project_name}-public" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "worker" {
  name        = "${var.project_name}-worker"
  description = "Outbound-only forms extraction task"
  vpc_id      = aws_vpc.forms.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-worker" }
}
