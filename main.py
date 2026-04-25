import asyncio
import aiohttp
import orjson

from http import HTTPStatus

config = orjson.loads(open('config.json', "r", encoding='utf-8').read())


async def get_ip(version: int) -> str:
    provider_key = f"ipv{version}_provider"

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=3),
        headers={"User-Agent": "curl/8.0.0"},
    ) as session:
        async with session.get(config['providers'][provider_key]) as res:
            if not HTTPStatus(res.status).is_success:
                raise RuntimeError(f'IPv{version} provider return error')
            return (await res.text()).strip()
 

async def main() -> None:
   await get_ip(4)

if __name__ == "__main__":
    asyncio.run(main())