#!/usr/bin/env python2
# encoding: utf-8

# Author: Alexandre Fonseca
# Description:
#   Installs, configures and manages Hadoop on a set of nodes
#   in a cluster.
# Associated guide:
#   http://www.alexjf.net/blog/distributed-systems/hadoop-yarn-installation-definitive-guide

import os
from fabric.api import run, cd, env, settings, put, sudo
from fabric.decorators import runs_once, parallel
from fabric.tasks import execute

###############################################################
#  START OF YOUR CONFIGURATION (CHANGE FROM HERE, IF NEEDED)  #
###############################################################

#### Generic ####
SSH_USER = "ubuntu"
# If you need to specify a special ssh key, do it here (e.g EC2 key)
#env.key_filename = "~/.ssh/giraph.pem"


#### EC2 ####
# Is this an EC2 deployment? If so, then we'll autodiscover the right nodes.
EC2 = False
EC2_REGION = "eu-west-1"
# In case this is an EC2 deployment, all cluster nodes must have a tag with
# 'Cluster' as key and the following property as value.
EC2_CLUSTER_NAME = "rtgiraph"
# Should ResourceManager participate in job execution (also be a slave node?)
EC2_RM_NONSLAVE = True
# Read AWS access key details from env if available
AWS_ACCESSKEY_ID = os.getenv("AWS_ACCESSKEY_ID", "undefined")
AWS_ACCESSKEY_SECRET = os.getenv("AWS_ACCESSKEY_SECRET", "undefined")
# In case the instances you use have an extra storage device which is not
# automatically mounted, specify here the path to that device.
EC2_INSTANCE_STORAGEDEV = None
#EC2_INSTANCE_STORAGEDEV = "/dev/xvdb" For Ubuntu r3.xlarge instances


#### Package Information ####
HADOOP_VERSION = "2.4.0"
HADOOP_PACKAGE = "hadoop-%s" % HADOOP_VERSION
#HADOOP_PACKAGE_URL = "http://apache.mirrors.spacedump.net/hadoop/common/stable/%s.tar.gz" % HADOOP_PACKAGE
HADOOP_PACKAGE_URL = "http://www.whoishostingthis.com/mirrors/apache/hadoop/common/%(hadoop)s/%(hadoop)s.tar.gz" % {'hadoop': HADOOP_PACKAGE}
HADOOP_PREFIX = "/home/ubuntu/Programs/%s" % HADOOP_PACKAGE
HADOOP_CONF = os.path.join(HADOOP_PREFIX, "etc/hadoop")


#### Installation information ####
# Change this to the command you would use to install packages on the
# remote hosts.
PACKAGE_MANAGER_INSTALL = "apt-get -qq install %s" # Debian/Ubuntu
#PACKAGE_MANAGER_INSTALL = "pacman -S %s" # Arch Linux
#PACKAGE_MANAGER_INSTALL = "yum install %s" # CentOS

# Change this list to the list of packages required by Hadoop
# In principle, should just be a JRE for Hadoop, Python
# for the Hadoop Configuration replacement script and wget
# to get the Hadoop package
REQUIREMENTS = ["wget", "python", "openjdk-7-jre-headless"] # Debian/Ubuntu
#REQUIREMENTS = ["wget", "python", "jre7-openjdk-headless"] # Arch Linux
#REQUIREMENTS = ["wget", "python", "java-1.7.0-openjdk-devel"] # CentOS

# Commands to execute (in order) before installing listed requirements
# (will run as root). Use to configure extra repos or update repos
REQUIREMENTS_PRE_COMMANDS = []

# If you want to install Oracle's Java instead of using the OpenJDK that
# comes preinstalled with most distributions replace the previous options
# with a variation of the following: (UBUNTU only)
#REQUIREMENTS = ["wget", "python", "oracle-java7-installer"] # Debian/Ubuntu
#REQUIREMENTS_PRE_COMMANDS = [
    #"add-apt-repository ppa:webupd8team/java -y",
    #"apt-get -qq update",
    #"echo debconf shared/accepted-oracle-license-v1-1 select true | debconf-set-selections",
    #"echo debconf shared/accepted-oracle-license-v1-1 seen true | debconf-set-selections",
