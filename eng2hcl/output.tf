resource "aws_s3_bucket" "my_data" {
  acl    = "private"
  region = "us-east-1"
}

resource "aws_instance" "WebServer" {
  ami           = "ami-0abc123"
  instance_type = "t2.micro"
  monitoring    = true
}

resource "aws_vpc" "main_vpc" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_db_instance" "appdb" {
  engine            = "postgres"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
}
