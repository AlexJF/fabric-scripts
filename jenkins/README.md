# Jenkins Fabric Management Script

This script installs all packages needed for running Jenkins master and slave
nodes. Check the top of the script for configuration variables and change
them to your liking.

Master can control slave nodes via SSH. thinBackup plugin is automatically
installed by default for easy configuration and plugin restore.

Slave nodes configuration can be added by going to the Jenkins web UI
and adding slaves with the following settings:

* Remote FS root: /home/jenkins
* Launch method: Launch slave agents on Unix machines via SSH
* Host: <slave host>
* Credentials: SSH private key credentials for user 'jenkins'
