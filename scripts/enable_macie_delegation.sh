#!/bin/bash

# Script to enable Delegated Admin in a payer account for all Macie Regions

MACIE_ACCOUNT=$1

if [ -z $MACIE_ACCOUNT ] ; then
	echo "Usage: $0 <account_id_of_account_to_run_macie>"
	exit 1
fi

REGIONS=`aws ec2 describe-regions --query 'Regions[].[RegionName]' --output text`
for r in $REGIONS ; do
  echo "Enabling Macie Delegated Admin in $r"
  aws macie2 enable-organization-admin-account --admin-account-id $MACIE_ACCOUNT --region $r
done