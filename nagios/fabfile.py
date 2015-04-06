#!/usr/bin/env python2
# encoding: utf-8

# Author: Alexandre Fonseca
# Description:
#   Installs, configures and manages Nagios on a set of nodes
#   in a cluster.

import os
import tempfile
import textwrap
from fabric.api import run, cd, env, settings, put, sudo
from fabric.decorators import runs_once, parallel
from fabric.tasks import execute

env.password = "password"

# Packages info
NAGIOS_CORE_VERSION = "4.0.8"
NAGIOS_CORE_PACKAGE = "nagios-{}".format(NAGIOS_CORE_VERSION)
NAGIOS_CORE_URL = "http://liquidtelecom.dl.sourceforge.net/project/nagios/nagios-4.x/{package}/{package}.tar.gz".format(package=NAGIOS_CORE_PACKAGE)

NAGIOS_PLUGINS_VERSION = "2.0.3"
NAGIOS_PLUGINS_PACKAGE = "nagios-plugins-{}".format(NAGIOS_PLUGINS_VERSION)
NAGIOS_PLUGINS_URL = "http://nagios-plugins.org/download/{}.tar.gz".format(NAGIOS_PLUGINS_PACKAGE)

NRPE_VERSION = "2.15"
NRPE_PACKAGE = "nrpe-{}".format(NRPE_VERSION)
NRPE_URL = "http://liquidtelecom.dl.sourceforge.net/project/nagios/nrpe-2.x/{package}/{package}.tar.gz".format(package=NRPE_PACKAGE)

PNP4NAGIOS_VERSION = "0.6.25"
PNP4NAGIOS_PACKAGE = "pnp4nagios-{}".format(PNP4NAGIOS_VERSION)
PNP4NAGIOS_URL = "http://liquidtelecom.dl.sourceforge.net/project/pnp4nagios/PNP-0.6/{package}.tar.gz".format(package=PNP4NAGIOS_PACKAGE)

# Cluster info
CLUSTER_MASTER = "grafos01"
CLUSTER_WORKERS = ["grafos01", "grafos02", "grafos03"]
#CLUSTER_WORKERS = ["grafos{:02d}".format(x) for x in range(1, 11)]

# Nagios info
NAGIOS_USER = "nagios"
NAGIOS_GROUP = "nagcmd"
NAGIOS_HTTP_USER = "nagiosadmin"
NAGIOS_HTTP_PASSWORD = "grafos"

# NRPE info
NRPE_SERVICES = [
    ("Load", "check_load"),
    ("Disk IO", "check_io"),
    ("Network", "check_net"),
    ("CPU", "check_cpu"),
    ("Socket", "check_socket"),
    ("Memory", "check_mem"),
    ("Processes", "check_procs")
]

# System info
NET_INTERFACE = "eth0"
SENDMAIL_BIN = "/usr/bin/sendmail"

APACHE2_CONFD = "/etc/apache2/conf.d"
#APACHE2_CONFD = "/etc/apache/sites-enabled" # Ubuntu 14.04
APACHE2_DAEMON = "apache2"

PREINSTALL_COMMANDS = [
    "wget -O - http://cpanmin.us | perl - --sudo App::cpanminus",
    "cpanm Sys::Statistics::Linux"
]

INSTALL_COMMAND = "apt-get -qq install {package}"
DEPENDENCIES = [
    "wget",
    "build-essential",
    "apache2",
    "apache2-utils",
    "php5-gd",
    "libgd2-xpm-dev",
    "libapache2-mod-php5",
    "xinetd",
    "sysstat",
    "rrdtool",
    "librrds-perl",
    "libssl-dev",
]

POSTINSTALL_COMMANDS = [
    "a2enmod rewrite",
    "a2enmod cgi",
    "service {0} restart".format(APACHE2_DAEMON)
]

def bootstrapFabric():
    hosts = [CLUSTER_MASTER] + CLUSTER_WORKERS
    seen = set()
    # Remove empty hosts and duplicates
    cleanedHosts = [host for host in hosts if host and host not in seen and not seen.add(host)]
    env.hosts = cleanedHosts

    retrieveClusterInformation()

    print("Hosts to IPS:")
    print(CLUSTER_PRIVATE_IPS)


# MAIN FUNCTIONS
def install():
    installDependencies()
    addUserAndGroup()
    installCore()
    installPlugins()
    installNRPE()
    installPNP4Nagios()
    restartNagios()

