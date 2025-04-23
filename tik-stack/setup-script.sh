#!/bin/bash
# Script to set up the TIK stack and create necessary directories

# Create directories
mkdir -p grafana/provisioning/datasources
mkdir -p grafana/provisioning/dashboards

# Create InfluxDB datasource for Grafana
cat > grafana/provisioning/datasources/influxdb.yml << EOF
apiVersion: 1

datasources:
  - name: InfluxDB
    type: influxdb
    access: proxy
    url: http://influxdb:8086
    secureJsonData:
      token: mytoken
    jsonData:
      version: Flux
      organization: myorg
      defaultBucket: mybucket
      tlsSkipVerify: true
    isDefault: true
EOF

echo "Created Grafana InfluxDB datasource configuration"

# Create dashboard setup
cat > grafana/provisioning/dashboards/dashboard.yml << EOF
apiVersion: 1

providers:
  - name: 'Default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    options:
      path: /var/lib/grafana/dashboards
EOF

echo "Created Grafana dashboard provider configuration"

# Verify that docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "docker-compose is not installed. Please install it first."
    exit 1
fi

echo "Starting the TIK stack..."
docker-compose up -d

echo "Waiting for services to initialize..."
sleep 10

echo "Stack is now running!"
echo "Access Grafana at: http://localhost:3000 (admin/adminpassword)"
echo "Access InfluxDB at: http://localhost:8086 (admin/adminpassword)"
echo "Access Kapacitor at: http://localhost:9092"

echo "To view logs, run: docker-compose logs -f"
echo "To stop the stack, run: docker-compose down"