from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import json


app = FastAPI()


from darkstat.lan import get_top_devices_in_total, get_top_devices_in_in, get_top_devices_in_out, all_devices, minutes, hours, days
from darkstat.data import get_top_devices_in_total

lan1 = "enp3s0"
lan1_port  = "5554"
lan2 = "enp4s0"
lan2_port = "20000"

wan1 = "enp1s0"
wan1_port = "5555"
wan2 = "enp2s0"
wan2_port = "40000"


@app.get("/lan1/all_devices")
def get_all_devices():
    json_data = all_devices(lan1,lan1_port)
    return json_data


@app.get("/lan1/top_in")
def get_top_devices_in():
    top_in_devices = get_top_devices_in_in(lan1,lan1_port)
    return top_in_devices


@app.get("/lan1/top_out")
def get_top_devices_out():
    top_out_devices = get_top_devices_in_out(lan1,lan1_port)
    return top_out_devices


@app.get("/lan1/top_total")
def get_top_devices_total():
    top_total_devices = get_top_devices_in_total(lan1,lan1_port)
    return top_total_devices


@app.get("/lan2/all_devices")
def get_all_devices():
    json_data = all_devices(lan2,lan2_port)
    return json_data


@app.get("/lan2/top_in")
def get_top_devices_in():
    top_in_devices = get_top_devices_in_in(lan2,lan2_port)
    return top_in_devices


@app.get("/lan2/top_out")
def get_top_devices_out():
    top_out_devices = get_top_devices_in_out(lan2,lan2_port)
    return top_out_devices


@app.get("/lan2/top_total")
def get_top_devices_total():
    top_total_devices = get_top_devices_in_total(lan2,lan2_port)
    return top_total_devices


@app.get("/wan1/minutes")
def minute():
    data = minutes(wan1,wan1_port)
    if data:
        return data
    return "No data found"


@app.get("/wan1/hours")
def hour():
    data = hours(wan1,wan1_port)
    if data:
        return data
    return "No data found"


@app.get("/wan1/days")
def day():
    data = days(wan1,wan1_port)
    if data:
      return data
    return "No data found"


@app.get("/wan2/minutes")
def minute():
    data = minutes(wan2,wan2_port)
    if data:
        return data
    return "No data found"


@app.get("/wan2/hours")
def hour():
    data = hours(wan2,wan2_port)
    if data:
        return data
    return "No data found"


@app.get("/wan2/days")
def day():
    data = days(wan2,wan2_port)
    if data:
        return data
    return "No data found"

@app.get("/demo")
def data():
    data = get_top_devices_in_total("ens37","5554")
    return data


@app.get("/display")
def display_json():
    try:
        # Replace 'output.json' with the actual file name
        with open('output.json', 'r') as json_file:
            data = json_file.read()
            return JSONResponse(content=data, status_code=200, media_type="application/json")
    except FileNotFoundError:
        return JSONResponse(content={"error": "File not found"}, status_code=404)
    except Exception as e:
        return JSONResponse(content={"error": f"Error reading file: {str(e)}"}, status_code=500)

@app.get("/json")    
def read_json_file(filename='output.json'):
    try:
        with open(filename, 'r') as json_file:
            data = json.load(json_file)
            return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON format")

@app.get("/active")
def read_active():
    try:
        with open("Active.json", "r") as file:
            data = json.load(file)
        return JSONResponse(content=data, status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Active.json not found")

@app.get("/disconnected")
def read_disconnected():
    try:
        with open("Disconnected.json", "r") as file:
            data = json.load(file)
        return JSONResponse(content=data, status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Disconnected.json not found")

@app.get("/all")
def read_all():
    try:
        current_data = []
        with open("Active.json", "r") as active_file:
            current_data = json.load(active_file).get("Active Devices", [])

        disconnected_data = []
        with open("Disconnected.json", "r") as disconnected_file:
            disconnected_data = json.load(disconnected_file).get("Disconnected Devices", [])

        return JSONResponse(content={"Active Devices": current_data, "Disconnected Devices": disconnected_data},
                            status_code=200)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Files not found")