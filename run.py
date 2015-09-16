#
# Copyright (C) 2015 Jason Mar
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#



import wp2s3
kwargs = wp2s3.default_kwargs

# Edit the lines below with the specifics of your Wordpress account
myargs = {
    "wp_uri" : 'https://blogname.wordpress.com/xmlrpc.php',
    "wp_user" : 'user@wordpress.com',
    "wp_pass" : 'password',
    "wp_db" : 'wp.sqlite3',
    "wp_host" : 'blogname.files.wordpress.com',
    "s3_host" : 's3-us-west-2.amazonaws.com',
    "s3_bucket" : 'blogname',
    "wp_upload_dir" : r'C:\tmp\wp-upload',
    "state" : { # Edit state if you need to skip certain steps
        "metadata_loaded" : False, # False => fetch all media items and save to sqlite database
        "media_downloaded" : False, # False => download all media items using links in database
        "media_uploaded" : False, # False => upload all files from wp_upload_dir to s3 bucket
        "posts_edited" : False # False => fetch all posts, replace wp_host with s3_host/s3_bucket, and apply changes
    }
}
kwargs.update(myargs)
wp2s3.perform_migration(kwargs)

# EOF