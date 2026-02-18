# import_suma_data.py
  This script can be used to import user, system-group or repositories into an MLM System. 
  Normally this will be used when creating a new MLM based on another installation. Only 1 option can be used at a time.  

Arguments:
----------
* -f FILE, --file FILE → The required input file path.
* -g, --group → Operate on a group. Create the input file with:
>  for x in \$(spacecmd -q -- group_list);do spacecmd -q -- group_details $x;echo;done > groups.txt
* -u, --user → Operate on a user. Create the input file with:
>  for x in \$(spacecmd -q -- user_list);do spacecmd -q -- user_details $x;echo;done > users.txt
* -r, --repo → Operate on a repository. Create the input file with:
>  for x in \$(spacecmd -q -- repo_list);do spacecmd -q -- repo_details $x;echo;done > repos.txt
* --version → show program's version number and exit

