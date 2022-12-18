from asyncua.common.node import Node
from asyncua import Client, ua
from azure.iot.device import IoTHubDeviceClient, Message
from typing import Literal, Union
from uuid import uuid4
from datetime import datetime
import json


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

    MessageType = Literal[
        'Telemetry',
        'Event'
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

    async def get_property(self, property_name: Property, with_value: bool = False) -> Union[Node, str, int]:
        property_node = await self.device.get_child(property_name)
        return property_node if not with_value else await property_node.read_value()

    async def set_property(self, property_name: Property, value: ua.Variant):
        await self.device.get_child(property_name).write_value(value)

    async def call_method(self, method_name: Method):
        await self.device.call_method(method_name)

    async def send_telemetry(self):
        data = {
            'ProductionStatus': await self.get_property('ProductionStatus', with_value=True),
            'WorkorderId': await self.get_property('WorkorderId', with_value=True),
            'GoodCount': await self.get_property('GoodCount', with_value=True),
            'BadCount': await self.get_property('BadCount', with_value=True),
            'Temperature': await self.get_property('Temperature', with_value=True),
        }

        print(datetime.now().isoformat(), data)
        self.send_message(data, 'Telemetry')

    def send_message(self, data: dict, message_type: MessageType):
        data['MessageType'] = message_type
        message = Message(
            data=json.dumps(data),
            content_encoding='utf-8',
            content_type='application/json',
            message_id=str(uuid4())
        )
        self.iothub_client.send_message(message)
