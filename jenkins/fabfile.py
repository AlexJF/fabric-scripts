#!/usr/bin/env python2
# encoding: utf-8

# Author: Alexandre Fonseca
# Description:
#   Installs Jenkins master and slave nodes.
#
#   Jenkins will be installed on /var/lib/jenkins with
#   user 'jenkins' on the master node. A new user 'jenkins'
#   will be created on the slaves and all jenkins content
#   will go to its home dir, /home/jenkins (root directory
#   of the slave when you configure it on Jenkin's web UI)
#
#   Jenkins slave nodes will accept connections from the
#   master node so slaves can be configured automatically
#   via SSH from the Master node.
#
# Note:
#   Script only works on Debian-based distros with apt-get.
#   If you want to make it work on other distros, you'll
#   have to dive into the DON'T CHANGE section but it shouldn't
#   be too hard.

from fabric.api import run, cd, env, settings, put, sudo

###############################################################
#  START OF YOUR CONFIGURATION (CHANGE FROM HERE, IF NEEDED)  #
###############################################################
JENKINS_HTTP_PORT = -1
JENKINS_HTTPS_PORT = 8080

JENKINS_PLUGIN_DOWNLOAD_URL = "http://updates.jenkins-ci.org/latest"

# Any extra plugins that you want to install initially
JENKINS_EXTRA_PLUGINS = ["thinBackup"]

# Change these to point to local Jenkins master keys to be
# used in this installation.
JENKINS_MASTER_PRIVATE_KEY = "id_rsa"
JENKINS_MASTER_PUBLIC_KEY = "id_rsa.pub"

# You can either set these here or pass them on execution with
# fab -H<master host>,<slave1 host>,<slave2 host>
JENKINS_MASTER_HOST = None
JENKINS_SLAVE_HOSTS = []

# Packages needed to run basic 32 bit applications in 64 bits 
# Debian/Ubuntu
DEBIAN_32_COMPAT = ["libc6-i386", "lib32stdc++6", "lib32gcc1", 
    "lib32ncurses5", "lib32z1"]
# Packages that should be installed on the master host
MASTER_REQUIREMENTS = ["openjdk-7-jre-headless", "git"] + DEBIAN_32_COMPAT
# Packages that should be installed on the slave hosts
SLAVE_REQUIREMENTS = ["openjdk-7-jre-headless", "git", "php5", "php5-json", 
    "ant"] + DEBIAN_32_COMPAT
##############################################################
#  END OF YOUR CONFIGURATION (CHANGE UNTIL HERE, IF NEEDED)  #
##############################################################

#####################################################################
#  DON'T CHANGE ANYTHING BELOW (UNLESS YOU KNOW WHAT YOU'RE DOING)  #
#####################################################################
PACKAGE_MANAGER_INSTALL = "apt-get install %s"
PACKAGE_MANAGER_UPDATE = "apt-get update"

# Debian/Ubuntu
# If no hosts provided via the argument, try using
# hardcoded ones
if not env.hosts:
    env.hosts = [JENKINS_MASTER_HOST] + JENKINS_SLAVE_HOSTS

# If no hardcoded hosts, quit
if not env.hosts:
    raise Exception("No hosts specified")

JENKINS_MASTER_HOST = env.hosts[0]

# Main functions
def setup():
    setupMaster()
    setupSlave()

def setupMaster():
    if env.host == JENKINS_MASTER_HOST:
        print("+ Setting up Master")
        installMasterDependencies()
        installJenkins()
        installJenkinsPlugins(JENKINS_EXTRA_PLUGINS)
        installJenkinsMasterSSHKeys()
        print("+ Master setup")

def setupSlave():
    if env.host in JENKINS_SLAVE_HOSTS:
        print("+ Setting up Slave")
        installSlaveDependencies()
        addJenkinsUser()
        allowJenkinsMasterSSHKeys()
        disableSSHStrictKeyChecking()
        print("+ Slave setup")

# HELPER FUNCTIONS
def installJenkins():
    print("+ Installing Jenkins")
    sudo("wget -q -O - http://pkg.jenkins-ci.org/debian/jenkins-ci.org.key | apt-key add -")
    sudo("sh -c \"echo 'deb http://pkg.jenkins-ci.org/debian binary/' > /etc/apt/sources.list.d/jenkins.list\"")
    sudo(PACKAGE_MANAGER_UPDATE)
    sudo(PACKAGE_MANAGER_INSTALL % "jenkins")
    changeIniStyleConfig("/etc/default/jenkins", {
        "HTTP_PORT": JENKINS_HTTP_PORT,
        "HTTPS_PORT": JENKINS_MASTER_PORT,
        }, True)
    sudo("/etc/init.d/jenkins restart")

def installJenkinsPlugins(plugins):
    print("+ Installing Jenkins Plugins")
    with settings(warn_only=True):
        if run("test -d /var/lib/jenkins/plugins").failed:
            sudo("mkdir -p /var/lib/jenkins/plugins")
            sudo("chown jenkins /var/lib/jenkins/plugins")
    with cd("/var/lib/jenkins/plugins"):
        for plugin in plugins:
            sudo("wget %s/%s.hpi" % (JENKINS_PLUGIN_DOWNLOAD_URL, plugin))
    print("+ Jenkins plugins installed")

def changeIniStyleConfig(fileName, variables, useSudo=False):
    global run 
    run = run

    if useSudo:
        run = sudo

    for variable, value in variables.items():
        lineNumber = run("grep -n '^%(var)s\s*\=' '%(file)s' | cut -d : -f 1" %
                {"var": variable, "file": fileName})
        try:
            lineNumber = int(lineNumber)
            run("sed -i \"" + str(lineNumber) + "s/.*/%(var)s\=%(val)s/\" '%(file)s'" % 
                {"var": variable, "val": value, "file": fileName})
        except ValueError:
            run("echo \"%(var)s=%(val)s\" >> \"%(file)s\"" % 
                {"var": variable, "val": str(value), "file": fileName})

def installJenkinsMasterSSHKeys():
    print("+ Setting up Jenkins master SSH keys")
    with cd("/var/lib/jenkins/"):
        with settings(warn_only=True):
            if run("test -d .ssh").failed:
                sudo("mkdir -p .ssh")
        put(JENKINS_MASTER_PRIVATE_KEY, ".ssh/id_rsa", use_sudo=True)
        put(JENKINS_MASTER_PUBLIC_KEY, ".ssh/id_rsa.pub", use_sudo=True)
        sudo("chmod 0700 .ssh/id_rsa")
        sudo("chown -R jenkins .ssh")
    print("+ Jenkins master SSH keys setup")

def allowJenkinsMasterSSHKeys():
    print("+ Allowing Jenkins master SSH keys on Slave")
    with cd("/home/jenkins"):
        with settings(warn_only=True):
            if run("test -d .ssh").failed:
                sudo("mkdir -p .ssh")
    with cd("/home/jenkins/.ssh"):
        put(JENKINS_MASTER_PUBLIC_KEY, "jenkins_master.pub", use_sudo=True)
        sudo("cat jenkins_master.pub >> authorized_keys")

def disableSSHStrictKeyChecking():
    with cd("/home/jenkins/.ssh"):
        sudo("echo 'StrictHostKeyChecking no' > config")

def addJenkinsUser():
    sudo("useradd -m -s /usr/sbin/nologin jenkins")
