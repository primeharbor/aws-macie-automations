#!/usr/bin/env python3

#
# Script to get the price of enabling Macie for all Public Buckets, or for a specific Bucket.
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

# https://aws.amazon.com/macie/pricing/
PRICE_PER_GB = 1

DIVISOR = 1024*1024*1024
PRICE_PER_BYTE = PRICE_PER_GB / DIVISOR

# mapping needed to filter to only public buckets
PUBLIC_CRITERIA = {
  "publicAccess.effectivePermission": {
    "eq": ["PUBLIC"]
  }
}


def main(args, logger):

    # variables to store the global size and cost
    total_cost = 0
    total_size = 0

    # Macie is regional even though buckets aren't.
    # So we need to iterate across regions to find our bucket
    # Unless you know already
    if args.region:
        regions = [args.region]
    else:
        regions = get_regions()

    for r in regions:
        macie_client = boto3.client('macie2', region_name=r)

        if args.bucket:
            logger.debug(f"Looking for {args.bucket} in region {r}")
            bucket_info = get_bucket_info(args.bucket, macie_client)
            if bucket_info is None:
                logger.debug(f"{args.bucket} isn't in {r}")
                continue
            logger.debug(f"Found {args.bucket} in {r}")
            print(f"Macie Scan cost of {args.bucket} is ${int(get_bucket_cost(bucket_info)):,} (size {int(bucket_info['classifiableSizeInBytes']/DIVISOR):,} GB - {bucket_info['classifiableObjectCount']:,} objects)")
            exit(0)
        else:
            regional_cost = 0
            regional_size = 0
            regional_count = 0
            paginator = macie_client.get_paginator('describe_buckets')
            response = paginator.paginate(criteria=PUBLIC_CRITERIA)
            for page in response:
                for b in page['buckets']:
                    regional_cost += get_bucket_cost(b)
                    regional_size += b['classifiableSizeInBytes']
                    regional_count += 1

            print(f"Public Scan in {r} will cost US${int(regional_cost):,} size: {int(regional_size/DIVISOR):,} GB for {regional_count} buckets")

            total_cost += regional_cost
            total_size += regional_size

    print(f"Total Cost: US${int(total_cost):,} Total Size: {int(total_size/DIVISOR):,}GB")


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


def get_bucket_cost(bucket_info):

    cost = bucket_info['classifiableSizeInBytes'] * PRICE_PER_BYTE

    logger.debug(f"Macie Scan cost of {bucket_info['bucketName']} is ${int(cost):,} (size {int(bucket_info['classifiableSizeInBytes']/DIVISOR):,} GB - {bucket_info['classifiableObjectCount']:,} objects)")

    return(cost)


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
    parser.add_argument("--bucket", help="Only price out this bucket")
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