#]


#### Environment ####
# Set this to True/False depending on whether or not ENVIRONMENT_FILE
# points to an environment file that is automatically loaded in a new
# shell session
ENVIRONMENT_FILE_NOTAUTOLOADED = False
ENVIRONMENT_FILE = "/home/ubuntu/.bashrc"
#ENVIRONMENT_FILE_NOTAUTOLOADED = True
#ENVIRONMENT_FILE = "/home/ubuntu/hadoop2_env.sh"

# Should the ENVIRONMENT_VARIABLES be applies to a clean (empty) environment
# file or should they simply be merged (only additions and updates) into the
# existing environment file? In any case, the previous version of the file
# will be backed up.
ENVIRONMENT_FILE_CLEAN = False
ENVIRONMENT_VARIABLES = [
    ("JAVA_HOME", "/usr/lib/jvm/java-7-openjdk-amd64"), # Debian/Ubuntu 64 bits
    #("JAVA_HOME", "/usr/lib/jvm/java-7-openjdk"), # Arch Linux
    #("JAVA_HOME", "/usr/java/jdk1.7.0_51"), # CentOS
    ("HADOOP_PREFIX", HADOOP_PREFIX),
    ("HADOOP_HOME", r"\\$HADOOP_PREFIX"),
    ("HADOOP_COMMON_HOME", r"\\$HADOOP_PREFIX"),
    ("HADOOP_CONF_DIR", r"\\$HADOOP_PREFIX/etc/hadoop"),
    ("HADOOP_HDFS_HOME", r"\\$HADOOP_PREFIX"),
    ("HADOOP_MAPRED_HOME", r"\\$HADOOP_PREFIX"),
    ("HADOOP_YARN_HOME", r"\\$HADOOP_PREFIX"),
    ("HADOOP_PID_DIR", "/tmp/hadoop_%s" % HADOOP_VERSION),
    ("YARN_PID_DIR", r"\\$HADOOP_PID_DIR"),
    ("PATH", r"\\$HADOOP_PREFIX/bin:\\$PATH"),
]


#### Host data (for non-EC2 deployments) ####
HOSTS_FILE="/etc/hosts"
NET_INTERFACE="eth0"
RESOURCEMANAGER_HOST = "resourcemanager.alexjf.net"
NAMENODE_HOST = RESOURCEMANAGER_HOST

SLAVE_HOSTS = ["slave%d.alexjf.net" % i for i in range(1, 6)]
# Or equivalently
#SLAVE_HOSTS = ["slave1.alexjf.net", "slave2.alexjf.net",
#          "slave3.alexjf.net", "slave4.alexjf.net",
#          "slave5.alexjf.net"]

# If you'll be running map reduce jobs, you should choose a host to be
# the job tracker
JOBTRACKER_HOST = SLAVE_HOSTS[0]
JOBTRACKER_PORT = 8021

# If you'll run MapReduce jobs, you might want to set a JobHistory server.
# e.g: JOBHISTORY_HOST = "jobhistory.alexjf.net"
JOBHISTORY_HOST = JOBTRACKER_HOST
JOBHISTORY_PORT = 10020


#### Configuration ####
# Should the configuration options be applied to a clean (empty) configuration
# file or should they simply be merged (only additions and updates) into the
# existing environment file? In any case, the previous version of the file
# will be backed up.
CONFIGURATION_FILES_CLEAN = False

HADOOP_TEMP = "/mnt/hadoop/tmp"
HDFS_DATA_DIR = "/mnt/hdfs/datanode"
HDFS_NAME_DIR = "/mnt/hdfs/namenode"

IMPORTANT_DIRS = [HADOOP_TEMP, HDFS_DATA_DIR, HDFS_NAME_DIR]

