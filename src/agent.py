from asyncua.common.node import Node
from asyncua import Client, ua
from azure.iot.device import IoTHubDeviceClient, Message, MethodRequest, MethodResponse
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

        self.iothub_client.on_twin_desired_properties_patch_received = self.on_twin_desired_properties_patch_received_handler
        self.iothub_client.on_method_request_received = self.on_method_request_received_handler

        self.__tasks = []
        self.__errors = []

    def __repr__(self) -> str:
        return f'Agent ({self.device_name or "Nieznane urządzenie"})'

    def __str__(self) -> str:
        return self.__repr__()

    @property
    def tasks(self):
        tasks = self.__tasks.copy()
        tasks.append(self.send_telemetry())
        self.__tasks.clear()
        return tasks

    async def subscribed_properties(self):
        return [
            await self.get_property('ProductionRate'),
            await self.get_property('DeviceError')
        ]

    async def create(self):
        self.device_name = (await self.device.read_browse_name()).Name
        return self

    async def get_property(self, property_name: Property, with_value: bool = False) -> Union[Node, str, int]:
        property_node = await self.device.get_child(property_name)
        return property_node if not with_value else await property_node.read_value()

    async def set_property(self, property_name: Property, value: ua.Variant):
        property_node = await self.device.get_child(property_name)
        await property_node.write_value(value)

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

    def on_twin_desired_properties_patch_received_handler(self, patch: dict):
        if 'ProductionRate' in patch:
            self.__tasks.append(self.set_property(
                property_name='ProductionRate',
                value=ua.Variant(patch['ProductionRate'], ua.VariantType.Int32)
            ))

            print('Zaktualizowano ProductionRate na', patch['ProductionRate'])

    def on_method_request_received_handler(self, method_request: MethodRequest):
        if method_request.name == 'EmergencyStop':
            self.__tasks.append(self.call_method('EmergencyStop'))
            method_response = MethodResponse.create_from_method_request(
                method_request,
                200,
                'EmergencyStop'
            )
            self.iothub_client.send_method_response(method_response)
        elif method_request.name == 'ResetErrorStatus':
            self.__tasks.append(self.call_method('ResetErrorStatus'))
            method_response = MethodResponse.create_from_method_request(
                method_request,
                200,
                'ResetErrorStatus'
            )
            self.iothub_client.send_method_response(method_response)
        elif method_request.name == 'MaintenanceDone':
            self.iothub_client.patch_twin_reported_properties({
                'MaintenanceDone': datetime.now().isoformat()
            })
        else:
            method_response = MethodResponse.create_from_method_request(
                method_request,
                404,
                'Metoda nie istnieje'
            )
            self.iothub_client.send_method_response(method_response)

    async def datachange_notification(self, node, value, _):
        name = (await node.read_browse_name()).Name
        if name == 'ProductionRate':
            self.iothub_client.patch_twin_reported_properties({
                'ProductionRate': value
            })

        elif name == 'DeviceError':
            self.__errors.clear()
            errors = {
                1: 'Emergency Stop',
                2: 'Power Failure',
                4: 'Sensor Failure',
                8: 'Unknown'
            }

            for err_value, error in errors.items():
                if value & err_value:
                    if error not in self.__errors:
                        self.__errors.append(error)
                        self.send_message({'DeviceError': error}, 'event')
                        self.iothub_client.patch_twin_reported_properties({"LastErrorDate": datetime.now().isoformat()})
            self.iothub_client.patch_twin_reported_properties({"DeviceError": self.__errors})
