uyunihub_wait_for_tomcat:
  http.wait_for_successful_query:
    - method: GET
    - name: https://localhost/
    - verify_ssl: False
    - status: 200

uyunihub_create_first_user:
  http.wait_for_successful_query:
    - method: POST
    - name: https://localhost/rhn/newlogin/CreateFirstUser.do
    - status: 200
    - data: "submitted=true&\
             orgName={{ salt['pillar.get']('hub:hub_org') }}&\
             login={{ salt['pillar.get']('hub:server_username') }}&\
             desiredpassword={{ salt['pillar.get']('hub:server_password') }}&\
             desiredpasswordConfirm={{ salt['pillar.get']('hub:server_password') }}&\
             email=galaxy-noise%40suse.de&\
             firstNames=Administrator&\
             lastName=Administrator"
    - verify_ssl: False
    - unless: satwho | grep -x {{ salt['pillar.get']('hub:server_username') }}
    - require:
      - http: uyunihub_wait_for_tomcat

# set password in case user already existed with a different password
uyunihub_first_user_set_password:
  cmd.run:
    - name: echo -e "{{ salt['pillar.get']('hub:server_password') }}\n{{ salt['pillar.get']('hub:server_password') }}" | satpasswd -s {{ salt['pillar.get']('hub:server_username') }}
    - require:
      - http: uyunihub_create_first_user

uyunihub_sshkey_hubmaster:
  ssh_auth.present:
    - user: root
    - enc: ssh-rsa
    - names:
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDlaH9o2ZNx6yKm0SiuxnTiNeeNhT8hZgiHciUqcO9UEkykq03pk1q676A9C8VQCkLKgPiZx7OLDrekaNQMwT5gTTIAMmJRWRLGM2H6Q6ha3C3qzBekPj5u7xtnB2cEl4oeE6PTme08UQ2gyT26DRhj5TYxT9NqQzhLm6yNusF5HkU+g8XnDKPk4xJynazBndy0wz22UDVtYHiuxfzCk9mx7OS4LJO/hmi5TSmKJGSpNXNDBnB3BZR5KJ6qRHMvMKp4Mor36qKzLQQU5VqA7IoQY3rg2aG6EZgpumD8ihr2CONXHbrjlw2qxSmP7/MoocHyxJm9T7UREPh+0cSmrnXFYukhp3saw5JoAjVoYkIpno82kCypO0dPvDXSdaXk4nTT5GTi872/1u+e6tEfvGajC9jszfuBwl6G8Crn7abYNAdjtXKbQPphSCxpQGulpLKXasj4574uDMSpFTQjhmhfrtdvNkEWkE/Mt1VFd5MQWqF7HcNGGnzrPGHON39T9s8= root@hubmaster

uyunihub_opt_uyunihub_dir_exist:
  file.directory:
    - name: /opt/uyunihub
    - user: root
    - group: root
    - dir_mode: 750
    - file_mode: 640

uyunihub_uyunihub_yaml_file:
  file.managed:
    - name: /opt/uyunihub/uyunihub.yaml
    - uid: root
    - gid: root
    - mode: 640
    - require:
      - http: uyunihub_create_first_user
      - file: uyunihub_opt_uyunihub_dir_exist
    - create: True
    - contents: |
        server:
          hubmaster: {{ salt['pillar.get']('mgr_server') }}
          user: {{ salt['pillar.get']('hub:server_username') }}
          password: {{ salt['pillar.get']('hub:server_password') }}
        
        all:
          basechannels:
        {%- for channel in salt['pillar.get']('hub:channels_all') %}
            - {{ channel.basechannel }}
        {%- endfor %}
          projects:
        {%- for project in salt['pillar.get']('hub:projects_all') %}
            - {{ project.project }}
        {%- endfor %}
          configchannels:
        {%- for channel in salt['pillar.get']('hub:config_all') %}
            - {{ channel.configchannel }}
        {%- endfor %}
        
        {%- for item in salt['pillar.get']('hub:slave') %}
        
        {{ item.slave }}:
          basechannels:
        {%- for channel in item.channels %}
            - {{ channel.basechannel }}
        {%- endfor %}
          configchannels:
        {%- for channel in item.config %}
            - {{ channel.configchannel }}
        {%- endfor %}
          projects:
        {%- for channel in item.projects %}
            - {{ channel.project }}
        {%- endfor %}
        {%- endfor %} 
        
uyunihub_register_slave_py:
  file.managed:
    - name: /opt/uyunihub/register_slave.py
    - uid: root
    - gid: root
    - mode: 740
    - require:
      - file: uyunihub_opt_uyunihub_dir_exist
      - file: uyunihub_uyunihub_yaml_file
    - create: True
    - source: salt://uyunihub/register_slave.py
    
uyunihub_update_config_channels_py:
  file.managed:
    - name: /opt/uyunihub/update_config_channels.py
    - uid: root
    - gid: root
    - mode: 740
    - require:
      - file: uyunihub_opt_uyunihub_dir_exist
      - file: uyunihub_uyunihub_yaml_file
    - create: True
    - source: salt://uyunihub/update_config_channels.py

uyunihub_cron_d_update_config_channels:
  file.managed:
    - name: /etc/cron.d/update_config_channels
    - uid: root
    - gid: root
    - mode: 740
    - require:
      - file: uyunihub_opt_uyunihub_dir_exist
      - file: uyunihub_update_config_channels_py
    - create: True
    - contents: |
        # Activity reports every 10 minutes everyday
        10 05 * * * root cd /opt/uyunihub && ./update_config_channels.py

uyunihub_sync_software_py:
  file.managed:
    - name: /opt/uyunihub/sync_software.py
    - uid: root
    - gid: root
    - mode: 740
    - require:
      - file: uyunihub_opt_uyunihub_dir_exist
      - file: uyunihub_uyunihub_yaml_file
    - create: True
    - source: salt://uyunihub/sync_software.py

{% if not "joined" in grains.get('hub_joined','Undef') %}
uyunihub_master_ca:
  file.managed:
    - name: /etc/pki/trust/anchors/RHN-ORG-TRUSTED-SSL-CERT-master
    - uid: root
    - gid: root
    - mode: 740
    - create: True
    - skip_verify: True
    - source: http://{{ salt['pillar.get']('mgr_server') }}/pub/RHN-ORG-TRUSTED-SSL-CERT

uyunihub_update_ca_certificates_master_ca:
  cmd.script:
    - name: /usr/sbin/update-ca-certificates
    - require:
      - file: uyunihub_master_ca

uyunihub_register_slave_run_script:
  cmd.script:
    - name: /opt/uyunihub/register_slave.py
    - cwd: /opt/uyunihub
    - require:
      - cmd: uyunihub_update_ca_certificates_master_ca
      - file: uyunihub_register_slave_py
      - file: uyunihub_uyunihub_yaml_file

set_grains_hub_joined:
    grains.present:
        - name: hub_joined
        - value: joined
        - require:
            - cmd: uyunihub_register_slave_run_script
{% endif %}

uyunihub_sync_software_run_script:
  cmd.run:
    - name: /opt/uyunihub/sync_software.py
    - cwd: /opt/uyunihub
    - bg: True
    - require:
      - file: uyunihub_uyunihub_yaml_file

uyunihub_update_configuration_channels_run_script:
  cmd.run:
    - name: /opt/uyunihub/update_config_channels.py
    - cwd: /opt/uyunihub
    - bg: True
    - require:
      - file: uyunihub_uyunihub_yaml_file
