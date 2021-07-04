#!/usr/bin/env python3

#
# Get stats on findings for a specific bucket or all buckets.
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


def main(args, logger):

    # Macie is regional even though buckets aren't. So we need to iterate across regions to find out bucket
    # Unless you know already
    if args.region:
        regions = [args.region]
    else:
        regions = get_regions()

    for r in regions:
        macie_client = boto3.client('macie2', region_name=r)

        findingCriteria = {
            'criterion': {
                'category': {'eq': ['CLASSIFICATION']},
                'severity.description': {'eq': [args.severity]}
            }
        }
        if args.bucket:
            findingCriteria['criterion']['resourcesAffected.s3Bucket.name'] = {'eq': [args.bucket]}

        list_response = macie_client.get_finding_statistics(
            findingCriteria=findingCriteria,
            size=5000,
            groupBy='resourcesAffected.s3Bucket.name'
        )
        findings = list_response['countsByGroup']
        logger.debug(f"Found {len(findings)} findings in {r}")
        if len(findings) == 0:
            # No findings in this region, move along
            continue

        for f in list_response['countsByGroup']:
            print(f"{f['groupKey']} ({r}) has {f['count']} {args.severity} classification findings")


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
    parser.add_argument("--region", help="Only Process this region")
    parser.add_argument("--bucket", help="Only price out this bucket")
    parser.add_argument("--severity", help="Report on this severity", required=True)
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