# Need to do this in a function so that we can rewrite the values when any
# of the hosts change in runtime (e.g. EC2 node discovery).
def updateHadoopSiteValues():
    global CORE_SITE_VALUES, HDFS_SITE_VALUES, YARN_SITE_VALUES, MAPRED_SITE_VALUES

    CORE_SITE_VALUES = {
        "fs.defaultFS": "hdfs://%s/" % NAMENODE_HOST,
        "fs.s3n.awsAccessKeyId": AWS_ACCESSKEY_ID,
        "fs.s3n.awsSecretAccessKey": AWS_ACCESSKEY_SECRET,
        "hadoop.tmp.dir": HADOOP_TEMP
    }

    HDFS_SITE_VALUES = {
        "dfs.datanode.data.dir": "file://%s" % HDFS_DATA_DIR,
        "dfs.namenode.name.dir": "file://%s" % HDFS_NAME_DIR,
        "dfs.permissions": "false",
    }

    YARN_SITE_VALUES = {
        "yarn.resourcemanager.hostname": RESOURCEMANAGER_HOST,
        "yarn.scheduler.minimum-allocation-mb": 128,
        "yarn.scheduler.maximum-allocation-mb": 1024,
        "yarn.scheduler.minimum-allocation-vcores": 1,
        "yarn.scheduler.maximum-allocation-vcores": 2,
        "yarn.nodemanager.resource.memory-mb": 4096,
        "yarn.nodemanager.resource.cpu-vcores": 4,
        "yarn.log-aggregation-enable": "true",
        "yarn.nodemanager.aux-services": "mapreduce_shuffle",
        "yarn.nodemanager.vmem-pmem-ratio": 3.1,
        "yarn.nodemanager.remote-app-log-dir": os.path.join(HADOOP_TEMP, "logs"),
        "yarn.nodemanager.log-dirs": os.path.join(HADOOP_TEMP, "userlogs"),
    }

    MAPRED_SITE_VALUES = {
        "yarn.app.mapreduce.am.resource.mb": 1024,
        "yarn.app.mapreduce.am.command-opts": "-Xmx768m",
        "mapreduce.framework.name": "yarn",
        "mapreduce.map.cpu.vcores": 1,
        "mapreduce.map.memory.mb": 1024,
        "mapreduce.map.java.opts": "-Xmx768m",
        "mapreduce.reduce.cpu.vcores": 1,
        "mapreduce.reduce.memory.mb": 1024,
        "mapreduce.reduce.java.opts": "-Xmx768m",
    }

##############################################################
#  END OF YOUR CONFIGURATION (CHANGE UNTIL HERE, IF NEEDED)  #
##############################################################

#####################################################################
#  DON'T CHANGE ANYTHING BELOW (UNLESS YOU KNOW WHAT YOU'RE DOING)  #
#####################################################################
CORE_SITE_VALUES = {}
HDFS_SITE_VALUES = {}
YARN_SITE_VALUES = {}
MAPRED_SITE_VALUES = {}

def bootstrapFabric():
    if EC2:
        readHostsFromEC2()

    updateHadoopSiteValues()

    env.user = SSH_USER
    hosts = [NAMENODE_HOST, RESOURCEMANAGER_HOST, JOBHISTORY_HOST] + SLAVE_HOSTS
    seen = set()
    # Remove empty hosts and duplicates
    cleanedHosts = [host for host in hosts if host and host not in seen and not seen.add(host)]
    env.hosts = cleanedHosts

    if JOBTRACKER_HOST:
        MAPRED_SITE_VALUES["mapreduce.jobtracker.address"] = "%s:%s" % \
            (JOBTRACKER_HOST, JOBTRACKER_PORT)

    if JOBHISTORY_HOST:
        MAPRED_SITE_VALUES["mapreduce.jobhistory.address"] = "%s:%s" % \
            (JOBHISTORY_HOST, JOBHISTORY_PORT)


# MAIN FUNCTIONS
def forceStopEveryJava():
    run("jps | grep -vi jps | cut -d ' ' -f 1 | xargs -L1 -r kill")


@runs_once
def debugHosts():
    print("Resource Manager: {}".format(RESOURCEMANAGER_HOST))
    print("Name node: {}".format(NAMENODE_HOST))
    print("Job Tracker: {}".format(JOBTRACKER_HOST))
    print("Job History: {}".format(JOBHISTORY_HOST))
    print("Slaves: {}".format(SLAVE_HOSTS))


