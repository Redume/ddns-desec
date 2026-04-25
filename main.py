import asyncio
import aiohttp
import ipaddress
import orjson

from http import HTTPStatus

config = orjson.loads(open('config.json', "r", encoding='utf-8').read())


def parse_ip(text: str, version: int) -> str:
    for part in text.replace("=", " ").split():
        try:
            ip = ipaddress.ip_address(part.strip())
        except ValueError:
            continue

        if ip.version == version:
            return str(ip)

    raise ValueError(f"IPv{version} provider did not return an IP")


async def get_ip(version: int) -> str:
    provider_key = f"ipv{version}_provider"

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=3),
        headers={"User-Agent": "curl/8.0.0"},
    ) as session:
        async with session.get(config['providers'][provider_key]) as res:
            if not HTTPStatus(res.status).is_success:
                raise RuntimeError(f'IPv{version} provider return error')
            return parse_ip(await res.text(), version)


async def get_ip_or_none(version: int) -> str | None:
    try:
        return await get_ip(version)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, RuntimeError):
        return None
 

async def get_records() -> list:
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=3),
    ) as session:
        async with session.get(
            f'https://desec.io/api/v1/domains/{config['desec']['auth']['domain']}/rrsets', 
            headers={
                "Authorization": f"Token {config['desec']['auth']['api_token']}"
            },
        ) as res:
            if not HTTPStatus(res.status).is_success:
                raise RuntimeError("Error desec API") # change

            return await res.json()

async def update_records(*ips: str) -> bool:
    records = []

    for ip in ips:
        ip_version = ipaddress.ip_address(ip).version

        if ip_version == 4:
            if not config.get("a", True):
                continue
            record_type = "A"
        else:
            if not config.get("aaaa", True):
                continue
            record_type = "AAAA"

        for subdomain in config['desec']['subdomain']:
            records.append({
                "subname": subdomain,
                "type": record_type,
                "records": [ip],
                "ttl": config['ttl'],
            })

    if not records:
        return False

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=3),
    ) as session:
        async with session.put(
            f"https://desec.io/api/v1/domains/{config['desec']['auth']['domain']}/rrsets/",
            headers={
                "Authorization": f"Token {config['desec']['auth']['api_token']}",
                "Content-Type": "application/json"
            },
            json={"rrsets": records}
        ) as res:
            if not HTTPStatus(res.status).is_success:
                return False
            return True
    

async def main() -> None:
    tasks = []

    if config.get("a", True):
        tasks.append(get_ip_or_none(4))
    if config.get("aaaa", True):
        tasks.append(get_ip_or_none(6))

    ips = await asyncio.gather(*tasks)
    print(await update_records(*(ip for ip in ips if ip)))

if __name__ == "__main__":
    asyncio.run(main())
