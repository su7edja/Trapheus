import os
import random
import string

import boto3

import constants


def lambda_export_rds_snapshot_to_s3(event, context):
    """start export task of RDS snapshot to S3 bucket"""
    region = os.environ['Region']
    rds = boto3.client('rds', region)
    result = {}
    instance_id = event['identifier']
    random_str_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    export_id = instance_id + "-" + random_str_id
    snapshot_id = instance_id + constants.SNAPSHOT_POSTFIX
    is_cluster = event.get('isCluster')
    snapshot_arn = get_snapshot_arn(snapshot_id, is_cluster)
    account_id = __get_aws_account_id()
    bucket_name = constants.RDS_SNAPSHOTS_BUCKET_NAME_PREFIX + account_id
    try:
        response = rds.start_export_task(
            ExportTaskIdentifier=export_id,
            SourceArn=snapshot_arn,
            S3BucketName=bucket_name,
            IamRoleArn=os.environ['SNAPSHOT_EXPORT_TASK_ROLE'],
            KmsKeyId=os.environ['SNAPSHOT_EXPORT_TASK_KEY'],
        )
        result['taskname'] = constants.EXPORT_SNAPSHOT
        result['identifier'] = instance_id
        result['status'] = response['Status']
        return result
    except Exception as error:
        raise Exception(error)


def get_snapshot_arn(snapshot_name, is_cluster):
    """returns snapshot arn if in available state"""
    region = os.environ['Region']
    rds = boto3.client('rds', region)
    if is_cluster:
        snapshots_response = rds.describe_db_cluster_snapshots(DBClusterSnapshotIdentifier=snapshot_name)
        assert snapshots_response['ResponseMetadata'][
                   'HTTPStatusCode'] == 200, f"Error fetching cluster snapshots: {snapshots_response}"
        snapshots = snapshots_response['DBClusterSnapshots']
        assert len(snapshots) == 1, f"More than one snapshot matches name {snapshot_name}"
        snap = snapshots[0]
        snap_arn = snap['DBClusterSnapshotArn']
    else:
        snapshots_response = rds.describe_db_snapshots(DBSnapshotIdentifier=snapshot_name)
        assert snapshots_response['ResponseMetadata'][
                   'HTTPStatusCode'] == 200, f"Error fetching DB snapshots: {snapshots_response}"
        snapshots = snapshots_response['DBSnapshots']
        assert len(snapshots) == 1, f"More than one snapshot matches name {snapshot_name}"
        snap = snapshots[0]
        snap_arn = snap['DBSnapshotArn']  # arn is available even in creating state

    snap_status = snap.get('Status')
    if snap_status == 'available':
        return snap_arn
    else:
        raise Exception(f"Snapshot is not available yet, status is {snap_status}")


def __get_aws_account_id():
    return boto3.client('sts').get_caller_identity().get('Account')