def installDependencies():
    for command in PREINSTALL_COMMANDS:
        sudo(command)
    for requirement in DEPENDENCIES:
        sudo(INSTALL_COMMAND.format(package=requirement))
    for command in POSTINSTALL_COMMANDS:
        sudo(command)


def addUserAndGroup():
    with settings(warn_only=True):
        if run_with_settings("id {NAGIOS_USER}").failed:
            sudo_with_settings("useradd {NAGIOS_USER}")
            sudo_with_settings("groupadd {NAGIOS_GROUP}")
            sudo_with_settings("usermod -a -G {NAGIOS_GROUP} {NAGIOS_USER}")


def installCore():
    if not env.host == CLUSTER_MASTER:
        return

    with settings(warn_only=True):
        if not run("test -d {}".format("/usr/local/nagios")).failed:
            print("Core already installed.")
            return

    with settings(warn_only=True):
        if run("test -f %s.tar.gz" % NAGIOS_CORE_PACKAGE).failed:
            run("wget -O %s.tar.gz %s" % (NAGIOS_CORE_PACKAGE, NAGIOS_CORE_URL))
    run("tar --overwrite -xf %s.tar.gz" % NAGIOS_CORE_PACKAGE)

    with cd(NAGIOS_CORE_PACKAGE):
        run_with_settings("./configure --with-nagios-group={NAGIOS_USER} --with-command-group={NAGIOS_GROUP} --with-mail={SENDMAIL_BIN} --with-httpd-conf={APACHE2_CONFD}")
        run("make all")
        sudo("make install")
        sudo("make install-init")
        sudo("make install-config")
        sudo("make install-commandmode")
        sudo("make install-webconf")
        sudo("cp -R contrib/eventhandlers/ /usr/local/nagios/libexec")
        sudo_with_settings("chown -R {NAGIOS_USER}:{NAGIOS_USER} /usr/local/nagios/libexec/eventhandlers")
        sudo("/usr/local/nagios/bin/nagios -v /usr/local/nagios/etc/nagios.cfg")
        sudo_with_settings("/etc/init.d/{APACHE2_DAEMON} restart")
        sudo_with_settings("htpasswd -cb /usr/local/nagios/etc/htpasswd.users {NAGIOS_HTTP_USER} {NAGIOS_HTTP_PASSWORD}")
        sudo("ln -s /etc/init.d/nagios /etc/rcS.d/S99nagios")


def installPlugins():
    with settings(warn_only=True):
        if run("test -f {}.tar.gz".format(NAGIOS_PLUGINS_PACKAGE)).failed:
            run("wget -O {}.tar.gz {}".format(NAGIOS_PLUGINS_PACKAGE, NAGIOS_PLUGINS_URL))
    run("tar --overwrite -xf {}.tar.gz".format(NAGIOS_PLUGINS_PACKAGE))

    with cd(NAGIOS_PLUGINS_PACKAGE):
        run_with_settings("./configure --with-nagios-group={NAGIOS_USER} --with-nagios-user={NAGIOS_USER}")
        run_with_settings("make")
        sudo_with_settings("make install")


def installNRPE():
    with settings(warn_only=True):
        if run("test -f %s.tar.gz" % NRPE_PACKAGE).failed:
            run("wget -O %s.tar.gz %s" % (NRPE_PACKAGE, NRPE_URL))
    run("tar --overwrite -xf %s.tar.gz" % NRPE_PACKAGE)

    with cd(NRPE_PACKAGE):
        run_with_settings("./configure --enable-ssl --with-ssl=/usr/bin/openssl --with-ssl-lib=/usr/lib/x86_64-linux-gnu")
        run_with_settings("make all")
        if env.host in CLUSTER_WORKERS:
            sudo_with_settings("make install-plugin")
            sudo_with_settings("make install-daemon")
            sudo_with_settings("make install-daemon-config")
            sudo_with_settings("make install-xinetd")
            addLinesToFile("/etc/services", ["nrpe\t5666/tcp\tNRPE"])
        if env.host == CLUSTER_MASTER:
            sudo_with_settings("make install-daemon")
    updateNPREConfig()


