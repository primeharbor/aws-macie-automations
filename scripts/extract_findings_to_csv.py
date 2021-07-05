#!/usr/bin/env python3

#
# Extract a CSV of findings for a particular bucket
#

import boto3
from botocore.exceptions import ClientError
import json
import os
import time
import datetime
from dateutil import tz
import csv


import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

CSV_HEADER = ['AccountId', 'BucketName', 'Region', 'FileExtension', 'Severity', 'FindingType',
              'FindingCount', 'Details', 'ObjectKey', 'S3Path', 'URLPath', 'FindingConsoleURL']


def main(args, logger):

    # Macie is regional even though buckets aren't. So we need to iterate across regions to find out bucket
    # Unless you know already
    if args.region:
        regions = [args.region]
    else:
        regions = get_regions()

    # Store bucket results
    results = {
        "Low": 0,
        "Medium": 0,
        "High": 0
    }

    with open(args.filename, 'w') as csvoutfile:
        writer = csv.writer(csvoutfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(CSV_HEADER)

        for r in regions:
            macie_client = boto3.client('macie2', region_name=r)

            # Build a Findings criteria dictionary to pass to Macie2
            findingCriteria = {'criterion': {'category': {'eq': ['CLASSIFICATION']}}}

            if args.bucket:
                findingCriteria['criterion']['resourcesAffected.s3Bucket.name'] = {'eq': [args.bucket]}

            if args.severity:
                if args.severity == "High":
                    findingCriteria['criterion']['severity.description'] = {'eq': ["High"]}
                elif args.severity == "Medium":
                    findingCriteria['criterion']['severity.description'] = {'eq': ["High", "Medium"]}
                else:
                    # No need to add a severity filter
                    pass

            # Macie is annyoing in that I have to list each findings, then pass the list of ids to the
            # get_findings() API to get any useful details. Bah
            list_response = macie_client.list_findings(
                findingCriteria=findingCriteria,
                maxResults=40
            )
            findings = list_response['findingIds']
            logger.debug(f"Found {len(findings)} findings in {r}")
            if len(findings) == 0:
                # No findings in this region, move along
                continue

            # Now get the meat of  these findings
            get_response = macie_client.get_findings(findingIds=findings)
            for f in get_response['findings']:
                bucket_name = f['resourcesAffected']['s3Bucket']['name']
                key = f['resourcesAffected']['s3Object']['key']
                summary, count = get_summary(f)
                writer.writerow([f['accountId'], bucket_name, r,
                                f['resourcesAffected']['s3Object']['extension'],
                                f['severity']['description'], f['type'],
                                count, summary, key,
                                f"s3://{bucket_name}/{key}",
                                f"https://{bucket_name}.s3.amazonaws.com/{key}",
                                f"https://{r}.console.aws.amazon.com/macie/home?region={r}#findings?search=resourcesAffected.s3Bucket.name%3D{bucket_name}&macros=current&itemId={f['id']}"])
                results[f['severity']['description']] += 1

            # pagination is a pita. Here we continue to the List pagination
            while 'nextToken' in list_response:
                list_response = macie_client.list_findings(
                    findingCriteria=findingCriteria,
                    maxResults=40,
                    nextToken=list_response['nextToken']
                )
                findings = list_response['findingIds']
                logger.debug(f"Found {len(findings)} more findings in {r}")
                get_response = macie_client.get_findings(findingIds=findings)
                for f in get_response['findings']:
                    bucket_name = f['resourcesAffected']['s3Bucket']['name']
                    key = f['resourcesAffected']['s3Object']['key']
                    summary, count = get_summary(f)
                    writer.writerow([f['accountId'], bucket_name, r,
                                    f['resourcesAffected']['s3Object']['extension'],
                                    f['severity']['description'], f['type'],
                                    count, summary, key,
                                    f"s3://{bucket_name}/{key}",
                                    f"https://{bucket_name}.s3.amazonaws.com/{key}",
                                    f"https://{r}.console.aws.amazon.com/macie/home?region={r}#findings?search=resourcesAffected.s3Bucket.name%3D{bucket_name}&macros=current&itemId={f['id']}"])
                    results[f['severity']['description']] += 1

    print(f"Exported High: {results['High']} Medium: {results['Medium']} Low: {results['Low']} ")
    csvoutfile.close()


def get_summary(finding):
    summary = []
    count = 0
    for data_type in finding['classificationDetails']['result']['sensitiveData']:
        summary.append(f"{data_type['category']}: {data_type['totalCount']}")
        count += data_type['totalCount']
    return("\n".join(summary), count)


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
    parser.add_argument("--filename", help="Save to filename", required=True)
    parser.add_argument("--severity", help="Filter on this severity and higher",
                        choices=['High', 'Medium', 'Low'], default='Medium')

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

    # # Sanity check region
    # if args.region:
    #     os.environ['AWS_DEFAULT_REGION'] = args.region

    # if 'AWS_DEFAULT_REGION' not in os.environ:
    #     logger.error("AWS_DEFAULT_REGION Not set. Aborting...")
    #     exit(1)

    try:
        main(args, logger)
    except KeyboardInterrupt:
        exit(1)