def bootstrap():
    with settings(warn_only=True):
        if EC2_INSTANCE_STORAGEDEV and run("mountpoint /mnt").failed:
            sudo("mkfs.ext4 %s" % EC2_INSTANCE_STORAGEDEV)
            sudo("mount %s /mnt" % EC2_INSTANCE_STORAGEDEV)
            sudo("chmod 0777 /mnt")
            sudo("rm -rf /tmp/hadoop-ubuntu")
    ensureImportantDirectoriesExist()
    installDependencies()
    install()
    setupEnvironment()
    config()
    setupHosts()
    formatHdfs()


def ensureImportantDirectoriesExist():
    for importantDir in IMPORTANT_DIRS:
        ensureDirectoryExists(importantDir)


def installDependencies():
    for command in REQUIREMENTS_PRE_COMMANDS:
        sudo(command)
    for requirement in REQUIREMENTS:
        sudo(PACKAGE_MANAGER_INSTALL % requirement)


def install():
    installDirectory = os.path.dirname(HADOOP_PREFIX)
    run("mkdir -p %s" % installDirectory)
    with cd(installDirectory):
        with settings(warn_only=True):
            if run("test -f %s.tar.gz" % HADOOP_PACKAGE).failed:
                run("wget -O %s.tar.gz %s" % (HADOOP_PACKAGE, HADOOP_PACKAGE_URL))
        run("tar --overwrite -xf %s.tar.gz" % HADOOP_PACKAGE)


def config():
    changeHadoopProperties("core-site.xml", CORE_SITE_VALUES)
    changeHadoopProperties("hdfs-site.xml", HDFS_SITE_VALUES)
    changeHadoopProperties("yarn-site.xml", YARN_SITE_VALUES)
    changeHadoopProperties("mapred-site.xml", MAPRED_SITE_VALUES)


def configRevertPrevious():
    revertHadoopPropertiesChange("core-site.xml")
    revertHadoopPropertiesChange("hdfs-site.xml")
    revertHadoopPropertiesChange("yarn-site.xml")
    revertHadoopPropertiesChange("mapred-site.xml")


def setupEnvironment():
    with settings(warn_only=True):
        if not run("test -f %s" % ENVIRONMENT_FILE).failed:
            op = "cp"

            if ENVIRONMENT_FILE_CLEAN:
                op = "mv"

            currentBakNumber = getLastBackupNumber(ENVIRONMENT_FILE) + 1
            run("%(op)s %(file)s %(file)s.bak%(bakNumber)d" %
                {"op": op, "file": ENVIRONMENT_FILE, "bakNumber": currentBakNumber})

    run("touch %s" % ENVIRONMENT_FILE)

    for variable, value in ENVIRONMENT_VARIABLES:
        lineNumber = run("grep -n 'export\s\+%(var)s\=' '%(file)s' | cut -d : -f 1" %
                {"var": variable, "file": ENVIRONMENT_FILE})
        try:
            lineNumber = int(lineNumber)
            run("sed -i \"" + str(lineNumber) + "s@.*@export %(var)s\=%(val)s@\" '%(file)s'" %
                {"var": variable, "val": value, "file": ENVIRONMENT_FILE})
        except ValueError:
            run("echo \"export %(var)s=%(val)s\" >> \"%(file)s\"" %
                {"var": variable, "val": value, "file": ENVIRONMENT_FILE})


def environmentRevertPrevious():
    revertBackup(ENVIRONMENT_FILE)


def formatHdfs():
    if env.host == NAMENODE_HOST:
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/bin/hdfs namenode -format")


@runs_once
def setupHosts():
    privateIps = execute(getPrivateIp)
    execute(updateHosts, privateIps)

    if env.host == RESOURCEMANAGER_HOST:
        run("rm -f privateIps")
        run("touch privateIps")

        for host, privateIp in privateIps.items():
            run("echo '%s' >> privateIps" % privateIp)


def start():
    operationOnHadoopDaemons("start")


def stop():
    operationOnHadoopDaemons("stop")


