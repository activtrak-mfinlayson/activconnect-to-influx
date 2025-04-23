
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

gcloud init
gcloud auth application-default login
gcloud auth list



python bq-to-influxdb.py \
  --project-id activtrak-com-214616 \
  --dataset-id 567556 \
  --table-name logsV2 \
  --influx-url http://localhost:8086 \
  --influx-token vtiHBXdkHCRHSOzJmksqDJkxN4nhfFAIr6ss6rrts0L4rnVQQ3v6ZLiK8Qp3e_IwzQ8AuIwN_n_dGJsAuM-LVA== \
  --influx-org myorg \
  --influx-bucket mybucket \
  --batch-size 1000 \
  --start-date 2025-01-01