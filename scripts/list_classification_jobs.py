#!/usr/bin/env python3

#
# Script to hit all the regions and get status of classification jobs
#

import boto3
from botocore.exceptions import ClientError
import json
import os
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


def main(args, logger):

    # Macie is regional so we need to iterate across regions
    if args.region:
        regions = [args.region]
    else:
        regions = get_regions()

    # API will allow filtering, we can combine if we want
    # Ref: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/macie2.html#Macie2.Client.list_classification_jobs
    filter = {'includes': []}
    if args.status:
        filter['includes'].append({'comparator': 'EQ', 'key': 'jobStatus', 'values': [args.status]})
    if args.weekly:
        filter['includes'].append({'comparator': 'EQ', 'key': 'jobType', 'values': ['SCHEDULED']})
    if args.onetime:
        filter['includes'].append({'comparator': 'EQ', 'key': 'jobType', 'values': ['ONE_TIME']})

    for r in regions:
        macie_client = boto3.client('macie2', region_name=r)

        # Todo: pagination
        response = macie_client.list_classification_jobs(filterCriteria=filter)

        for j in response['items']:
            if 'bucketCriteria' in j and j['bucketCriteria'] == PUBLIC_CRITERIA['bucketCriteria']:
                print(f"{j['name']} in {r} type {j['jobType']} status {j['jobStatus']} Created {j['createdAt'].date()} for public buckets ")
            elif 'bucketDefinitions' in j:
                for bd in j['bucketDefinitions']:
                    print(f"{j['name']} in {r} type {j['jobType']} status {j['jobStatus']} Created {j['createdAt'].date()} for {bd['buckets']} in account {bd['accountId']} ")
            else:
                print(f"{j['name']} in {r} type {j['jobType']} status {j['jobStatus']} Created {j['createdAt'].date()} is a one-off job")


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
    parser.add_argument("--region", help="Only run in this region")
    parser.add_argument("--status", help="Filter to show only this status",
                        choices=['RUNNING', 'PAUSED', 'CANCELLED', 'COMPLETE', 'IDLE', 'USER_PAUSED'])
    parser.add_argument("--weekly", help="Filter to show only weekly scan job of new objects", action='store_true')
    parser.add_argument("--onetime", help="Filter to show only one time scan of all objects", action='store_true')
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