def test():
    if env.host == RESOURCEMANAGER_HOST:
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/bin/hadoop jar \\$HADOOP_PREFIX/share/hadoop/yarn/hadoop-yarn-applications-distributedshell-%(version)s.jar org.apache.hadoop.yarn.applications.distributedshell.Client --jar \\$HADOOP_PREFIX/share/hadoop/yarn/hadoop-yarn-applications-distributedshell-%(version)s.jar --shell_command date --num_containers %(numContainers)d --master_memory 1024" %
            {"version": HADOOP_VERSION, "numContainers": len(SLAVE_HOSTS)})


def testMapReduce():
    if env.host == RESOURCEMANAGER_HOST:
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/bin/hadoop dfs -rm -f -r out")
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/bin/hadoop jar \\$HADOOP_PREFIX/share/hadoop/mapreduce/hadoop-mapreduce-examples-%s.jar randomwriter out" % HADOOP_VERSION)


# HELPER FUNCTIONS
def ensureDirectoryExists(directory):
    with settings(warn_only=True):
        if run("test -d %s" % directory).failed:
            run("mkdir -p %s" % directory)


@parallel
def getPrivateIp():
    if not EC2:
        return run("ifconfig %s | grep 'inet\s\+' | awk '{print $2}' | cut -d':' -f2" % NET_INTERFACE).strip()
    else:
        return run("wget -qO- http://instance-data/latest/meta-data/local-ipv4")


@parallel
def updateHosts(privateIps):
    with settings(warn_only=True):
        if not run("test -f %s" % HOSTS_FILE).failed:
            currentBakNumber = getLastBackupNumber(HOSTS_FILE) + 1
            sudo("cp %(file)s %(file)s.bak%(bakNumber)d" %
                {"file": HOSTS_FILE, "bakNumber": currentBakNumber})

    sudo("touch %s" % HOSTS_FILE)

    for host, privateIp in privateIps.items():
        lineNumber = run("grep -n '^%(host)s' '%(file)s' | cut -d : -f 1" %
                {"host": host, "file": HOSTS_FILE})
        try:
            lineNumber = int(lineNumber)
            sudo("sed -i \"" + str(lineNumber) + "s@.*@%(host)s %(ip)s@\" '%(file)s'" %
                {"host": host, "ip": privateIp, "file": HOSTS_FILE})
        except ValueError:
            sudo("echo \"%(host)s %(ip)s\" >> \"%(file)s\"" %
                {"host": host, "ip": privateIp, "file": HOSTS_FILE})


def getLastBackupNumber(filePath):
    dirName = os.path.dirname(filePath)
    fileName = os.path.basename(filePath)

    with cd(dirName):
        latestBak = run("ls -1 | grep %s.bak | tail -n 1" % fileName)
        latestBakNumber = -1
        if latestBak:
            latestBakNumber = int(latestBak[len(fileName) + 4:])
        return latestBakNumber


def changeHadoopProperties(fileName, propertyDict):
    if not fileName or not propertyDict:
        return

    with cd(HADOOP_CONF):
        with settings(warn_only=True):
            import hashlib
            replaceHadoopPropertyHash = \
                hashlib.md5(
                    open("replaceHadoopProperty.py", 'rb').read()
                ).hexdigest()
            if run("test %s = `md5sum replaceHadoopProperty.py | cut -d ' ' -f 1`"
                   % replaceHadoopPropertyHash).failed:
                put("replaceHadoopProperty.py", HADOOP_CONF + "/")
                run("chmod +x replaceHadoopProperty.py")

        with settings(warn_only=True):
            if not run("test -f %s" % fileName).failed:
                op = "cp"

                if CONFIGURATION_FILES_CLEAN:
                    op = "mv"

                currentBakNumber = getLastBackupNumber(fileName) + 1
                run("%(op)s %(file)s %(file)s.bak%(bakNumber)d" %
                    {"op": op, "file": fileName, "bakNumber": currentBakNumber})

        run("touch %s" % fileName)

        command = "./replaceHadoopProperty.py '%s' %s" % (fileName,
            " ".join(["%s %s" % (str(key), str(value)) for key, value in propertyDict.items()]))
        run(command)


