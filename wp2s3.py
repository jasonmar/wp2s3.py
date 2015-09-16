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

import os
import os.path
import errno
import sqlite3
import time
import json
import sqlite3
import urllib
import urllib2
import cookielib
import boto3
import botocore
import wordpress_xmlrpc
from botocore.exceptions import ClientError
from wordpress_xmlrpc import Client
from wordpress_xmlrpc import WordPressPost
from wordpress_xmlrpc.methods import media
from wordpress_xmlrpc.methods import posts
from urllib2 import HTTPError
from urllib2 import URLError



# Perform all media library migration steps
def perform_migration(kwargs):

    # Get the authenticated connection objects
    kwargs = init(kwargs)

    # Download and deduplicte media library metadata
    if not kwargs['state']['metadata_loaded']:
        prepare_media_items(kwargs)

    # Download the media library
    if not kwargs['state']['media_downloaded']:
        download_media_items(kwargs)

    # Upload the media library to S3
    if not kwargs['state']['media_uploaded']:
        upload_files(kwargs)

    # Edit the posts
    if not kwargs['state']['posts_edited']:
        replace_images(kwargs)

    kwargs['db'].close()
    print 'Finished migrating media items from ' + x['wp_host'] + ' to ' + x['s3_host'] + x['s3_bucket']



default_kwargs = {
    "wp_uri" : 'https://blogname.wordpress.com/xmlrpc.php',
    "wp_user" : 'user@wordpress.com',
    "wp_pass" : 'password',
    "wp_db" : 'wp.sqlite3',
    "wp_host" : 'blogname.files.wordpress.com',
    "s3_host" : 's3-us-west-2.amazonaws.com',
    "s3_bucket" : 'blogname',
    "wp_upload_dir" : r'C:\tmp\wp-upload',
    "http_headers" : {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.93 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8'
    },
    "state" : { # Edit state if you need to skip certain steps
        "metadata_loaded" : False, # False => fetch all media items and save to sqlite database
        "media_downloaded" : False, # False => download all media items using links in database
        "media_uploaded" : False, # False => upload all files from wp_upload_dir to s3 bucket
        "posts_edited" : False # False => fetch all posts, replace wp_host with s3_host/s3_bucket, and apply changes
    }
}



# login to wordpress.com
def login(kwargs):

    cookie_file = 'cookiejar.txt'
    cookies = cookielib.CookieJar()

    cookie_handler = urllib2.HTTPCookieProcessor(cookies)
    redirect_handler = urllib2.HTTPRedirectHandler()
    opener = urllib2.build_opener(redirect_handler, cookie_handler)

    state = {"opener": opener}

    uri = "https://wordpress.com/wp-login.php"
    opts = {
        'log': kwargs['wp_user'],
        'pwd': kwargs['wp_pass'],
        'rememberme': 'forever',
        'wp-submit': 'Log In',
        'testcookie': 1
    }

    # Prepare POST request
    post_data = urllib.urlencode(opts)
    request = urllib2.Request(uri, post_data, kwargs['http_headers'])

    # Submit POST
    try:
        response = opener.open(request)
    except HTTPError as e:
        print(e.code)
        print(e.read())
        raise

    print 'successfully logged in'

    cookies.extract_cookies(response, request)

    return state



# Download data from a uri to a file
def uri2file(uri, file, kwargs):

    print 'downloading ' + uri + ' to ' + file

    # Prepare GET request
    request = urllib2.Request(uri, None, kwargs['http_headers'])

    try:
        # Submit request
        response = kwargs['opener'].open(request)
        # Write data to file
        with open(file, "wb") as of:
            of.write(response.read())
    except HTTPError as e:
        print 'request for ' + uri + ' failed with HTTPError: ' + str(e.code) + ' ' + e.msg
    except URLError as e:
        print 'request for ' + uri + ' failed URLError:  ' + e.reason
    except TypeError as e:
        print 'request for ' + uri + ' failed with TypeError:  ' + e.msg
    except:
        print 'request for ' + uri + ' failed'




# Obtain authenticated connection object
def init(kwargs):

    print 'Creating Wordpress.com session'
    opener = login(kwargs)

    print 'Connecting to Wordpress XMLRPC Endpoint ' + kwargs['wp_uri']
    wp_client = Client(kwargs['wp_uri'], kwargs['wp_user'], kwargs['wp_pass'])

    print 'Connecting to Amazon S3'
    s3 = boto3.resource('s3')

    print 'Connecting to SQLite3 Database ' + kwargs['wp_db']
    db = sqlite3.connect(kwargs['wp_db'])
    db_cursor = db.cursor()

    print 'All connections have been initialized'
    res = {"wp_client": wp_client, "db": db, "db_cursor": db_cursor, "s3": s3}
    res.update(kwargs)
    res.update(opener)
    return res



