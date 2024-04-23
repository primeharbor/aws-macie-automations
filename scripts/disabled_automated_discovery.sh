#!/bin/bash

# Script to enable Delegated Admin in a payer account for all Macie Regions

REGIONS=`aws ec2 describe-regions --query 'Regions[].[RegionName]' --output text`
for r in $REGIONS ; do
  echo "Disabling Macie Automated Discovery in $r"
  aws macie2 update-automated-discovery-configuration  --region $r --status DISABLED
done