def installPNP4Nagios():
    if not env.host == CLUSTER_MASTER:
        return

    with settings(warn_only=True):
        if run("test -f %s.tar.gz" % PNP4NAGIOS_PACKAGE).failed:
            run("wget -O %s.tar.gz %s" % (PNP4NAGIOS_PACKAGE, PNP4NAGIOS_URL))
    run("tar --overwrite -xf %s.tar.gz" % PNP4NAGIOS_PACKAGE)

    with cd(PNP4NAGIOS_PACKAGE):
        run_with_settings("./configure")
        run_with_settings("make all")
        sudo_with_settings("make fullinstall")
        sudo_with_settings("service {APACHE2_DAEMON} restart")

    configurePNP4Nagios()


def configurePNP4Nagios():
    if not env.host == CLUSTER_MASTER:
        return

    addLinesToFile("/usr/local/nagios/etc/nagios.cfg", [
            r"process_performance_data=1",
            r"service_perfdata_file=/usr/local/pnp4nagios/var/service-perfdata",
            r"service_perfdata_file_template=DATATYPE::SERVICEPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tSERVICEDESC::$SERVICEDESC$\tSERVICEPERFDATA::$SERVICEPERFDATA$\tSERVICECHECKCOMMAND::$SERVICECHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$\tSERVICESTATE::$SERVICESTATE$\tSERVICESTATETYPE::$SERVICESTATETYPE$",
            r"service_perfdata_file_mode=a",
            r"service_perfdata_file_processing_interval=15",
            r"service_perfdata_file_processing_command=process-service-perfdata-file",
            r"host_perfdata_file=/usr/local/pnp4nagios/var/host-perfdata",
            r"host_perfdata_file_template=DATATYPE::HOSTPERFDATA\tTIMET::$TIMET$\tHOSTNAME::$HOSTNAME$\tHOSTPERFDATA::$HOSTPERFDATA$\tHOSTCHECKCOMMAND::$HOSTCHECKCOMMAND$\tHOSTSTATE::$HOSTSTATE$\tHOSTSTATETYPE::$HOSTSTATETYPE$",
            r"host_perfdata_file_mode=a",
            r"host_perfdata_file_processing_interval=15",
            r"host_perfdata_file_processing_command=process-host-perfdata-file",
            r"process_performance_data=1",
            r"service_perfdata_file_mode=a",
            r"service_perfdata_file_processing_command=process-service-perfdata-file",
            r"host_perfdata_file_mode=a",
            r"host_perfdata_file_processing_command=process-host-perfdata-file",
        ])


def updateConfig():
    updateNPREConfig()
    configurePNP4Nagios()

def updateNPREConfig():
    put_with_settings("xinetd_nrpe", "/etc/xinetd.d/nrpe", use_sudo=True)

    if env.host in CLUSTER_WORKERS:
        configureNRPESlaves()

    if env.host == CLUSTER_MASTER:
        configureNRPEMaster()

def startNagios():
    if env.host in CLUSTER_WORKERS:
        sudo_with_settings("service xinetd start")

    if env.host == CLUSTER_MASTER:
        sudo_with_settings("service nagios start")
        sudo_with_settings("service npcd start")

def stopNagios():
    if env.host == CLUSTER_MASTER:
        sudo_with_settings("service nagios stop")
        sudo_with_settings("service npcd stop")

def restartNagios():
    if env.host in CLUSTER_WORKERS:
        sudo_with_settings("service xinetd restart")

    if env.host == CLUSTER_MASTER:
        sudo_with_settings("service nagios restart")
        sudo_with_settings("service npcd restart")


def installChecks():
    put("check_iostat", "/usr/local/nagios/libexec/check_iostat", use_sudo=True)
    sudo_with_settings("chown {NAGIOS_USER} /usr/local/nagios/libexec/check_iostat")
    sudo("chmod 755 /usr/local/nagios/libexec/check_iostat")
    put("check_netint.pl", "/usr/local/nagios/libexec/check_netint.pl", use_sudo=True)
    sudo_with_settings("chown {NAGIOS_USER} /usr/local/nagios/libexec/check_netint.pl")
    sudo("chmod 755 /usr/local/nagios/libexec/check_netint.pl")
    put("check_linux_stats.pl", "/usr/local/nagios/libexec/check_linux_stats.pl", use_sudo=True)
    sudo_with_settings("chown {NAGIOS_USER} /usr/local/nagios/libexec/check_linux_stats.pl")
    sudo("chmod 755 /usr/local/nagios/libexec/check_linux_stats.pl")

