import os

import azure.functions as func
from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import CloudToDeviceMethod


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
    except ValueError as e:
        return func.HttpResponse(f"ValueError: {str(e)}", status_code=500)

    registry_manager = IoTHubRegistryManager(os.environ["ConnectionString"])
    devices = [d for d in req_body if float(d["ErrorsCount"]) > 3]
    for device in devices:
        registry_manager.invoke_device_method(
            device["DeviceId"],
            CloudToDeviceMethod(method_name="EmergencyStop")
        )
    return func.HttpResponse("Ok", status_code=200)
