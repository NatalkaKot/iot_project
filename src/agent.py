from asyncua.common.node import Node
from asyncua import Client
from azure.iot.device import IoTHubDeviceClient
from typing import Literal


class Agent:
    Property = Literal[
        'ProductionStatus',
        'WorkorderId',
        'ProductionRate',
        'GoodCount',
        'BadCount',
        'Temperature',
        'DeviceError'
    ]

    Method = Literal[
        'EmergencyStop',
        'ResetErrorStatus'
    ]

    def __init__(self, device: Node, connection_string: str, opcua_client: Client):
        self.device = device
        self.device_name = None
        self.opcua_client = opcua_client

        self.iothub_client = IoTHubDeviceClient.create_from_connection_string(connection_string)
        self.iothub_client.connect()

    def __repr__(self) -> str:
        return f'Agent ({self.device_name or "Nieznane urządzenie"})'

    def __str__(self) -> str:
        return self.__repr__()

    async def create(self):
        self.device_name = (await self.device.read_browse_name()).Name
        return self

    async def get_property(self, property_name: Property, with_value: bool = False):
        property_node = await self.device.get_child(property_name)
        return property_node if not with_value else await property_node.read_value()

    async def call_method(self, method_name: Method):
        await self.device.call_method(method_name)