def configureNRPESlaves():
    put("slave_nrpe_config", "/usr/local/nagios/etc/nrpe.cfg", use_sudo=True)
    sudo_with_settings("chown {NAGIOS_USER} /usr/local/nagios/etc/nrpe.cfg")
    installChecks()

def configureNRPEMaster():
    addLinesToFile("/usr/local/nagios/etc/nagios.cfg", [
        "cfg_file=/usr/local/nagios/etc/hosts.cfg",
        "cfg_file=/usr/local/nagios/etc/services.cfg"
    ])
    addHostsToConfig()
    addServicesToConfig()
    addCommandsToConfig()


def addHostsToConfig():
    put("master_nrpe_hosts", "/usr/local/nagios/etc/hosts.cfg", use_sudo=True)

    host_config_base = textwrap.dedent("""\
    define host {{
    use linux-box
    host_name {hostname}
    alias {hostname}
    address {address}
    }}""")

    config_parts = []

    for worker in CLUSTER_WORKERS:
        config_parts.append(host_config_base.format(hostname=worker, address=CLUSTER_PRIVATE_IPS[worker]))

    sudo("echo \"{hosts}\" >> \"{file}\"".format(hosts="\n".join(config_parts), file="/usr/local/nagios/etc/hosts.cfg"))

def addServicesToConfig():
    service_config_base = textwrap.dedent("""\
    define service {{
    use generic-service
    host_name {hostname}
    check_interval 1
    service_description {description}
    check_command check_nrpe!{command}
    }}""")

    config_parts = []

    for worker in CLUSTER_WORKERS:
        for service_name, service_command in NRPE_SERVICES:
            config_parts.append(service_config_base.format(hostname=worker, description=service_name, command=service_command))

    sudo("echo \"{services}\" > \"{file}\"".format(services="\n".join(config_parts), file="/usr/local/nagios/etc/services.cfg"))


def addCommandsToConfig():
    put("commands.cfg", "/usr/local/nagios/etc/objects/commands.cfg", use_sudo=True)
    sudo_with_settings("chown {NAGIOS_USER} /usr/local/nagios/etc/objects/commands.cfg")


def addLinesToFile(cfg_file, lines):
    with settings(warn_only=True):
        if not sudo("test -f {}".format(cfg_file)).failed:
            currentBakNumber = getLastBackupNumber(cfg_file) + 1
            sudo("cp {file} {file}.bak{bakNumber}".format(file=cfg_file, bakNumber=currentBakNumber))

    sudo("touch %s" % cfg_file)

    for line in lines:
        lineNumber = sudo("grep -n -F -x '{line}' '{file}' | cut -d : -f 1".format(line=line, file=cfg_file))
        try:
            lineNumber = int(lineNumber)
            # Line already exists
            pass
        except ValueError:
            sudo("echo '{line}' >> \"{file}\"".format(line=line, file=cfg_file))


def getLastBackupNumber(filePath):
    dirName = os.path.dirname(filePath)
    fileName = os.path.basename(filePath)

    with cd(dirName):
        latestBak = sudo("ls -1 | grep %s.bak | tail -n 1" % fileName)
        latestBakNumber = -1
        if latestBak:
            latestBakNumber = int(latestBak[len(fileName) + 4:])
        return latestBakNumber

CLUSTER_PRIVATE_IPS = {}
CLUSTER_MASTER_IP = None

@runs_once
def retrieveClusterInformation():
    global CLUSTER_PRIVATE_IPS
    global CLUSTER_MASTER_IP

    private_ips = execute(getPrivateIp)

    CLUSTER_PRIVATE_IPS = private_ips
    CLUSTER_MASTER_IP = CLUSTER_PRIVATE_IPS[CLUSTER_MASTER]

@parallel
def getPrivateIp():
    return run("ifconfig %s | grep 'inet\s\+' | awk '{print $2}' | cut -d':' -f2" % NET_INTERFACE).strip()


def run_with_settings(command):
    return run(command.format(**globals()))

def sudo_with_settings(command):
    return sudo(command.format(**globals()))

def put_with_settings(local_path, remote_path, use_sudo=False):
    temp_file = None

    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False)

        with open(local_path, 'r') as base_file:
            base_file_contents = base_file.read()
            temp_file.write(base_file_contents.format(**globals()))
    finally:
        if temp_file:
            temp_file.close()

    put(temp_file.name, remote_path, use_sudo)

bootstrapFabric()
