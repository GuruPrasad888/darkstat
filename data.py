import time
import re
import requests
import json
import time
from bs4 import BeautifulSoup
import ipaddress
import subprocess
from datetime import datetime


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


def individual_device_data(interface,port):

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


def get_port_data(device, port):

    ip_address = device["IP address"]

    data = refresh_page(f"http://localhost:{port}/hosts/{ip_address}/")

    soup = BeautifulSoup(data, 'html.parser')

    #in_data = soup.find('b', text='In:').find_next('b').text.strip().replace(',', '')
    #out_data = soup.find('b', text='Out:').find_next('b').text.strip().replace(',', '')
    #total_data = soup.find('b', text='Total:').find_next('b').text.strip().replace(',', '')

    result = {
        'Timestamp' : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'IP Address': soup.find('h2', class_='pageheader').text.strip(),
        'MAC Address': soup.find('b', text='MAC Address:').find_next('tt').text.strip().upper(),
        'In' : device["In"],
        'Out' : device["Out"],
        'Total' : device["Total"],
        'Name': device["Name"],
        'Last seen': device["Last seen"],
        'TCP ports on this host': [],
        'TCP ports on remote hosts': [],
        'UDP ports on this host': [],
        'UDP ports on remote hosts': [],
        'IP Protocols': []
    }

    # Extract TCP ports on this host
    tcp_table = soup.find('h3', text='TCP ports on this host').find_next('table')
    rows = tcp_table.find_all('tr')[1:]  # Skip the header row

    for row in rows:
        cells = row.find_all('td')
        port, service, in_value, out_value, total_value, syns = map(lambda x: x.text.strip(), cells)
        
        result['TCP ports on this host'].append({
            'Port': port,
            'Service': service,
            'In': int(in_value.replace(",", "")),
            'Out': int(out_value.replace(",", "")),
            'Total': int(total_value.replace(",", "")),
            'syns': syns
        })

    # Extract TCP ports on remote hosts
    tcp_remote_table = soup.find('h3', text='TCP ports on remote hosts').find_next('table')
    rows_remote = tcp_remote_table.find_all('tr')[1:]  # Skip the header row

    for row in rows_remote:
        cells = row.find_all('td')
        port, service, in_value, out_value, total_value, syns = map(lambda x: x.text.strip(), cells)
        
        result['TCP ports on remote hosts'].append({
            'Port': port,
            'Service': service,
            'In': int(in_value.replace(",", "")),
            'Out': int(out_value.replace(",", "")),
            'Total': int(total_value.replace(",", "")),
            'syns': syns
        })

    # Extract UDP ports on this host
    udp_table = soup.find('h3', text='UDP ports on this host').find_next('table')
    rows_udp = udp_table.find_all('tr')[1:]  # Skip the header row

    for row in rows_udp:
        cells = row.find_all('td')
        port, service, in_value, out_value, total_value = map(lambda x: x.text.strip(), cells)
        
        result['UDP ports on this host'].append({
            'Port': port,
            'Service': service,
            'In': int(in_value.replace(",", "")),
            'Out': int(out_value.replace(",", "")),
            'Total': int(total_value.replace(",", ""))
        })

    # Extract UDP ports on remote hosts
    udp_remote_table = soup.find('h3', text='UDP ports on remote hosts').find_next('table')
    rows_udp_remote = udp_remote_table.find_all('tr')[1:]  # Skip the header row

    for row in rows_udp_remote:
        cells = row.find_all('td')
        port, service, in_value, out_value, total_value = map(lambda x: x.text.strip(), cells)
        
        result['UDP ports on remote hosts'].append({
            'Port': port,
            'Service': service,
            'In': int(in_value.replace(",", "")),
            'Out': int(out_value.replace(",", "")),
            'Total': int(total_value.replace(",", ""))
        })

    # Extract IP protocols
    ip_protocol_table = soup.find('h3', text='IP protocols').find_next('table')
    rows_ip_protocol = ip_protocol_table.find_all('tr')[1:]  # Skip the header row

    for row in rows_ip_protocol:
        cells = row.find_all('td')
        protocol, protocol_name, in_value, out_value, total_value = map(lambda x: x.text.strip(), cells)
        
        result['IP Protocols'].append({
            'Protocol Number': protocol,
            'Protocol name': protocol_name.upper(),
            'In': int(in_value.replace(",", "")),
            'Out': int(out_value.replace(",", "")),
            'Total': int(total_value.replace(",", ""))
        })
    return result


def get_top_devices_in_total(interface, port):

    if is_interface_up(interface):

        ip_data = individual_device_data(interface, port)
        top_in_total_devices = sorted(ip_data, key=lambda x: x["Total"], reverse=True)[:50]
        
        individual_data = []
        
        for device in top_in_total_devices:
            port_data = get_port_data(device, port)
            individual_data.append(port_data)
        return individual_data
   
    return "Interface is down"


if __name__ == "__main__":
    try:
        while True:
            start_time = time.time()  
            individual_data = get_top_devices_in_total("ens37", "5554")

            json_data = json.dumps({"data":individual_data}, indent=2)

            timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
            filename = f"/home/guru/json_files/{timestamp}.json"

            with open(filename, "w") as json_file:
                json_file.write(json_data)

            elapsed_time = time.time() - start_time
            sleep_time = 30 - elapsed_time  
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
