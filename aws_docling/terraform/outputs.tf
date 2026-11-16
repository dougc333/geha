output "bucket_name" {
  value = aws_s3_bucket.documents.id
}

output "vpc_id" {
  value = aws_vpc.docling.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "lambda_name" {
  value = aws_lambda_function.convert.function_name
}
