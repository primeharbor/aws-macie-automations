#!/usr/bin/env python3

#
# Configure Macie in the Delegated Admin account & add and enable all org members
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

    # We need a list of all accounts. Like GuardDuty we need to pass in the root email
    accounts = list_accounts()
    # we can't add ourselves to ourself, so get this account id to ignore later
    my_account_id = get_my_account_id()

    # Macie is a regional service
    if args.region:
        regions = [args.region]
    else:
        regions = get_regions()

    for r in regions:
        logger.info(f"Processing region {r}")
        macie_client = boto3.client('macie2', region_name=r)

        response = macie_client.describe_organization_configuration()
        if response['autoEnable'] is False:
            if args.actually_do_it:
                logger.info(f"Auto Enabling new accounts in {r}")
                macie_client.update_organization_configuration(autoEnable=True)
            else:
                logger.info(f"Need to autoEnable new accounts in {r}")

        # Configure the output bucket
        logger.info(f"Applying export configuration {args.bucket} w/ {args.KMSKey} in {r}")
        response = macie_client.put_classification_export_configuration(
            configuration={
                's3Destination': {
                    'bucketName': args.bucket,
                    'keyPrefix': f"{r}/",
                    'kmsKeyArn': args.KMSKey
                }
            }
        )

        # Get the list of active members
        current_members = get_members(macie_client)

        # Now to add all members
        for a in accounts:
            if a['Id'] == my_account_id:
                # I can't process myself
                continue

            # idempotency!
            if a['Id'] in current_members:
                continue

            # Organizations returns SUSPENDED account too
            if a['Status'] != "ACTIVE":
                continue

            if args.actually_do_it:
                logger.info(f"Adding {a['Id']} to Macie in {r}")
                response = macie_client.create_member(account={'accountId': a['Id'], 'email': a['Email']})
            else:
                logger.info(f"Need to add {a['Id']} to Macie in {r}")


def get_members(client):
    # Return the list of active macie members. These accounts we don't need to enable
    output = []
    response = client.list_members(maxResults=50)
    for a in response['members']:
        if a['relationshipStatus'] == "Enabled":
            output.append(a['accountId'])
        else:
            logger.warning(f"Account {a['accountId']} is status {a['relationshipStatus']}")

    while 'nextToken' in response:
        response = client.list_members(maxResults=50, nextToken=response['nextToken'])
        for a in response['members']:
            if a['relationshipStatus'] == "Enabled":
                output.append(a['accountId'])
            else:
                logger.warning(f"Account {a['accountId']} is status {a['relationshipStatus']}")

    return(output)


def get_my_account_id():
    client = boto3.client('sts')
    response = client.get_caller_identity()
    return(response['Account'])


def list_accounts():
    # A Delegated Admin account has this permission to call organizations:list_accounts()
    client = boto3.client('organizations')
    output = []
    response = client.list_accounts(MaxResults=20)
    while 'NextToken' in response:
        output = output + response['Accounts']
        time.sleep(1)
        response = client.list_accounts(MaxResults=20, NextToken=response['NextToken'])

    output = output + response['Accounts']
    return(output)


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
    parser.add_argument("--actually-do-it", help="Enable existing detector in Delegated Admin", action='store_true')
    parser.add_argument("--account-list", help="Only Process this file of accounts")
    parser.add_argument("--region", help="Only Process this region")
    parser.add_argument("--bucket", help="Bucket to Push Findings to", required=True)
    parser.add_argument("--KMSKey", help="KMS Key Arn to encrypt the findings", required=True)
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
