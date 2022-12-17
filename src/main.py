from agent import Agent
from asyncio import get_event_loop
from asyncua import Client
from config import Config


async def main():
    config = Config()
    agents = []

    async with Client(config.get_server_url()) as client:
        objects = client.get_objects_node()
        for device in await objects.get_children():
            device_name = (await device.read_browse_name()).Name
            if device_name != 'Server':
                agent = await Agent(
                    device=device,
                    connection_string=config.get_device_config(device_name),
                    opcua_client=client
                ).create()

                agents.append(agent)

        print(agents)

if __name__ == '__main__':
    loop = get_event_loop()
    loop.run_until_complete(main())
