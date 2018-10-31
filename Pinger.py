#!/usr/bin/env python

import os, sys, struct, select, time, argparse, logging
import socket
#  1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | ICMP_ECHO | 0 | checksum |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | self.own_id | self.seq_number |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

def arguments_handler():
    parser = argparse.ArgumentParser(description='Input client configurations.', add_help=False)
    parser.add_argument('-d', type=str, dest='domain', help='dst The destination IP for the ping message')
    parser.add_argument('-c', type=int, dest='count', help='count The number of packets used to compute RTT default 10', default=10)
    parser.add_argument('-p', type=str, dest='payload', help="payload The string to include in the payload. "
                                                             "EX: \"Hello World\"", default='helloworld')
    parser.add_argument('-l', type= str, dest='logfile', default='pinger_log.txt', help="logfile Write the debug info to the specified log file")
    if len(sys.argv[1:]) < 1:
        parser.print_help()
        sys.exit()
    parser_obj = parser.parse_args()
    return parser_obj


def setup_logger(logger_name, log_file, level=logging.INFO):

    log_setup = logging.getLogger(logger_name)
    formatter = logging.Formatter('%(message)s')
    fileHandler = logging.FileHandler(log_file, mode='w')
    fileHandler.setFormatter(formatter)
    log_setup.setLevel(level)
    log_setup.addHandler(fileHandler)


def generate_logifile(filename, username):
    if os.path.isfile(filename):
        os.remove(filename)
    setup_logger(username, filename)
    return logging.getLogger(username)

def recv_ping(my_socket, logger, payload_len, timeout = 1):

    #timeLeft = timeout
    while True:
        #start_time = float(time.time())
        ready = select.select([my_socket],[],[],timeout)
        if ready[0] == []:
            return -1
        recPacket, addr = my_socket.recvfrom(1024)

        ttl = ord(recPacket[8])
        icmpHeader = recPacket[20:28]
        type, code, checksum, packetID, sequence = struct.unpack(
            "bbHHh", icmpHeader
        )

        start_time = float(recPacket[28+payload_len:])
        end_time = float(time.time())

        rtt = int(round(1000*(end_time-start_time)))
        print "Reply from %s: bytes = %d time = %d ms TTL = %d" % (addr[0], payload_len, rtt, ttl)
        return rtt

def send_ping(my_socket, dest_addr, ID, data):
    ICMP_ECHO_REQUEST = 8
    dest_addr  =  socket.gethostbyname(dest_addr)

    # Header is type (8), code (8), checksum (16), id (16), sequence (16)
    my_checksum = 0

    # Make a dummy heder with a 0 checksum.
    header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1)
    start_time = str(time.time())
    #print start_time
    my_checksum = checksum(header + data + start_time)

    header = struct.pack(
        "bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1
    )
    packet = header + data + start_time
    my_socket.sendto(packet, (dest_addr, 0))


def start_ping(dest_addr, logger, data):
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    send_ping(my_socket, dest_addr, 0, data)
    return recv_ping(my_socket, logger, len(data))




def checksum(source_string):
    """
    I'm not too confident that this is right but testing seems
    to suggest that it gives the same answers as in_cksum in ping.c
    """
    sum = 0
    countTo = (len(source_string)/2)*2
    count = 0

    while count<countTo:
        thisVal = ord(source_string[count + 1])*256 + ord(source_string[count])
        sum = sum + thisVal
        sum = sum & 0xffffffff # Necessary?
        count = count + 2

    if countTo<len(source_string):
        sum = sum + ord(source_string[len(source_string) - 1])
        sum = sum & 0xffffffff # Necessary?

    sum = (sum >> 16)  +  (sum & 0xffff)
    sum = sum + (sum >> 16)
    answer = ~sum
    answer = answer & 0xffff

    # Swap bytes. Bugger me if I know why.
    answer = answer >> 8 | (answer << 8 & 0xff00)

    return answer


if __name__ == '__main__':
    parser_obj = arguments_handler()
    domain = parser_obj.domain
    count = parser_obj.count
    data = parser_obj.payload
    logfile = parser_obj.logfile

    logger = generate_logifile(logfile, "shunkai")

    max_rtt = 0
    min_rtt = 256
    sum = 0
    avg_rtt = 0
    lost = 0
    print "Ping %s with %d bytes of data %s" % (domain, len(data), data)
    for i in xrange(count):
        rtt = start_ping(domain, logger, data)
        if rtt == -1:
            print "Request timeout"
            lost += 1
        else:
            if rtt > max_rtt: max_rtt = rtt
            if rtt < min_rtt: min_rtt = rtt
            sum += rtt
    if min_rtt == 256: min_rtt = 0
    avg_rtt = sum/count
    print "Ping statistics for %s:" % domain
    print "Packets: Sent = %d, Received = %d, Lost = %d (%d %% loss)" % (count, count-lost, lost, 100*(float(lost)/float(count)))
    print "Approximate round trip times in milli-seconds:"
    print "Minimum = %d ms, Maximum = %d ms, Average = %d ms" % (min_rtt, max_rtt, avg_rtt)