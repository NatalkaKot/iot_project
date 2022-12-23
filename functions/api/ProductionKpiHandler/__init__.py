import os

import azure.functions as func
from azure.iot.hub import IoTHubRegistryManager


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
    except ValueError as e:
        return func.HttpResponse(f"ValueError: {str(e)}", status_code=500)

    registry_manager = IoTHubRegistryManager(os.environ["ConnectionString"])
    devices = [d for d in req_body if float(d["ProductionKpi"]) < 90]
    for device in devices:
        twin = registry_manager.get_twin(device["DeviceId"])
        twin.properties.desired["ProductionRate"] = twin.properties.reported["ProductionRate"] - 10
        registry_manager.update_twin(device["DeviceId"], twin, twin.etag)
    return func.HttpResponse("Ok", status_code=200)