def get_wp_media_library(wp_client):
    media_items = []
    i0 = 0
    n = 999
    k = 100

    while n > 0:
        filter = {"number": k, "offset": i0}
        method = media.GetMediaLibrary(filter)
        res = wp_client.call(method)
        i0 += k
        n = len(res)

        for r in res:
            media_items.append(r)

    return media_items



def create_media_table(db, cursor):
    createTableSQL='''
    CREATE TABLE WPMEDIA (
      id text,
      parent int,
      title text,
      description text,
      caption text,
      date_created long,
      link text,
      thumbnail text,
      metadata text
    )
    '''

    cursor.execute(createTableSQL)
    db.commit()



def insert_media_items(media_items, db, db_cursor):
    insertMediaSQL='''
    INSERT INTO WPMEDIA (
      id,
      parent,
      title,
      description,
      caption,
      date_created,
      link,
      thumbnail,
      metadata
    ) VALUES (?,?,?,?,?,?,?,?,?)
    '''

    for x in media_items:
        n = 0
        dt = x.date_created

        # get unix time
        ts = long(time.mktime((dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, 0, 0, 0)))

        # convert metadata dict to string
        metadata = json.dumps(x.metadata)
        row = (x.id, x.parent, x.title, x.description, x.caption, ts, x.link, x.thumbnail, metadata)

        # Insert the data
        db_cursor.execute(insertMediaSQL, row)

        if n % 100 == 0:
            db.commit()

    db.commit()



def get_distinct_records(db, db_cursor):

    create_table_sql = '''
    CREATE TABLE WPMEDIA1 AS
    SELECT id, parent, title, description, caption, date_created, link, thumbnail, metadata
    FROM WPMEDIA
    GROUP BY id, parent, title, description, caption, date_created, link, thumbnail, metadata
    '''
    db_cursor.execute(create_table_sql)

    db_cursor.execute("DROP TABLE WPMEDIA")
    db.commit()



def mkdir_p(dir):
    try:
        os.makedirs(dir)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(dir):
            pass
        else:
            raise



def download_media_items(kwargs):
    kwargs['db_cursor'].execute("SELECT LINK FROM WPMEDIA1")
    rs = kwargs['db_cursor'].fetchall()
    n = 0
    m = len(rs)
    log1 = ' of ' + str(m) + ': '

    for r in rs:
        media_uri = r[0]
        if media_uri.lower().startswith("http"):
            split = media_uri.split("/")
            
            # get YYYY/MM from original media link
            outdir = kwargs['wp_upload_dir'] + os.path.sep + split[-3] + os.path.sep + split[-2] + os.path.sep
            filename = split[-1]
            
            mkdir_p(outdir)            
            outfile = os.path.join(outdir, filename)
            
            # Check whether file exists
            if os.path.isfile(outfile):
                print str(n) + log1 + outfile + ' already exists'
            else:
                print str(n) + log1 + outfile
                # Download the file
                uri2file(media_uri, outfile, kwargs)
            n += 1
        else:
            print 'invalid link: ' + media_uri



# bucket_exists(s3_bucket: str, s3: s3.ServiceResource): Boolean
def bucket_exists(s3_bucket, s3):
    try:
        # Send HEAD BUCKET request and get response
        response = s3.meta.client.head_bucket(Bucket=s3_bucket)['ResponseMetadata']
        status = response['HTTPStatusCode']
    except ClientError as e:
        # Collect error message
        response = e.response['ResponseMetadata']
        status = response['HTTPStatusCode']
    if status == 200:
        # The bucket exists
        return True
    elif status == 404:
        # The bucket probably doesn't exist
        return False
    else:
        # The bucket may already exist but we aren't authorized (403)
        raise



# key_exists(s3_bucket, key_name: str, s3: s3.ServiceResource): Boolean
def key_exists(s3_bucket, key_name, s3):
    try:
        # Send HEAD OBJECT request and collect response
        response = s3.meta.client.head_object(Bucket=s3_bucket, Key=key_name)['ResponseMetadata']
        status = response['HTTPStatusCode']
    except ClientError as e:
        response = e.response['ResponseMetadata']
        status = response['HTTPStatusCode']
    if status == 200:
        # The object exists
        return True
    elif status == 404:
        # The object probably doesn't exist
        return False
    else:
        # The object may already exist and we aren't authorized (403)
        raise



# Upload files in directory to AWS S3 bucket
# ls(dir: str): [(file_path, key_name)]
def ls(dir):
    print 'finding files in ' + dir
    i = len(dir) + 1
    keys = []
    for dirname, dirnames, filenames in os.walk(dir):
        for filename in filenames:

            # Remove base directory and replace '\' with '/' - should end up with 'YYYY/MM'
            key_name = dirname[i:].replace(os.path.sep,'/') + '/' + filename

            # Get the full path of the file
            file_path = os.path.join(dirname, filename)

            # Add the key and path as a tuple
            keys.append((file_path, key_name))

    print str(len(keys)) + ' files found'
    return keys



