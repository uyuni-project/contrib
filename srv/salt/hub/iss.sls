
register_slave:
  cmd.script:
    - name: salt://hub/register_slave.py
    - template: jinja
    - args: "{{ salt['pillar.get']('hub:server_username') }} {{ salt['pillar.get']('hub:server_password') }} {{ salt['pillar.get']('hub:iss_master') }} {{ grains.get('fqdn') }}"

register_master:
  cmd.script:
    - name: salt://hub/register_master.py
    - template: jinja
    - args: "{{ salt['pillar.get']('hub:server_username') }} {{ salt['pillar.get']('hub:server_password') }} {{ salt['pillar.get']('hub:iss_master') }} {{ grains.get('fqdn') }}"
    - require:
      - cmd: register_slave

update_ca_truststore:
  cmd.run:
    - name: ln -s /srv/www/htdocs/pub/RHN-ORG-TRUSTED-SSL-CERT /etc/pki/trust/anchors/RHN-ORG-TRUSTED-SSL-CERT-SLAVE && /usr/sbin/update-ca-certificates


