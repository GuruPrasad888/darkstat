import time
import re
import requests
import json
from bs4 import BeautifulSoup
import ipaddress
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta


lease_file_path = "/var/lib/misc/dnsmasq.leases"


def get_subnet(interface_name):
    try:
        result = subprocess.run(["ip", "-j", "-o", "addr", "show", interface_name], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        local_ip = data[0]["addr_info"][0]["local"]
        prefix_len = data[0]["addr_info"][0]["prefixlen"]
        return local_ip, prefix_len


    except subprocess.CalledProcessError as e:
        print(f"Error executing 'ip' command: {e}")
        return None
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        print(f"Error parsing JSON output: {e}")
        return None


def get_device_name_from_lease(ip_address, mac_address):


    try:
        with open(lease_file_path, 'r') as lease_file:
            leases = lease_file.readlines()


        mac_address = mac_address.lower()  # Convert MAC address to lowercase because mac address in lease file is in lowercase


        for line in leases:
            values = line.strip().split()
            if len(values) >= 4 and values[2] == ip_address and values[1].lower() == mac_address:   # Check if IP address and MAC address match
                device_name = values[3]
                return device_name
    except FileNotFoundError:
        print(f"DHCP lease file not found: {lease_file_path}")
    except Exception as e:
        print(f"Error reading DHCP lease file: {e}")


    return "Unknown"


def convert_to_human_readable(devices):
    def convert_bytes_to_human_readable(bytes_value):
        if bytes_value < 1024:
            return f"{bytes_value} B"
        elif bytes_value < 1024 ** 2:
            return f"{bytes_value / 1024:.2f} KB"
        elif bytes_value < 1024 ** 3:
            return f"{bytes_value / (1024 ** 2):.2f} MB"
        elif bytes_value < 1024 ** 4:
            return f"{bytes_value / (1024 ** 3):.2f} GB"
        else:
            return f"{bytes_value / (1024 ** 4):.2f} TB"
    
    for device in devices:
        device["In"] = convert_bytes_to_human_readable(device["In"])
        device["Out"] = convert_bytes_to_human_readable(device["Out"])
        device["Total"] = convert_bytes_to_human_readable(device["Total"])
    return devices


def is_ip_in_subnet(ip_address, subnet):
    try:
        ip_address_obj = ipaddress.ip_address(ip_address)
        subnet_obj = ipaddress.ip_network(subnet, strict=False)
        return ip_address_obj in subnet_obj
    except ValueError:
        return False
    

def refresh_page(url):
    retry_attempts = 5
    retry_delay = 2  # seconds

    for attempt in range(retry_attempts):
        try:
            response = requests.get(url)
            return response.text
        except requests.exceptions.RequestException as e:
            time.sleep(retry_delay)


def is_interface_up(interface_name):
    try:
        result = subprocess.run(['ip', 'a', 'show', interface_name], capture_output=True, text=True)
        # Check if the output contains 'state UP' in the status section
        return 'state UP' in result.stdout
    except Exception as e:
        return False


def extract_data(interface,port):
    if is_interface_up(interface):
        local_ip, cidr = get_subnet(interface)
        subnet = f"{local_ip}/{cidr}"


        network_address = ipaddress.IPv4Network(subnet, strict=False).network_address
        broadcast_address = ipaddress.IPv4Network(subnet, strict=False).broadcast_address


        excluded_ips = [str(network_address), str(broadcast_address), local_ip]


        html_code = refresh_page(f"http://localhost:{port}/hosts/?full=yes")


        soup = BeautifulSoup(html_code, "html.parser")
        ip_data = []


        for row in soup.find_all("tr", class_=re.compile("alt[12]")):
            columns = row.find_all("td")
            ip_link = columns[0].find('a')


            if ip_link:
                ip_match = re.search(r"\d+\.\d+\.\d+\.\d+", ip_link['href'])
                if ip_match:
                    ip_address = ip_match.group()
                    if ip_address in excluded_ips:
                        continue


                    if is_ip_in_subnet(ip_address, subnet):
                        data = {
                            "IP address": ip_address,
                            "MAC address":columns[2].text.upper(),
                            "Name":get_device_name_from_lease(ip_address, mac_address=columns[2].text),
                            "In":int(columns[3].text.replace(",", "")),
                            "Out":int(columns[4].text.replace(",", "")),
                            "Total":int(columns[5].text.replace(",", "")),
                            "Last seen": columns[6].text
                        }
                        ip_data.append(data)


        return ip_data
    else:
        return False


def all_devices(interface,port):
    ip_data = extract_data(interface,port)
    if ip_data:
        return convert_to_human_readable(ip_data)
    return "Interface is down"


def get_top_devices_in_total(interface,port):
    ip_data = extract_data(interface,port)
    if ip_data:
        top_in_total_devices = sorted(ip_data, key=lambda x: x["Total"], reverse=True)[:10]
        return convert_to_human_readable(top_in_total_devices)
    return "Interface is down"


def get_top_devices_in_in(interface,port):
    ip_data = extract_data(interface,port,)
    if ip_data:
        top_in_in_devices = sorted(ip_data, key=lambda x: x["In"], reverse=True)[:10]
        return convert_to_human_readable(top_in_in_devices)
    return "Interface is down"


def get_top_devices_in_out(interface,port):
    ip_data = extract_data(interface,port)
    if ip_data:
        top_in_out_devices = sorted(ip_data, key=lambda x: x["Out"], reverse=True)[:10]
        return convert_to_human_readable(top_in_out_devices)
    return "Interface is down"

def extract_minutes(xml_data):
    root = ET.fromstring(xml_data)
    minutes_data = []
    current_time = datetime.now()

    for element in root.iter('minutes'):
        for index, e in enumerate(element.findall('e')):
            # Subtract minutes based on the index
            time_difference = timedelta(minutes=59 - index)
            entry_time = current_time - time_difference
            
            date_time = entry_time.replace(second=0).strftime('%d-%m-%Y %H:%M:%S')
                
            minutes_data.append({
                'DateTime': date_time,
                'In': int(e.get('i')),
                'Out': int(e.get('o')),
                'Total': int(e.get('i')) + int(e.get('o')),
            })

    return minutes_data

def extract_hours(xml_data):
    root = ET.fromstring(xml_data)
    hours_data = []

    encountered_zero = False

    for element in root.iter('hours'):
        for e in element.findall('e'):
            period_value = int(e.get('p'))

            # Check if we have encountered 0
            if period_value == 0:
                encountered_zero = True

            # Calculate date based on the period value
            if encountered_zero:
                # If period_value is 0, it represents the first hour of today
                date_time = datetime.now().replace(hour=period_value, minute=0, second=0).strftime('%d-%m-%Y %H:%M:%S')
            else:
                # If period_value is before 0, it represents hours yesterday
                date_time = (datetime.now() - timedelta(days=1)).replace(hour=period_value, minute=0, second=0).strftime('%d-%m-%Y %H:%M:%S')

            hours_data.append({
                'Time': date_time,
                'In': int(e.get('i')),
                'Out': int(e.get('o')),
                'Total': int(e.get('i')) + int(e.get('o')),
              #  'period': period_value,
                
            })

    return hours_data

def extract_days(xml_data):
    root = ET.fromstring(xml_data)
    days_data = []
    current_month = datetime.now().month
    current_year = datetime.now().year
    encountered = False

    for element in root.iter('days'):
        for e in element.findall('e'):
            period_value = int(e.get('p'))

            # Calculate date based on the period value
            if period_value == 1:
                encountered = True

            if not encountered:
                # Days in the previous month
                previous_month = current_month - 1 if current_month > 1 else 12
                previous_year = current_year - 1 if current_month == 1 else current_year
                days_in_previous_month = datetime(previous_year, previous_month, period_value).strftime('%d-%m-%Y')
                date_time = days_in_previous_month
            else:
                # Days in the current month
                date_time = f'{period_value:02d}-{current_month:02d}-{current_year}'
                
            days_data.append({
                'Date': date_time,
                'In': int(e.get('i')),
                'Out': int(e.get('o')),
                'Total': int(e.get('i')) + int(e.get('o')),
               # 'period': period_value,
            })

    return days_data

def minutes(interface,port):
    if is_interface_up(interface):
        xml_data = refresh_page(f"http://localhost:{port}/graphs.xml")
        minutes_data = extract_minutes(xml_data)

        if minutes_data:
            return convert_to_human_readable(minutes_data)
    return "Interface is down"

def hours(interface,port):
    if is_interface_up(interface):
        xml_data = refresh_page(f"http://localhost:{port}/graphs.xml")
        hours_data = extract_hours(xml_data)

        if hours_data:
            return convert_to_human_readable(hours_data)
    return "Interface is down"

def days(interface,port):
    if is_interface_up(interface):
        xml_data = refresh_page(f"http://localhost:{port}/graphs.xml")
        days_data = extract_days(xml_data)

        if days_data:
            return convert_to_human_readable(days_data)
    return "Interface is down"
