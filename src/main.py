from agent import Agent
from asyncio import get_event_loop, gather, sleep
from asyncua import Client
from config import Config


async def main():
    config = Config()
    agents, subscriptions = [], []

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

                subscription = await client.create_subscription(250, agent)
                await subscription.subscribe_data_change(await agent.subscribed_properties())

                subscriptions.append(subscription)

        while True:
            for agent in agents:
                await gather(*agent.tasks)
            await sleep(1)

if __name__ == '__main__':
    loop = get_event_loop()
    loop.run_until_complete(main())
