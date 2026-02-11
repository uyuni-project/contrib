# monitoring

On special request a monitoring solution can be installed for running system_update.py (and the related group_system_update.py). 
The solution is based on running a service that will listen to a given port and write updates to a sqlite3 database.
The database is created, when not present, on starting the service.

To configure this service, perform the following steps:
- install the following packages: python3-Flask, python3-PyYAML
- make the scripts /opt/uyuni-tools/database/smtdb.py executable.
- copy the file /opt/uyuni-tools/database/smtdb.service to /etc/systemd/system. And enable the service with: systemctl enable --now smtdb.service

In /opt/uyuni-tools add the following to the configsm.yaml:
<pre>
monitoring:
  hostname: 127.0.0.1
  port: 5000
  monitoring_system_update: True
  monitoring_system_highstate: False
</pre>

Note:<br>
If 127.0.0.1 is used for hostname, only from the same host the monitoring service can be accessed. When using 0.0.0.0, the service can be accessed from any host. Alternative, the hostname can be set to the IP address or the FQDN of the host.

To remove records or get the status of the monitored hosts, curl commands can be used.
#### Get Status (GET to `/status`)

Get All Records (JSON default):
> curl http://127.0.0.1:5000/status

Get All Records in raw CSV format:
> curl http://127.0.0.1:5000/status?output=raw

Get All Records in text format:
> curl http://127.0.0.1:5000/status?output=text

Get All Running Hosts (Text output):
> curl "http://127.0.0.1:5000/status?status=running&output=text"

Get Specific Hostname (JSON):
> curl "http://127.0.0.1:5000/status?hostname=db-prod-02"

Get Hosts with Wildcard (Raw/CSV output):
> curl "http://127.0.0.1:5000/status?hostname=web*&output=raw"

#### Delete Records (DELETE to `/records`)

Delete All Error Records:
>curl -X DELETE "http://127.0.0.1:5000/records?status=error"

Delete a Specific Host:
> curl -X DELETE "http://127.0.0.1:5000/records?hostname=db-prod-02"

Delete All Records (No filters):
> curl -X DELETE http://127.0.0.1:5000/records





