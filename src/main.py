from asyncio import get_event_loop
from asyncua import Client
from config import Config


async def main():
    config = Config()

    async with Client(config.get_server_url()) as client:
        await client.check_connection()

if __name__ == '__main__':
    loop = get_event_loop()
    loop.run_until_complete(main())
