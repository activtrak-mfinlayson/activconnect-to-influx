#!/usr/bin/env python3
"""
Script to migrate data from BigQuery to InfluxDB.
Requires: google-cloud-bigquery, influxdb-client packages
"""

import os
import argparse
from datetime import datetime, timezone
from google.cloud import bigquery
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Migrate data from BigQuery to InfluxDB')
    parser.add_argument('--project-id', required=True,
                        help='BigQuery project ID')
    parser.add_argument('--dataset-id', required=True,
                        help='BigQuery dataset ID')
    parser.add_argument('--table-name', required=True,
                        help='BigQuery table name')
    parser.add_argument('--bq-credentials',
                        help='Path to BigQuery credentials JSON file')
    parser.add_argument('--influx-url', required=True, help='InfluxDB URL')
    parser.add_argument('--influx-token', required=True,
                        help='InfluxDB API token')
    parser.add_argument('--influx-org', required=True,
                        help='InfluxDB organization')
    parser.add_argument('--influx-bucket', required=True,
                        help='InfluxDB bucket')
    parser.add_argument('--batch-size', type=int, default=1000,
                        help='Number of records to process in each batch')
    parser.add_argument('--limit', type=int,
                        help='Limit the number of rows to process')
    parser.add_argument(
        '--start-date', help='Start date for filtering (YYYY-MM-DD)')
    parser.add_argument(
        '--end-date', help='End date for filtering (YYYY-MM-DD)')
    return parser.parse_args()


def configure_bigquery_client(args):
    """Configure and return a BigQuery client."""
    if args.bq_credentials:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = args.bq_credentials
    return bigquery.Client(project=args.project_id)


def configure_influxdb_client(args):
    """Configure and return an InfluxDB client."""
    return InfluxDBClient(
        url=args.influx_url,
        token=args.influx_token,
        org=args.influx_org
    )


def build_query(args):
    """Build the BigQuery SQL query."""
    query = f"SELECT * FROM `{args.project_id}.{args.dataset_id}.{args.table_name}`"

    # Add date filtering if provided
    conditions = []
    if args.start_date:
        conditions.append(f"time >= TIMESTAMP('{args.start_date}')")
    if args.end_date:
        conditions.append(f"time <= TIMESTAMP('{args.end_date}')")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # Order by time for consistent batch processing
    query += " ORDER BY time"

    # Add limit if provided
    if args.limit:
        query += f" LIMIT {args.limit}"

    return query


def row_to_point(row):
    """Convert a BigQuery row to InfluxDB Point."""
    # Use 'time' as the timestamp field if it exists, otherwise use current time
    timestamp = row.get('time')
    if not timestamp:
        timestamp = datetime.now(timezone.utc)

    # Determine the measurement name based on URL or application name
    measurement = row.get('log_url') or row.get('executable', 'unknown')
    if measurement:
        # Clean up the measurement name to be InfluxDB friendly
        measurement = measurement.replace(
            ' ', '_').replace('/', '_').replace('\\', '_')
        measurement = measurement[:100]  # Limit length to 100 characters

    # Create a point
    point = Point(measurement)

    # Set key fields as tags
    if row.get('useralias'):
        point.tag("useralias", str(row.get('useralias')))
    if row.get('computer'):
        point.tag("computer", str(row.get('computer')))
    if row.get('accountid'):
        point.tag("accountid", str(row.get('accountid')))
    if row.get('productivity'):
        point.tag("productivity", str(row.get('productivity')))
    if row.get('category'):
        point.tag("category", str(row.get('category')))
    if row.get('active_state'):
        point.tag("active_state", str(row.get('active_state')))

    # Add duration as the main measurement value
    if row.get('duration') is not None:
        point.field("duration", int(row.get('duration')))

    # Add additional fields that might be useful
    if row.get('productivity'):
        point.field("productivity", str(row.get('productivity')))
    if row.get('category'):
        point.field("category", str(row.get('category')))
    if row.get('active_state'):
        point.field("active_state", str(row.get('active_state')))
    if row.get('titlebar'):
        point.field("titlebar", str(row.get('titlebar')))

    # Set the timestamp
    point.time(timestamp, WritePrecision.NS)

    return point


def process_batch(rows, write_api, bucket):
    """Process a batch of rows and write to InfluxDB."""
    points = []
    for row in rows:
        row_dict = dict(row.items())
        points.append(row_to_point(row_dict))

    write_api.write(bucket=bucket, record=points)
    return len(points)


def migrate_data(args):
    """Migrate data from BigQuery to InfluxDB."""
    # Configure clients
    bq_client = configure_bigquery_client(args)
    influx_client = configure_influxdb_client(args)
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    # Drop and recreate the bucket
    buckets_api = influx_client.buckets_api()
    try:
        # Try to delete the bucket if it exists
        bucket = buckets_api.find_bucket_by_name(args.influx_bucket)
        if bucket:
            print(f"Deleting existing bucket: {args.influx_bucket}")
            buckets_api.delete_bucket(bucket)
    except Exception as e:
        print(f"Error deleting bucket: {e}")

    # Create new bucket
    print(f"Creating new bucket: {args.influx_bucket}")
    retention_rules = [{
        "type": "expire",
        "everySeconds": 0,  # 0 means infinite retention
    }]
    buckets_api.create_bucket(bucket_name=args.influx_bucket,
                              org=args.influx_org,
                              retention_rules=retention_rules)

    # Build and execute query
    query = build_query(args)
    print(f"Executing query: {query}")

    query_job = bq_client.query(query)

    # Process rows in batches
    rows = []
    total_rows = 0
    for row in query_job:
        rows.append(row)

        if len(rows) >= args.batch_size:
            processed = process_batch(rows, write_api, args.influx_bucket)
            total_rows += processed
            print(f"Processed {processed} rows. Total: {total_rows}")
            rows = []

    # Process remaining rows
    if rows:
        processed = process_batch(rows, write_api, args.influx_bucket)
        total_rows += processed
        print(f"Processed {processed} rows. Total: {total_rows}")

    print(f"Migration complete. Total rows processed: {total_rows}")

    # Clean up
    write_api.close()
    influx_client.close()


def main():
    args = parse_args()
    migrate_data(args)


if __name__ == "__main__":
    main()
