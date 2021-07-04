# aws-macie-automations
Scripts and Lambda to manage AWS Macie


## Scripts

* **enable_macie.py** - Run this script once to configure the Delegated Admin account for Macie. Run again if you need to configure new regions
* **get_macie_estimated_cost.py** - This script will provide a cost estimate for a specific bucket, or for all the public buckets. *Run this before creating a scan job*
* **create_scan_job.py** - This script will create either a one-time job or a weekly job for a specific bucket or all public buckets. Weekly jobs will only scan newly added or updated objects, so a one-time job should be run first.
* **findings_by_bucket.py** - Get stats on findings for a specific bucket or all buckets.
* **list_classification_jobs.py** - pull status of all classification jobs
* **get_macie_actual_cost.py** - Get the costs from the Macie service for either the month to date or past 30 days


Every script has the option to call it with `--help` to see arguments. As an explicit safety mechanism, both `enable_macie.py` and `create_scan_job.py` require you to pass the argument `--actually-do-it` before it will enable macie or create a job.