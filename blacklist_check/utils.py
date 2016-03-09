import datetime
import shlex
import subprocess
import socket
import dns

from .models import Types, DnsBlacklist
from django.utils import timezone


def check_bl(ip):
    data = dict()
    blacklist_hosts = DnsBlacklist.objects.all().values_list('dns', flat=True)
    blacklisted = True
    critical_blacklisted = True
    for bl in blacklist_hosts:
        try:
            my_resolver = dns.resolver.Resolver()
            query = '.'.join(reversed(str(ip.address).split("."))) + "." + bl
            answers = my_resolver.query(query, "A")
            answer_txt = my_resolver.query(query, "TXT")
            data[bl] = 'IP: {} IS listed in {} ({}: {})'.format(ip.address, bl, answers[0], answer_txt[0])
            blacklisted = False
            if bl.critical:
                critical_blacklisted = False
        except Exception as e:
            continue
    ip.blacklisted = blacklisted
    ip.critical_blacklisted = critical_blacklisted
    ip.data = data
    ip.save()


def check_ip_status(ip):
    cmd = shlex.split("ping -c1 {}".format(ip.address))
    try:
       output = subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        ip.status = Types.STATUS_DOWN
    else:
        ip.status = Types.STATUS_ACTIVE

    if ip.status == Types.STATUS_DOWN:
        print(ip.address)
        client_socket = socket.socket()
        client_socket.settimeout(4)
        try:
            client_socket.connect((ip.address, ip.ssh_port))
        except socket.error:
            ip.status = Types.STATUS_DOWN
        else:
            ip.status = Types.STATUS_ACTIVE
        client_socket.close()

    if ip.status == Types.STATUS_ACTIVE:
        try:
            ip.rdns = socket.gethostbyaddr(ip.address)[0]
        except Exception as e:
            pass

    ip.last_update = timezone.now()
    ip.save()