def revertBackup(fileName):
    dirName = os.path.dirname(fileName)

    with cd(dirName):
        latestBakNumber = getLastBackupNumber(fileName)

        # We have already reverted all backups
        if latestBakNumber == -1:
            return
        # Otherwise, perform reversion
        else:
            run("mv %(file)s.bak%(bakNumber)d %(file)s" %
                {"file": fileName, "bakNumber": latestBakNumber})


def revertHadoopPropertiesChange(fileName):
    revertBackup(os.path.join(HADOOP_CONF, fileName))


def operationInHadoopEnvironment(operation):
    with cd(HADOOP_PREFIX):
        command = operation
        if ENVIRONMENT_FILE_NOTAUTOLOADED:
            with settings(warn_only=True):
                import hashlib
                executeInHadoopEnvHash = \
                    hashlib.md5(
                        open("executeInHadoopEnv.sh", 'rb').read()
                    ).hexdigest()
                if run("test %s = `md5sum executeInHadoopEnv.sh | cut -d ' ' -f 1`"
                    % executeInHadoopEnvHash).failed:
                    put("executeInHadoopEnv.sh", HADOOP_PREFIX + "/")
                    run("chmod +x executeInHadoopEnv.sh")
            command = ("./executeInHadoopEnv.sh %s " % ENVIRONMENT_FILE) + command
        run(command)


def operationOnHadoopDaemons(operation):
    # Start/Stop NameNode
    if (env.host == NAMENODE_HOST):
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/sbin/hadoop-daemon.sh %s namenode" % operation)

    # Start/Stop DataNode on all slave hosts
    if env.host in SLAVE_HOSTS:
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/sbin/hadoop-daemon.sh %s datanode" % operation)

    # Start/Stop ResourceManager
    if (env.host == RESOURCEMANAGER_HOST):
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/sbin/yarn-daemon.sh %s resourcemanager" % operation)

    # Start/Stop NodeManager on all container hosts
    if env.host in SLAVE_HOSTS:
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/sbin/yarn-daemon.sh %s nodemanager" % operation)

    # Start/Stop JobHistory daemon
    if (env.host == JOBHISTORY_HOST):
        operationInHadoopEnvironment(r"\\$HADOOP_PREFIX/sbin/mr-jobhistory-daemon.sh %s historyserver" % operation)
    run("jps")


def readHostsFromEC2():
    import boto.ec2

    global RESOURCEMANAGER_HOST, NAMENODE_HOST, JOBTRACKER_HOST, \
        JOBHISTORY_HOST, SLAVE_HOSTS

    RESOURCEMANAGER_HOST = None
    NAMENODE_HOST = None
    JOBTRACKER_HOST = None
    JOBHISTORY_HOST = None
    SLAVE_HOSTS = []

    conn = boto.ec2.connect_to_region(EC2_REGION,
            aws_access_key_id=AWS_ACCESSKEY_ID,
            aws_secret_access_key=AWS_ACCESSKEY_SECRET)
    instances = conn.get_only_instances(filters={'tag:Cluster': EC2_CLUSTER_NAME})

    for instance in instances:
        instanceTags = instance.tags
        instanceHost = instance.public_dns_name

        if "resourcemanager" in instanceTags:
            RESOURCEMANAGER_HOST = instanceHost

        if "namenode" in instanceTags:
            NAMENODE_HOST = instanceHost

        if "jobhistory" in instanceTags:
            JOBHISTORY_HOST = instanceHost

        if "jobtracker" in instanceTags:
            JOBTRACKER_HOST = instanceHost

        if not EC2_RM_NONSLAVE or instanceHost != RESOURCEMANAGER_HOST:
            SLAVE_HOSTS.append(instanceHost)

    if SLAVE_HOSTS:
        if RESOURCEMANAGER_HOST is None:
            RESOURCEMANAGER_HOST = SLAVE_HOSTS[0]

            if EC2_RM_NONSLAVE:
                SLAVE_HOSTS.remove(0)

        if NAMENODE_HOST is None:
            NAMENODE_HOST = RESOURCEMANAGER_HOST

        if JOBTRACKER_HOST is None:
            JOBTRACKER_HOST = SLAVE_HOSTS[0]

        if JOBHISTORY_HOST is None:
            JOBHISTORY_HOST = SLAVE_HOSTS[0]

bootstrapFabric()
