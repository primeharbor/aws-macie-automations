#!/usr/bin/env python3

#
# Create one-time or weekly scan jobs on a specific bucket or all buckets
#

import boto3
from botocore.exceptions import ClientError
import json
import os
import sys
import time
import datetime
from dateutil import tz

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# criteria for a job that will scan all public buckets
PUBLIC_CRITERIA = {
    'bucketCriteria': {
        "includes": {"and": [{
            "simpleCriterion": {
                "comparator": "EQ",
                "key": "S3_BUCKET_EFFECTIVE_PERMISSION",
                "values": ["PUBLIC"]
                }
            }]
        }}
    }

DAY_OF_WEEK = "MONDAY"  # Start your week off right!


def main(args, logger):

    # Macie is regional even though buckets aren't. So we need to iterate across regions to find out bucket
    # Unless you know already
    if args.region:
        regions = [args.region]
    else:
        regions = get_regions()

    for r in regions:
        macie_client = boto3.client('macie2', region_name=r)

        if args.bucket:
            bucket_info = get_bucket_info(args.bucket, macie_client)
            if bucket_info is None:
                logger.debug(f"{args.bucket} isn't in {r}")
                continue
            logger.info(f"Found {args.bucket} in {r}")
            if args.weekly:
                create_scheduled_job(macie_client, args, r, bucket=args.bucket, accountId=bucket_info['accountId'])
            elif args.onetime:
                create_one_time_job(macie_client, args, r, bucket=args.bucket, accountId=bucket_info['accountId'])
            else:
                print("Neither --weekly or --onetime specified")
            # Found the bucket, we're done here.
            exit(0)
        else:
            if args.weekly:
                create_scheduled_job(macie_client, args, r)
            elif args.onetime:
                create_one_time_job(macie_client, args, r)
            else:
                print("Neither --weekly or --onetime specified")


def create_one_time_job(client, args, region, bucket=None, accountId=None):
    # define the Macie Job definition
    job = {
        "description": args.description,
        "initialRun": True,
        "jobType": 'ONE_TIME',
        "name": f"{args.name}-{region}",
        "s3JobDefinition": {},
        "samplingPercentage": args.sample
    }

    if bucket is None:
        job['s3JobDefinition'] = PUBLIC_CRITERIA
    else:
        job['s3JobDefinition'] = {'bucketDefinitions': [{"accountId": accountId, 'buckets': [bucket]}]}

    if args.actually_do_it:
        response = client.create_classification_job(**job)
        logger.info(f"Job {args.name}-{region} created in {region} with ID: {response['jobId']} ({response['jobArn']})")
    else:
        logger.info(f"Would create job {json.dumps(job, indent=2)}")


def create_scheduled_job(client, args, region, bucket=None, accountId=None):
    # define the Macie Job definition
    job = {
        "description": args.description,
        "initialRun": False,
        "jobType": 'SCHEDULED',
        "name": f"{args.name}-{region}",
        "s3JobDefinition": {},
        "scheduleFrequency": {'weeklySchedule': {'dayOfWeek': DAY_OF_WEEK}},
        "samplingPercentage": args.sample
    }

    if bucket is None:
        job['s3JobDefinition'] = PUBLIC_CRITERIA
    else:
        job['s3JobDefinition'] = {'bucketDefinitions': [{"accountId": accountId, 'buckets': [bucket]}]}

    if args.actually_do_it:
        response = client.create_classification_job(**job)
        logger.info(f"Job {args.name}-{region} created in {region} with ID: {response['jobId']} ({response['jobArn']})")
    else:
        logger.info(f"Would create job {json.dumps(job, indent=2)}")


def get_bucket_info(bucket_name, client):
    response = client.describe_buckets(criteria={'bucketName': {'eq': [bucket_name]}})

    if 'buckets' in response and len(response['buckets']) == 1:
        bucket_info = response['buckets'][0]
    elif 'buckets' in response and len(response['buckets']) > 1:
        logger.warning(f"Found multiple buckets with name {bucket_name}. That's really odd.")
        bucket_info = response['buckets'][0]
    else:
        return(None)
    return(bucket_info)


def get_regions():
    """Return an array of the regions this account is active in. Ordered with us-east-1 in the front."""
    ec2 = boto3.client('ec2')
    response = ec2.describe_regions()
    output = ['us-east-1']
    for r in response['Regions']:
        if r['RegionName'] == "us-east-1":
            continue
        output.append(r['RegionName'])
    return(output)


def do_args():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", help="print debugging info", action='store_true')
    parser.add_argument("--error", help="print error info only", action='store_true')
    parser.add_argument("--region", help="Only create the job in this region")
    parser.add_argument("--bucket", help="Create Job to only scan this bucket")
    parser.add_argument("--actually-do-it", help="Actually create the job. Omitting this is a dry-run", action='store_true')
    parser.add_argument("--sample", help="Percentage of objects to randomly scan", default=100)
    parser.add_argument("--name", help="Name of the job to execute", required=True)
    parser.add_argument("--description", help="Description to apply to each job", default=f"Created by {sys.argv[0]}")
    parser.add_argument("--weekly", help="Create a weekly scan job of new objects", action='store_true')
    parser.add_argument("--onetime", help="Create a one time scan of all objects", action='store_true')
    args = parser.parse_args()
    return(args)


if __name__ == '__main__':

    args = do_args()

    # Logging idea stolen from: https://docs.python.org/3/howto/logging.html#configuring-logging
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    if args.error:
        logger.setLevel(logging.ERROR)
    elif args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # create formatter
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    # add formatter to ch
    ch.setFormatter(formatter)
    # add ch to logger
    logger.addHandler(ch)

    try:
        main(args, logger)
    except KeyboardInterrupt:
        exit(1)
