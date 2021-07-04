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

TIMERANGE = {
    "MONTH_TO_DATE": "month to date",
    "PAST_30_DAYS": "in the past 30 days"
}


def main(args, logger):
    # variables to store the global size and cost
    total_cost = 0

    # Macie is regional even though buckets aren't.
    # So we need to iterate across regions to find our bucket
    # Unless you know already
    if args.region:
        regions = [args.region]
    else:
        regions = get_regions()

    for r in regions:
        macie_client = boto3.client('macie2', region_name=r)
        response = macie_client.get_usage_totals(timeRange=args.timerange)

        for t in response['usageTotals']:
            if t['type'] == "SENSITIVE_DATA_DISCOVERY":
                if t['estimatedCost'] == "0":
                    continue
                print(f"Cost of Macie in {r} is estimated to be ${float(t['estimatedCost']):,} {TIMERANGE[args.timerange]}")
            total_cost += float(t['estimatedCost'])

    print(f"Total Cost: US${int(total_cost):,} {TIMERANGE[args.timerange]}")


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
    parser.add_argument("--timerange", help="Query for this timeRange", choices=['MONTH_TO_DATE', 'PAST_30_DAYS'], default='MONTH_TO_DATE')
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