# Upload files in directory to AWS S3 bucket
# upload_dir_to_bucket(keys: (str,str), s3_bucket: str, s3: S3.Client): int
def upload_dir_to_bucket(keys, s3_bucket, s3):
    n_uploaded = 0
    for key in keys:
        infile = key[0]
        key_name = key[1]
        upload_successful = upload_if_not_exists(s3_bucket, key_name, infile, s3)
        if upload_successful:
            n_uploaded += 1
            if n_uploaded % 100 == 0:
                print str(n_uploaded) + ' files uploaded'
    print str(n_uploaded) + ' files uploaded'
    return n_uploaded



# upload_if_not_exists(s3_bucket: str, key_name: str, infile: str, s3: s3.ServiceResource): Boolean
def upload_if_not_exists(s3_bucket, key_name, infile, s3):
    # Check if key already exists in bucket
    if key_exists(s3_bucket, key_name, s3):
        print key_name + ' already exists'
        return False

    else:
        # Specify the target key
        object = s3.Object(s3_bucket, key_name)

        print 'uploading ' + infile + ' as ' + key_name + ' in ' + s3_bucket

        # Upload the file to the key
        object.put(ACL='public-read', Body=open(infile, 'rb'))

        return True



# Replaces string in post
# replace_str_in_post(old: str, new: str, post: wordpress_xmlrpc.WordPressPost, wp_client: wordpress_xmlrpc.Client): Boolean
def replace_str_in_post(old, new, post, wp_client):

    # Check whether the post has content
    if len(post.content) > 0:
        if post.content.find(old) > -1:
            needs_replacement = True
        else:
            needs_replacement = False
    else:
        print 'post id ' + str(post.id) + ' ' + post.slug + ' has content of length 0'
        needs_replacement = False

    if needs_replacement:

        # Replace the wordpress.com media hostname with the s3 uri
        post.content = post.content.replace(old, new)

        # Post the edited content to the wordpress xmlrpc server
        wp_client.call(posts.EditPost(post.id, post))

        return True
    else:
        print 'post id ' + str(post.id) + ' \"' + post.slug + '\" did not need replacement'
        return False



# Replaces uri in wordpress posts
#replace_uri_in_posts(old: str, new: str, wp_client: wordpress_xmlrpc.Client): int
def replace_uri_in_posts(old, new, wp_client):

    i0 = 0
    n = 999
    k = 100
    m = 0

    # Collect posts to be edited
    while n > 0:
        filter = {"number": k, "offset": i0}
        method = posts.GetPosts(filter)
        
        # Get a batch of WordpressPost
        res = wp_client.call(method)
        i0 += k
        n = len(res)

        for post in res:

            # Replace the hostname
            post_modified = replace_str_in_post(old, new, post, wp_client)

            # Record whether the post was modified
            if post_modified:
                print 'modified post_id ' + str(post.id) + ' "' + post.slug + '"'
                m += 1
                if m % 100 == 0:
                    print str(m) + ' posts modified'
            else:
                print 'post_id ' + str(post.id) + ' was not modified'

    print str(m) + ' posts modified'
    return m



# get_post_ids(cursor: sqlite3.Cursor): [int]
def get_post_ids(cursor):
    res = []
    cursor.execute('SELECT PARENT FROM WPMEDIA1')
    post_ids = cursor.fetchall()
    print str(len(post_ids)) + ' posts found'
    for id in post_ids:
      res.append(id[0])
    return res



# Downloads Media Library and deduplicates records
def prepare_media_items(kwargs):

    media_items = get_wp_media_library(kwargs['wp_client'])

    create_media_table(kwargs['db'], kwargs['db_cursor'])

    insert_media_items(media_items, kwargs['db'], kwargs['db_cursor'])

    get_distinct_records(kwargs['db'], kwargs['db_cursor'])

    kwargs['db_cursor'].execute("SELECT COUNT(1) FROM WPMEDIA1")
    n_items = kwargs['db_cursor'].fetchone()[0]
    print str(n_items) + ' distinct media items'



# Uploads media library to Amazon S3
def upload_files(kwargs):

    # List files to be uploaded
    keys = ls(kwargs['wp_upload_dir'])

    if len(keys) > 0:
        # Upload the files
        print 'uploading files in ' + kwargs['wp_upload_dir'] + ' to ' + kwargs['s3_bucket']
        n_uploaded = upload_dir_to_bucket(keys, kwargs['s3_bucket'], kwargs['s3'])
    else:
        n_uploaded = 0

    return n_uploaded



# Edits posts with new image URIs
def replace_images(kwargs):

    # Replace wordpress media hostname with s3 bucket uri
    old = kwargs['wp_host']
    new = kwargs['s3_host'] + '/' + kwargs['s3_bucket']
    print 'replacing ' + old + ' with ' + new + ' in all posts'
    n_replaced = replace_uri_in_posts(old, new, kwargs['wp_client'])



# EOF