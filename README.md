## Description

wp2s3.py is a python script that allows users to retrieve download all their media from a wordpress.com blog, upload all of it to an Amazon S3 bucket, and update URI's in all the posts to point to the S3 bucket.

## Motivation

The goal of this script is to provide an easy to use tool to migrate images from Wordpress.com to Amazon S3. If a wordpress.com blog you've been pulled into supporting has reached capacity but the users are unwilling or unable to pay for premium hosting, wp2s3.py may provide a way to delay the need to upgrade.

## Features

  * Retrieves media item metadata from wordpress.com blog
  * Stores full media metadata in a SQLite3 database
  * Uploads downloaded media to a specified Amazon S3 bucket
  * Modifies URI in all posts to reference the S3 bucket rather than wordpress.com
  * _Does not automatically delete images_

## Usage

  First, clone or download the contents of this repository.

  Edit the contents of run.py and provide the following information:

  * Wordpress XML RPC URI (your URI + '/xmlrpc.php)
  * credentials - the username and password you use to login to wordpress.com
  * hostnames - the hostname where your images are stored and 
  * image directory - where your media library will be downloaded to
  * S3 bucket name

  Once you've saved all the necessary items in run.py, execute it with python


    `python run.py`


  After verifying that all your posts are working and images are being served from S3, you will need to visit the admin console to delete them from the media library manually in order to free up space.

## Installation

You will need the AWS Python SDK and the Wordpress XML-RPC Client.

    pip install boto3 python-wordpress-xmlrpc

You will need to setup your AWS configuration.

If you have the AWS CLI, you can run `aws configure`

    > aws configure
    AWS Access Key ID [None]: YOUR_KEY
    AWS Secret Access Key [None]: YOUR_SECRET
    Default region name [None]: us-west-2
    Default output format [None]: json

You can also create your AWS CLI configuration file manually

    echo '[default]
    aws_access_key_id = YOUR_KEY
    aws_secret_access_key = YOUR_SECRET' >> ~/.aws/credentials
    echo '[default]
    region=us-west-2' >> ~/.aws/config

## AWS S3 IAM Security Settings

It's recommended to create an IAM user specifically for the purpose of uploading to s3.

You'll need two User Policies per bucket if you want to grant the minimum level of permissions.

The following User Policy will grant permission to upload files to a bucket and download any files that have already been uploaded.

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "Stmt1442361463000",
          "Effect": "Allow",
          "Action": [
            "s3:GetObject",
            "s3:GetObjectAcl",
            "s3:PutObject",
            "s3:PutObjectAcl",
            "s3:PutObjectVersionAcl"
          ],
          "Resource": [
            "arn:aws:s3:::bucketname/*"
          ]
        }
      ]
    }

The following User Policy grants permission to create a bucket with a specific name and retrieve metadata for the bucket once it's created.

    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Sid": "Stmt1442361463001",
          "Effect": "Allow",
          "Action": [
            "s3:CreateBucket",
            "s3:GetBucket",
            "s3:GetBucketAcl",
            "s3:GetBucketLocation",
            "s3:ListBucket"
          ],
          "Resource": [
            "arn:aws:s3:::bucketname"
          ]
        }
      ]
    }

## License

This project uses the Apache 2.0 license. Read LICENSE file.

## Authors and Copyright

Copyright (C) 2015 Jason Mar

